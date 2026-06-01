import { FC } from 'react';
import { Field } from '@decky/ui';
import type { ConnectionStatus } from '../services/api';

interface StatusDisplayProps {
  status: ConnectionStatus;
  errorMessage?: string | null;
  uptime?: number | null;
  connectedAt?: number | null;
  uplink?: number;
  downlink?: number;
}

export const StatusDisplay: FC<StatusDisplayProps> = ({
  status,
  errorMessage,
  uptime,
  connectedAt,
  uplink,
  downlink,
}) => {
  const getStatusColor = (): string => {
    switch (status) {
      case 'connected':
        return '#6bff6b';
      case 'connecting':
        return '#ffd93d';
      case 'error':
        return '#ff6b6b';
      case 'blocked':
        return '#ff6b6b';
      default:
        return '#aaa';
    }
  };

  const getStatusText = (): string => {
    switch (status) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Error';
      case 'blocked':
        return 'Blocked (Kill Switch)';
      default:
        return 'Disconnected';
    }
  };

  const formatUptime = (seconds?: number | null): string => {
    if (!seconds) return '';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const formatSpeed = (bytesPerSec?: number): string => {
    if (bytesPerSec === undefined || bytesPerSec === null) return '0 B/s';
    if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
    if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSec / (1024 * 1024)).toFixed(2)} MB/s`;
  };

  const statusIndicator = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div
        style={{
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          backgroundColor: getStatusColor(),
        }}
      />
      <span style={{ fontWeight: 600 }}>{getStatusText()}</span>
    </div>
  );

  return (
    <>
      <Field
        label="Connection Status"
        description={statusIndicator}
      />

      {status === 'connected' && uptime != null && (
        <Field
          label="Uptime"
          description={formatUptime(uptime)}
        />
      )}
      {status === 'connected' && connectedAt && (
        <Field
          label="Connected At"
          description={new Date(connectedAt * 1000).toLocaleString()}
        />
      )}

      {status === 'connected' && (
        <Field label="Traffic">
          <div style={{ display: 'flex', gap: '20px', justifyContent: 'flex-end' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
              <span style={{ fontSize: '12px', color: '#8f98a0', textTransform: 'uppercase' }}>↓ Download</span>
              <span style={{ fontSize: '14px', color: '#57cb70', fontWeight: 'bold' }}>{formatSpeed(downlink)}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
              <span style={{ fontSize: '12px', color: '#8f98a0', textTransform: 'uppercase' }}>↑ Upload</span>
              <span style={{ fontSize: '14px', color: '#66c0f4', fontWeight: 'bold' }}>{formatSpeed(uplink)}</span>
            </div>
          </div>
        </Field>
      )}

      {status === 'error' && errorMessage && (
        <Field
          label="Error"
          description={
            <span style={{ color: '#ff6b6b' }}>{errorMessage}</span>
          }
        />
      )}

      {status === 'blocked' && (
        <Field
          label="Kill Switch"
          description={
            <span style={{ color: '#ff6b6b' }}>
              All traffic is blocked. Reconnect to restore.
            </span>
          }
        />
      )}
    </>
  );
};
