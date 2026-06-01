import { FC, useState } from 'react';
import type { Subscription, VLESSConfig } from '../services/api';
import { showModal, ConfirmModal, TextField, ModalRoot, PanelSection, PanelSectionRow, Field, ButtonItem, Focusable, DialogButton } from '@decky/ui';
import { toaster } from '@decky/api';
import { QRImportBlock } from './QRImportBlock';

const SubRow: FC<{
  sub: Subscription;
  subConfigs: VLESSConfig[];
  isExpanded: boolean;
  toggleSub: () => void;
  isUpdating: boolean;
  isLocked: boolean;
  onUpdate: () => Promise<void>;
  onDelete: () => void;
}> = ({ sub, subConfigs, isExpanded, toggleSub, isUpdating, isLocked, onUpdate, onDelete }) => {
  const [isFocused, setIsFocused] = useState(false);
  return (
    <PanelSectionRow>
      <Focusable
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onClick={toggleSub}
        onActivate={toggleSub}
        style={{
          padding: '4px',
          borderRadius: '4px',
          outline: isFocused ? '2px solid #ffffff' : 'none',
          outlineOffset: '-2px',
        }}
      >
        <Field
          label={sub.title}
          description={
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {isExpanded && sub.announce && (
                <span style={{ fontStyle: 'italic', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>{sub.announce}</span>
              )}
              <span>{subConfigs.length} nodes</span>
            </div>
          }
        >
          <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
            <Focusable
              onClick={async (e: React.MouseEvent) => { e.stopPropagation(); await onUpdate(); }}
              onActivate={async (e: Event) => { e.stopPropagation(); await onUpdate(); }}
              style={{ color: '#ffffff', fontSize: '16px', padding: '4px', opacity: (isLocked || isUpdating) ? 0.5 : 1 }}
            >
              {isUpdating ? '⏳' : '🔄'}
            </Focusable>
            <Focusable
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); onDelete(); }}
              onActivate={(e: Event) => { e.stopPropagation(); onDelete(); }}
              style={{ color: '#ff6b6b', fontSize: '16px', padding: '4px', opacity: isLocked ? 0.5 : 1 }}
            >
              🗑️
            </Focusable>
            <span style={{ fontSize: '14px', width: '20px', textAlign: 'center' }}>
              {isExpanded ? '▼' : '▶'}
            </span>
          </div>
        </Field>
      </Focusable>
    </PanelSectionRow>
  );
};

const ConfigRow: FC<{
  config: VLESSConfig;
  isActive: boolean;
  isLocked: boolean;
  onSelect: () => void;
  onDelete?: () => void;
  showDetails?: boolean;
}> = ({ config, isActive, isLocked, onSelect, onDelete, showDetails }) => {
  const [isFocused, setIsFocused] = useState(false);
  return (
    <PanelSectionRow>
      <Focusable
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onClick={onSelect}
        onActivate={onSelect}
        style={{
          padding: '4px 6px',
          borderRadius: '4px',
          backgroundColor: isActive ? 'rgba(87, 203, 112, 0.15)' : (isFocused ? 'rgba(255, 255, 255, 0.1)' : 'transparent'),
          borderLeft: isActive ? '3px solid #57cb70' : '3px solid transparent',
          outline: isFocused ? '2px solid #ffffff' : 'none',
          outlineOffset: '-2px',
          transition: 'all 0.15s',
        }}
      >
        <Field
          label={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                border: isActive ? '2px solid #57cb70' : '2px solid #5a6370',
                backgroundColor: isActive ? '#57cb70' : 'transparent',
                flexShrink: 0,
                transition: 'all 0.15s',
              }}>
                {isActive && <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#fff' }} />}
              </span>
              <span>{config.name || config.address}</span>
            </div>
          }
          description={
            showDetails ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span>{config.address}:{config.port}</span>
                <span style={{ fontStyle: 'italic' }}>{(config as any).serverDescription || 'No description'}</span>
              </div>
            ) : (
              (config as any).serverDescription || 'No description'
            )
          }
        >
          <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
            {isActive && (
              <span style={{ color: '#57cb70', fontWeight: 'bold', fontSize: '12px' }}>Active</span>
            )}
            {onDelete && (
              <Focusable
                onClick={(e: React.MouseEvent) => { e.stopPropagation(); onDelete(); }}
                onActivate={(e: Event) => { e.stopPropagation(); onDelete(); }}
                style={{ color: '#ff6b6b', fontSize: '16px', padding: '4px', opacity: isLocked ? 0.5 : 1 }}
              >
                🗑️
              </Focusable>
            )}
          </div>
        </Field>
      </Focusable>
    </PanelSectionRow>
  );
};

interface ProfilesTabProps {
  configs: VLESSConfig[];
  subscriptions: Subscription[];
  activeConfigId?: string;
  onSetActiveConfig: (id: string) => Promise<{ success: boolean; error?: string }>;
  onDeleteConfig: (id: string) => Promise<{ success: boolean; error?: string }>;
  onDeleteSubscription: (id: string) => Promise<{ success: boolean; error?: string }>;
  onUpdateSubscription: (id: string) => Promise<{ success: boolean; error?: string }>;
  onAddProvider: (url: string) => Promise<{ success: boolean; error?: string }>;
  isLocked: boolean;
}

export const ProfilesTab: FC<ProfilesTabProps> = ({
  configs,
  subscriptions,
  activeConfigId,
  onSetActiveConfig,
  onDeleteConfig,
  onDeleteSubscription,
  onUpdateSubscription,
  onAddProvider,
  isLocked,
}) => {
  const [expandedSubs, setExpandedSubs] = useState<Record<string, boolean>>({});
  const [isUpdating, setIsUpdating] = useState<Record<string, boolean>>({});

  const toggleSub = (subId: string) => {
    setExpandedSubs((prev) => ({
      ...prev,
      [subId]: !prev[subId],
    }));
  };

  const getSubConfigs = (subId?: string) => {
    if (!subId) return configs.filter(c => !c.sub_id);
    return configs.filter(c => c.sub_id === subId);
  };

  const singleConfigs = getSubConfigs(undefined);

  return (
    <>
      {subscriptions.map(sub => {
        const subConfigs = getSubConfigs(sub.id);
        const isExpanded = expandedSubs[sub.id];
        return (
          <PanelSection key={`sub-${sub.id}`}>
            <SubRow
              sub={sub}
              subConfigs={subConfigs}
              isExpanded={isExpanded}
              toggleSub={() => toggleSub(sub.id)}
              isUpdating={!!isUpdating[sub.id]}
              isLocked={isLocked}
              onUpdate={async () => {
                if (isLocked || isUpdating[sub.id]) return;
                setIsUpdating(p => ({ ...p, [sub.id]: true }));
                const res = await onUpdateSubscription(sub.id);
                setIsUpdating(p => ({ ...p, [sub.id]: false }));
                if (res.success) {
                  toaster.toast({ title: 'Subscription Updated', body: 'Successfully updated nodes.' });
                } else {
                  toaster.toast({ title: 'Update Failed', body: res.error || 'Unknown error' });
                }
              }}
              onDelete={() => {
                if (isLocked) return;
                showModal(
                  <ConfirmModal
                    strTitle="Delete Subscription"
                    strDescription="Are you sure you want to delete this subscription and all its nodes?"
                    onOK={() => void onDeleteSubscription(sub.id)}
                  />
                );
              }}
            />
            {isExpanded && subConfigs.map(c => (
              <ConfigRow
                key={c.id}
                config={c}
                isActive={activeConfigId === c.id}
                isLocked={isLocked}
                onSelect={() => { if (!isLocked && c.id) void onSetActiveConfig(c.id); }}
              />
            ))}
          </PanelSection>
        );
      })}

      {singleConfigs.length > 0 && (
        <PanelSection title="Imported Links">
          {singleConfigs.map(c => (
            <ConfigRow
              key={c.id}
              config={c}
              isActive={activeConfigId === c.id}
              isLocked={isLocked}
              onSelect={() => { if (!isLocked && c.id) void onSetActiveConfig(c.id); }}
              showDetails={true}
              onDelete={() => {
                if (isLocked || !c.id) return;
                showModal(
                  <ConfirmModal
                    strTitle="Delete Config"
                    strDescription="Are you sure you want to delete this configuration?"
                    onOK={() => void onDeleteConfig(c.id!)}
                  />
                );
              }}
            />
          ))}
        </PanelSection>
      )}

      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            let tempUrl = '';
            showModal(
              <ModalRoot>
                <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '10px', boxSizing: 'border-box' }}>
                  <h3 style={{ margin: 0, color: 'white' }}>Add New Provider</h3>
                  <div style={{ borderBottom: '1px solid #3a5f8f', paddingBottom: '15px' }}>
                    <QRImportBlock />
                  </div>
                  <p style={{ margin: 0, color: '#8f98a0', fontSize: '14px', marginTop: '10px' }}>Paste a subscription link (vless:// or hy2:// or https://...) to add a new provider.</p>
                  <TextField
                    value={tempUrl}
                    onChange={(e: any) => { tempUrl = e.target ? e.target.value : e; }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                    <DialogButton onClick={() => { if (tempUrl) onAddProvider(tempUrl); }}>
                      Add Provider
                    </DialogButton>
                  </div>
                </div>
              </ModalRoot>
            );
          }}
          disabled={isLocked}
        >
          + Add New Provider
        </ButtonItem>
      </PanelSectionRow>
    </>
  );
};
