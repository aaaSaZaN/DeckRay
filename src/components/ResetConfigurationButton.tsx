import { FC, useState } from 'react';
import { ButtonItem, ConfirmModal, showModal } from '@decky/ui';

interface ResetConfigurationButtonProps {
  disabled?: boolean;
  onReset: () => Promise<{ success: boolean; error?: string }>;
}

export const ResetConfigurationButton: FC<ResetConfigurationButtonProps> = ({
  disabled,
  onReset,
}) => {
  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      const result = await onReset();
      if (!result.success) {
        console.error('Failed to reset configuration:', result.error);
        showModal(
          <ConfirmModal
            strTitle="Reset failed"
            strDescription={`Error: ${result.error}`}
            bDestructiveWarning={false}
          />
        );
      }
    } catch (err) {
      console.error('Failed to reset configuration:', err);
    } finally {
      setIsResetting(false);
    }
  };

  const confirmReset = () => {
    showModal(
      <ConfirmModal
        strTitle="Reset Configuration"
        strDescription="Are you sure you want to completely remove the saved connection configuration? This action cannot be undone."
        onOK={handleReset}
      />
    );
  };

  return (
    <ButtonItem
      layout="below"
      onClick={confirmReset}
      disabled={disabled || isResetting}
    >
      {isResetting ? 'Resetting...' : 'Reset to default'}
    </ButtonItem>
  );
};
