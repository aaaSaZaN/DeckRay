import { FC, useState, useEffect } from 'react';
import { ButtonItem, TextField, Field } from '@decky/ui';
import { HelpPopover } from './ui/HelpPopover';
import { QRImportBlock } from './QRImportBlock';
import type { HelpTopic } from '../types/ui';

interface ConfigImportProps {
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  isSaving: boolean;
  error?: string | null;
  successMessage?: string | null;
  helpTopic?: HelpTopic;
}

export const ConfigImport: FC<ConfigImportProps> = ({
  value,
  onChange,
  onSave,
  isSaving,
  error,
  successMessage,
  helpTopic,
}) => {
  const labelText = isSaving ? 'Saving…' : 'Save configuration';

  const [localValue, setLocalValue] = useState(value);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleChange = (event: any) => {
    const newVal = event.target.value;
    setLocalValue(newVal);
    // Push to parent after a slight delay to prevent input cursor jumping/jitter
    setTimeout(() => {
      onChange(newVal);
    }, 100);
  };

  return (
    <>
      <div style={{ marginBottom: '20px', paddingBottom: '20px', borderBottom: '1px solid #3a5f8f' }}>
        <QRImportBlock helpTopicQr={helpTopic} />
      </div>

      <TextField
        label="Paste a subscription link"
        description="Paste or edit your VLESS link. We validate the link before saving."
        value={localValue}
        onChange={handleChange}
        disabled={isSaving}
        bShowClearAction
        inlineControls={
          helpTopic ? <HelpPopover label="Help: VLESS link" topic={helpTopic} /> : undefined
        }
      />

      {error && (
        <Field
          label="Import Error"
          description={<span style={{ color: '#ff6b6b' }}>{error}</span>}
        />
      )}

      {successMessage && (
        <Field
          label="Success"
          description={<span style={{ color: '#6bff6b' }}>{successMessage}</span>}
        />
      )}

      <ButtonItem
        layout="below"
        onClick={onSave}
        disabled={isSaving || !value.trim()}
      >
        {labelText}
      </ButtonItem>
    </>
  );
};
