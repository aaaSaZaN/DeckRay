import type { CSSProperties } from 'react';
import { FC, useCallback, useState } from 'react';
import { PanelSection, PanelSectionRow, Focusable } from '@decky/ui';
import { ConfigSummaryCard } from '../ConfigSummaryCard';
import { ConnectionToggle } from '../ConnectionToggle';
import { KillSwitchToggle } from '../KillSwitchToggle';
import { ResetConfigurationButton } from '../ResetConfigurationButton';
import { StatusDisplay } from '../StatusDisplay';
import { TUNModeToggle } from '../TUNModeToggle';
import { HelpPopover } from '../ui/HelpPopover';
import { ProfilesTab } from '../ProfilesTab';
import { XrayVersionSelector } from '../XrayVersionSelector';
import { LogViewer } from '../LogViewer';
import { XrayVersionBadge } from '../XrayVersionBadge';


import type {
  CheckPrivilegesResponse,
  DeactivateKillSwitchResponse,
  ToggleConnectionResponse,
  ToggleKillSwitchResponse,
  ToggleTUNModeResponse,
} from '../../services/api';
import type { ConnectionConfigSummary, ConnectionState, OptionsState } from '../../types/ui';
import type { Subscription, VLESSConfig } from '../../services/api';

const TAB_MAIN = 'main';
const TAB_PROFILES = 'profiles';
const TAB_CONFIG_INFO = 'config-info';
const TAB_OPTIONS = 'options';

const TAB_TITLES: Record<string, string> = {
  [TAB_MAIN]: 'Connection',
  [TAB_PROFILES]: 'Profiles',
  [TAB_CONFIG_INFO]: 'Config',
  [TAB_OPTIONS]: 'Options',
};

const TAB_SIZE = 44;
const FOCUS_RING_STYLE: CSSProperties = {
  boxShadow: '0 0 0 2px #ffffff',
  borderColor: '#ffffff',
};

const tabButtonBaseStyle: CSSProperties = {
  width: TAB_SIZE,
  height: TAB_SIZE,
  minWidth: TAB_SIZE,
  minHeight: TAB_SIZE,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  backgroundColor: '#2c3b48',
  border: '1px solid #3a4a58',
  borderRadius: '6px',
  color: '#c7d5e0',
  cursor: 'pointer',
  boxSizing: 'border-box',
};

interface TabButtonProps {
  icon: string;
  isActive: boolean;
  isFocused: boolean;
  onSelect: () => void;
  onFocus: () => void;
  onBlur: () => void;
}

const TabButton: FC<TabButtonProps> = ({
  icon,
  isActive,
  isFocused,
  onSelect,
  onFocus,
  onBlur,
}) => (
  <Focusable
    onClick={(e: React.MouseEvent) => {
      e.preventDefault();
      onSelect();
    }}
    onActivate={() => onSelect()}
    onFocus={onFocus}
    onBlur={onBlur}
    style={{
      ...tabButtonBaseStyle,
      ...(isActive ? { borderColor: '#ffffff', backgroundColor: '#3a4a58', color: '#ffffff' } : {}),
      ...(isFocused ? FOCUS_RING_STYLE : {}),
    }}
  >
    <span style={{ fontSize: '18px' }}>{icon}</span>
  </Focusable>
);

interface ConfiguredLayoutProps {
  configSummary: ConnectionConfigSummary;
  connection: ConnectionState;
  options: OptionsState;
  onToggleConnection: (enable: boolean) => Promise<ToggleConnectionResponse>;
  onToggleTUNMode: (enabled: boolean) => Promise<ToggleTUNModeResponse>;
  onCheckTUNPrivileges: () => Promise<CheckPrivilegesResponse>;
  onToggleKillSwitch: (enabled: boolean) => Promise<ToggleKillSwitchResponse>;
  onDeactivateKillSwitch: () => Promise<DeactivateKillSwitchResponse>;
  onResetConfig: () => Promise<{ success: boolean; error?: string }>;
  configs: VLESSConfig[];
  subscriptions: Subscription[];
  activeConfigId?: string;
  onSetActiveConfig: (id: string) => Promise<{ success: boolean; error?: string }>;
  onDeleteConfig: (id: string) => Promise<{ success: boolean; error?: string }>;
  onDeleteSubscription: (id: string) => Promise<{ success: boolean; error?: string }>;
  onUpdateSubscription: (id: string) => Promise<{ success: boolean; error?: string }>;
  onAddProvider: (url: string) => Promise<{ success: boolean; error?: string }>;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const ConfiguredLayout: FC<ConfiguredLayoutProps> = ({
  configSummary,
  connection,
  options,
  onToggleConnection,
  onToggleTUNMode,
  onCheckTUNPrivileges,
  onToggleKillSwitch,
  onDeactivateKillSwitch,
  onResetConfig,
  configs,
  subscriptions,
  activeConfigId,
  onSetActiveConfig,
  onDeleteConfig,
  onDeleteSubscription,
  onUpdateSubscription,
  onAddProvider,
  activeTab,
  setActiveTab,
}) => {
  const [focusedTabIndex, setFocusedTabIndex] = useState<number | null>(null);
  const isResetDisabled = ['connecting', 'connected', 'blocked'].includes(connection.status);
  const isLocked = isResetDisabled;

  const tabIds = [TAB_MAIN, TAB_PROFILES, TAB_CONFIG_INFO, TAB_OPTIONS] as const;

  const tabRowStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'row',
    gap: '8px',
    alignItems: 'center',
  };

  return (
    <PanelSection title={TAB_TITLES[activeTab] ?? 'Connection'}>
      <PanelSectionRow>
        <Focusable {...{ 'flow-children': 'right' }} style={tabRowStyle}>
          <TabButton
            icon="🔌"
            isActive={activeTab === TAB_MAIN}
            isFocused={focusedTabIndex === 0}
            onSelect={() => setActiveTab(TAB_MAIN)}
            onFocus={() => setFocusedTabIndex(0)}
            onBlur={() => setFocusedTabIndex(null)}
          />
          <TabButton
            icon="📂"
            isActive={activeTab === TAB_PROFILES}
            isFocused={focusedTabIndex === 1}
            onSelect={() => setActiveTab(TAB_PROFILES)}
            onFocus={() => setFocusedTabIndex(1)}
            onBlur={() => setFocusedTabIndex(null)}
          />
          <TabButton
            icon="ℹ️"
            isActive={activeTab === TAB_CONFIG_INFO}
            isFocused={focusedTabIndex === 2}
            onSelect={() => setActiveTab(TAB_CONFIG_INFO)}
            onFocus={() => setFocusedTabIndex(2)}
            onBlur={() => setFocusedTabIndex(null)}
          />
          <TabButton
            icon="⚙️"
            isActive={activeTab === TAB_OPTIONS}
            isFocused={focusedTabIndex === 3}
            onSelect={() => setActiveTab(TAB_OPTIONS)}
            onFocus={() => setFocusedTabIndex(3)}
            onBlur={() => setFocusedTabIndex(null)}
          />
        </Focusable>
      </PanelSectionRow>

      {activeTab === TAB_MAIN && (
        <>
          <PanelSectionRow>
            <ConnectionToggle status={connection.status} onToggle={onToggleConnection} />
          </PanelSectionRow>
          <PanelSectionRow>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
              }}
            >
              <span style={{ fontSize: '14px', fontWeight: 600, color: '#c7d5e0' }}>Status</span>
              <HelpPopover label="Help: status" topic="configured.status" />
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <StatusDisplay
              status={connection.status}
              errorMessage={connection.message}
              uptime={connection.uptime}
              connectedAt={connection.connectedAt}
              uplink={connection.uplink}
              downlink={connection.downlink}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <XrayVersionBadge />
          </PanelSectionRow>
        </>
      )}

      {activeTab === TAB_CONFIG_INFO && (
        <ConfigSummaryCard summary={configSummary} />
      )}

      {activeTab === TAB_PROFILES && (
        <PanelSectionRow>
          <ProfilesTab
            configs={configs}
            subscriptions={subscriptions}
            activeConfigId={activeConfigId}
            onSetActiveConfig={onSetActiveConfig}
            onDeleteConfig={onDeleteConfig}
            onDeleteSubscription={onDeleteSubscription}
            onUpdateSubscription={onUpdateSubscription}
            onAddProvider={onAddProvider}
            isLocked={isLocked}
          />
        </PanelSectionRow>
      )}

      {activeTab === TAB_OPTIONS && (
        <>
          <PanelSectionRow>
            <TUNModeToggle
              enabled={options.tunEnabled}
              hasPrivileges={options.tunHasPrivileges}
              isActive={options.tunActive}
              onToggle={onToggleTUNMode}
              onCheckPrivileges={onCheckTUNPrivileges}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <KillSwitchToggle
              enabled={options.killSwitchEnabled}
              isActive={options.killSwitchActive}
              activatedAt={options.killSwitchActivatedAt}
              onToggle={onToggleKillSwitch}
              onDeactivate={onDeactivateKillSwitch}
            />
          </PanelSectionRow>
          <XrayVersionSelector />
          <LogViewer />
          <PanelSectionRow>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
                marginBottom: '4px',
              }}
            >
              <span style={{ fontSize: '14px', fontWeight: 600, color: '#c7d5e0' }}>
                Reset configuration
              </span>
              <HelpPopover label="Help: reset configuration" topic="configured.reset" />
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <ResetConfigurationButton disabled={isResetDisabled} onReset={onResetConfig} />
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
};
