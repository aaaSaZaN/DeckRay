import { FC, useState } from 'react';
import type { ConnectionConfigSummary } from '../types/ui';
import { showModal, ModalRoot, Field, ButtonItem, PanelSectionRow } from '@decky/ui';
import { MenuSelector } from './MenuSelector';
import { pingHost } from '../services/api';

const PING_METHODS = [
  { label: 'HTTP GET', data: 'http_get' },
  { label: 'HTTP HEAD', data: 'http_head' },
  { label: 'TCP', data: 'tcp' },
  { label: 'ICMP', data: 'icmp' },
];

interface ConfigSummaryCardProps {
  summary: ConnectionConfigSummary;
}

export const ConfigSummaryCard: FC<ConfigSummaryCardProps> = ({ summary }) => {
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [isPinging, setIsPinging] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const [pingMethod, setPingMethod] = useState<string>('http_get');

  if (!summary.exists) {
    return null;
  }

  const handlePing = async () => {
    if (!summary.endpoint) return;
    setIsPinging(true);
    setPingResult('Pinging...');
    try {
      const res = await pingHost(summary.endpoint, pingMethod);
      if (res.success && res.latencyMs !== undefined) {
        setPingResult(`${res.latencyMs} ms`);
      } else {
        setPingResult(res.error ? 'Err' : 'Timeout');
        if (res.error) console.error("Ping Error:", res.error);
      }
    } catch (e) {
      setPingResult('Error');
    }
    setIsPinging(false);
  };

  const showJsonModal = () => {
    if (!summary.nativeConfig) return;
    showModal(
      <ModalRoot>
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '80vh' }}>
          <h3 style={{ margin: 0, color: 'white' }}>JSON Configuration</h3>
          <div style={{ 
            overflowY: 'auto', 
            backgroundColor: '#1b2838', 
            padding: '10px', 
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'monospace',
            color: '#c7d5e0',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all'
          }}>
            {JSON.stringify(summary.nativeConfig, null, 2)}
          </div>
        </div>
      </ModalRoot>
    );
  };

  const protocolDisplay = summary.protocol === 'native_json' ? 'JSON' : (summary.protocol?.toUpperCase() || 'VLESS');

  const desc = summary.serverDescription || 'There is no description here. Well, none.';
  const hasDesc = !!summary.serverDescription;
  const isLong = desc.length > 120;
  const shown = isLong && !descExpanded ? desc.slice(0, 120) + '…' : desc;

  return (
    <>
      <Field
        label={summary.displayName || 'Unnamed Configuration'}
        description={
          <div style={{ color: hasDesc ? '#8f98a0' : '#5a6370', fontStyle: 'italic', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
            {shown}
            {isLong && (
              <span
                onClick={(e) => { e.stopPropagation(); setDescExpanded(!descExpanded); }}
                style={{ color: '#ffffff', cursor: 'pointer', marginLeft: '4px', fontStyle: 'normal' }}
              >
                {descExpanded ? '▲ Less' : '▼ More'}
              </span>
            )}
          </div>
        }
      >
        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '12px', color: '#c7d5e0', fontWeight: 'bold' }}>STATUS</span>
          <span style={{ fontSize: '14px', color: summary.isValid ? '#57cb70' : '#ff6b6b' }}>
            {summary.isValid ? 'Valid' : 'Invalid'}
          </span>
        </div>
      </Field>

      <Field label="Protocol" description={
        summary.protocol === 'native_json' ? (
          <span 
            onClick={showJsonModal}
            style={{ color: '#ffffff', cursor: 'pointer', textDecoration: 'underline' }}
          >
            {protocolDisplay}
          </span>
        ) : protocolDisplay
      } />

      {summary ? (
        <>
          <PanelSectionRow>
            <Field label="Address" description={summary.endpoint} />
          </PanelSectionRow>
          
          <PanelSectionRow>
            <MenuSelector
              label="Ping Method"
              value={pingMethod}
              options={PING_METHODS}
              onChange={(opt: any) => setPingMethod(opt as string)}
            />
          </PanelSectionRow>

          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handlePing}
              disabled={isPinging}
            >
              {isPinging ? 'Pinging...' : 'Test Connection Ping'}
            </ButtonItem>
          </PanelSectionRow>
          
          {pingResult !== null && (
            <PanelSectionRow>
              <div style={{ marginTop: '8px', padding: '10px', backgroundColor: '#2a2a2a', borderRadius: '4px' }}>
                {!(pingResult === 'Err' || pingResult === 'Timeout' || pingResult === 'Error' || pingResult === 'Pinging...') ? (
                  <span style={{ color: '#4CAF50' }}>Success: {pingResult}</span>
                ) : (
                  <span style={{ color: '#f44336' }}>{pingResult === 'Pinging...' ? pingResult : 'Failed to ping server'}</span>
                )}
              </div>
            </PanelSectionRow>
          )}
        </>
      ) : null}

      {summary.validationError && (
        <Field label="Validation Error" description={
          <span style={{ color: '#ff6b6b' }}>{summary.validationError}</span>
        } />
      )}
    </>
  );
};
