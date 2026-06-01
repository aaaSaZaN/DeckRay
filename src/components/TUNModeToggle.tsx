import { FC, useState } from 'react';
import { ToggleField, Field } from '@decky/ui';
import { HelpPopover } from './ui/HelpPopover';
import type { CheckPrivilegesResponse, ToggleTUNModeResponse } from '../services/api';

interface TUNModeToggleProps {
  enabled: boolean;
  hasPrivileges: boolean;
  isActive: boolean;
  tunInterface?: string | null;
  onToggle: (enabled: boolean) => Promise<ToggleTUNModeResponse>;
  onCheckPrivileges: () => Promise<CheckPrivilegesResponse>;
}

export const TUNModeToggle: FC<TUNModeToggleProps> = ({
  enabled,
  hasPrivileges,
  isActive,
  tunInterface,
  onToggle,
  onCheckPrivileges,
}) => {
  const [loading, setLoading] = useState(false);
  const [checkingPrivileges, setCheckingPrivileges] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (nextEnabled: boolean) => {
    setError(null);
    setLoading(true);

    try {
      const result = await onToggle(nextEnabled);
      if (!result.success) {
        setError(result.error || 'Failed to toggle TUN mode');
      }
    } catch (err) {
      console.error('Toggle error:', err);
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const descriptionContent = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <span>Overrides default TUN mode. Works worse in Gaming Mode.</span>
      {loading && (
        <span style={{ color: '#8f98a0', fontStyle: 'italic' }}>
          {enabled ? 'Disabling TUN mode...' : 'Enabling TUN mode...'}
        </span>
      )}
    </div>
  );

  return (
    <>
      <ToggleField
        label="Use System Proxy"
        description={descriptionContent}
        checked={!enabled}
        disabled={loading || checkingPrivileges}
        onChange={(newVal: boolean) => handleToggle(!newVal)}
      />

      {!enabled && (
        <Field
          label="Warning: System Proxy"
          description={
            <span style={{ color: '#ffb86b' }}>
              System Proxy performs worse in SteamOS Gaming Mode than the default TUN connection. It may cause disconnects or fail to route game traffic correctly.
            </span>
          }
        />
      )}

      {error && (
        <Field
          label="TUN Mode Error"
          description={<span style={{ color: '#ff6b6b' }}>{error}</span>}
        />
      )}
    </>
  );
};
