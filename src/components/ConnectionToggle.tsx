import { FC, useMemo, useState } from 'react';
import { ToggleField, Field } from '@decky/ui';
import type { ConnectionStatus, ToggleConnectionResponse } from '../services/api';

interface ConnectionToggleProps {
  status: ConnectionStatus;
  onToggle: (enable: boolean) => Promise<ToggleConnectionResponse>;
}

export const ConnectionToggle: FC<ConnectionToggleProps> = ({ status, onToggle }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEnabled = status === 'connected' || status === 'connecting';

  const isToggleDisabled = useMemo(() => {
    return loading || status === 'connecting' || status === 'blocked';
  }, [loading, status]);

  const description = useMemo(() => {
    if (status === 'blocked') {
      return 'Kill switch is active. Disable it to reconnect.';
    }
    if (loading) {
      return status === 'connecting' ? 'Connecting…' : 'Disconnecting…';
    }
    return isEnabled ? 'Proxy is active.' : 'Proxy is inactive';
  }, [isEnabled, loading, status]);

  const handleToggle = async (nextEnabled: boolean) => {
    setError(null);
    setLoading(true);

    try {
      const result = await onToggle(nextEnabled);
      if (!result.success) {
        setError(result.error || 'Failed to toggle connection');
      }
    } catch (err) {
      console.error('Toggle error:', err);
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <ToggleField
        label="Enable Connection"
        description={description}
        checked={isEnabled}
        disabled={isToggleDisabled}
        onChange={handleToggle}
      />

      {error && (
        <Field
          label="Connection Error"
          description={<span style={{ color: '#ff6b6b' }}>{error}</span>}
        />
      )}

      {status === 'blocked' && (
        <Field
          label="Kill Switch Active"
          description={
            <span style={{ color: '#ff6b6b' }}>
              Connection is blocked. Please disable kill switch first.
            </span>
          }
        />
      )}
    </>
  );
};
