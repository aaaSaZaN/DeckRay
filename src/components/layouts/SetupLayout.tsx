import { FC } from 'react';
import { PanelSection, PanelSectionRow } from '@decky/ui';
import { ConfigImport } from '../ConfigImport';

interface SetupLayoutProps {
  vlessUrl: string;
  onVlessUrlChange: (value: string) => void;
  onSave: () => void;
  isSaving: boolean;
  error?: string | null;
  successMessage?: string | null;
}

export const SetupLayout: FC<SetupLayoutProps> = ({
  vlessUrl,
  onVlessUrlChange,
  onSave,
  isSaving,
  error,
  successMessage,
}) => {
  return (
    <PanelSection title="Setup DeckRay">
      <PanelSectionRow>
        <ConfigImport
          value={vlessUrl}
          onChange={onVlessUrlChange}
          onSave={onSave}
          isSaving={isSaving}
          error={error}
          successMessage={successMessage}
          helpTopic="setup.qr_import"
        />
      </PanelSectionRow>
    </PanelSection>
  );
};
