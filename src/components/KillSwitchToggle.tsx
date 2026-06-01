import { FC, useState } from 'react';
import { ToggleField, Field, ButtonItem } from '@decky/ui';
import type { DeactivateKillSwitchResponse, ToggleKillSwitchResponse } from '../services/api';

interface KillSwitchToggleProps {
  enabled: boolean;
  isActive: boolean;
  activatedAt?: number | null;
  onToggle: (enabled: boolean) => Promise<ToggleKillSwitchResponse>;
  onDeactivate: () => Promise<DeactivateKillSwitchResponse>;
}

export const KillSwitchToggle: FC<KillSwitchToggleProps> = ({
  enabled,
  isActive,
  activatedAt,
  onToggle,
  onDeactivate,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (nextEnabled: boolean) => {
    setError(null);
    setLoading(true);

    try {
      const result = await onToggle(nextEnabled);
      if (!result.success) {
        setError('Failed to toggle kill switch');
      }
    } catch (err) {
      console.error('Toggle error:', err);
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async () => {
    setError(null);
    setLoading(true);

    try {
      const result = await onDeactivate();
      if (!result.success) {
        setError(result.error || 'Failed to deactivate kill switch');
      }
    } catch (err) {
      console.error('Deactivate error:', err);
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timestamp: number | null): string => {
    if (!timestamp) return '';
    return new Date(timestamp * 1000).toLocaleString();
  };

  const descriptionContent = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <span>Blocks all traffic if the proxy disconnects unexpectedly.</span>
      {loading && (
        <span style={{ color: '#8f98a0', fontStyle: 'italic' }}>
          {enabled ? 'Disabling kill switch...' : 'Enabling kill switch...'}
        </span>
      )}
    </div>
  );

  return (
    <>
      <ToggleField
        label="Enable Kill Switch"
        description={descriptionContent}
        checked={enabled}
        disabled={loading}
        onChange={handleToggle}
      />

      {isActive && (
        <>
          <Field
            label="⚠️ KILL SWITCH ACTIVE"
            description={
              <div style={{ color: '#ff6b6b' }}>
                <p>All system traffic is currently blocked. This happened because the proxy disconnected unexpectedly.</p>
                {activatedAt && <p>Activated at: {formatTime(activatedAt)}</p>}
              </div>
            }
          />
          <ButtonItem onClick={handleDeactivate} disabled={loading}>
            {loading ? 'Deactivating...' : 'Deactivate Kill Switch'}
          </ButtonItem>
        </>
      )}

      {error && (
        <Field
          label="Kill Switch Error"
          description={<span style={{ color: '#ff6b6b' }}>{error}</span>}
        />
      )}
    </>
  );
};
