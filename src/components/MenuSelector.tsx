import { FC, useState } from 'react';
import { Field, Focusable } from '@decky/ui';

interface Option {
  label: string;
  data: string | number;
}

interface MenuSelectorProps {
  label: string;
  value: string | number;
  options: Option[];
  onChange: (data: any) => void;
  disabled?: boolean;
}

/**
 * An inline, QAM-safe dropdown selector.
 * 
 * Expands directly below the field instead of using showContextMenu,
 * ensuring that focus stays completely inside the plugin panel and
 * never causes the panel to close or switch tabs.
 */
export const MenuSelector: FC<MenuSelectorProps> = ({
  label,
  value,
  options,
  onChange,
  disabled,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const currentLabel = options.find((o) => o.data === value)?.label ?? String(value);

  const toggleOpen = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', marginBottom: isOpen ? '8px' : '0' }}>
      <Field label={label}>
        <Focusable
          onClick={toggleOpen}
          onActivate={toggleOpen}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '6px',
            padding: '6px 10px',
            backgroundColor: disabled ? '#1a2530' : (isOpen ? '#3a4a58' : '#2c3b48'),
            border: '1px solid',
            borderColor: isFocused ? '#ffffff' : '#3a4a58',
            borderRadius: '4px',
            color: disabled ? '#5a6370' : '#c7d5e0',
            cursor: disabled ? 'default' : 'pointer',
            minWidth: '120px',
            opacity: disabled ? 0.5 : 1,
            outline: 'none',
            boxShadow: isFocused ? '0 0 0 2px rgba(255, 255, 255, 0.4)' : 'none',
          }}
        >
          <span style={{ fontSize: '13px', flex: 1, textAlign: 'right' }}>{currentLabel}</span>
          <span style={{ fontSize: '10px', color: '#8f98a0', transition: 'transform 0.2s', transform: isOpen ? 'rotate(180deg)' : 'none' }}>▼</span>
        </Focusable>
      </Field>

      {isOpen && !disabled && (
        <div style={{
          marginTop: '4px',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#1b2838',
          border: '1px solid #3a4a58',
          borderRadius: '4px',
          padding: '4px',
          gap: '2px',
        }}>
          {options.map((opt) => {
            const isSelected = opt.data === value;
            return (
              <FocusableRow
                key={String(opt.data)}
                isSelected={isSelected}
                onClick={() => {
                  onChange(opt.data);
                  setIsOpen(false);
                }}
              >
                {isSelected ? `✓ ${opt.label}` : opt.label}
              </FocusableRow>
            );
          })}
        </div>
      )}
    </div>
  );
};

const FocusableRow: FC<{ isSelected: boolean; onClick: () => void; children: React.ReactNode }> = ({ isSelected, onClick, children }) => {
  const [rowFocused, setRowFocused] = useState(false);
  return (
    <Focusable
      onClick={onClick}
      onActivate={onClick}
      onFocus={() => setRowFocused(true)}
      onBlur={() => setRowFocused(false)}
      style={{
        padding: '8px 12px',
        borderRadius: '3px',
        backgroundColor: isSelected ? 'rgba(87, 203, 112, 0.15)' : (rowFocused ? 'rgba(255,255,255,0.1)' : 'transparent'),
        color: isSelected ? '#57cb70' : '#c7d5e0',
        outline: rowFocused ? '2px solid #ffffff' : 'none',
        outlineOffset: '-2px',
        cursor: 'pointer',
        fontSize: '13px',
      }}
    >
      {children}
    </Focusable>
  );
};
