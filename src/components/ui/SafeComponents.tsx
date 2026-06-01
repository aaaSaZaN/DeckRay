import {
  Focusable,
  Field,
  ToggleField,
  ButtonItem,
  DialogButton,
  DialogButtonPrimary,
  TextField,
  PanelSection,
  PanelSectionRow,
} from '@decky/ui';
import { FC } from 'react';

// A helper to safely render Focusable
export const SafeFocusable: FC<any> = (props) => {
  if (!Focusable) {
    console.warn('DeckRay: Focusable is undefined in @decky/ui!');
    return (
      <div 
        onClick={props.onClick} 
        style={{ ...(props.style || {}), cursor: 'pointer' }}
        className={props.className}
      >
        {props.children}
      </div>
    );
  }
  // @ts-ignore
  const className = `deckray-focusable ${props.className || ''}`;
  return <Focusable onActivate={props.onClick || props.onActivate} {...props} className={className} />;
};

// A helper for Field
export const SafeField: FC<any> = (props) => {
  if (!Field) {
    console.warn('DeckRay: Field is undefined in @decky/ui!');
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', background: '#1b2a3a', borderRadius: '4px', marginBottom: '8px' }}>
        <div>
          <div style={{ fontWeight: 'bold', color: '#c7d5e0' }}>{props.label}</div>
          {props.description && <div style={{ fontSize: '12px', color: '#8f98a0', marginTop: '4px' }}>{props.description}</div>}
        </div>
        {props.children && <div>{props.children}</div>}
      </div>
    );
  }
  // @ts-ignore
  return <Field {...props} />;
};

// A helper for ToggleField
export const SafeToggleField: FC<any> = (props) => {
  if (!ToggleField) {
    console.warn('DeckRay: ToggleField is undefined in @decky/ui!');
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', background: '#1b2a3a', borderRadius: '4px', marginBottom: '8px' }}>
        <div>
          <div style={{ fontWeight: 'bold', color: '#c7d5e0' }}>{props.label}</div>
          {props.description && <div style={{ fontSize: '12px', color: '#8f98a0', marginTop: '4px' }}>{props.description}</div>}
        </div>
        <input 
          type="checkbox" 
          checked={props.checked} 
          onChange={(e: any) => props.onChange?.(e.target.checked)}
          disabled={props.disabled}
          style={{ width: '20px', height: '20px' }}
        />
      </div>
    );
  }
  // @ts-ignore
  return <ToggleField {...props} />;
};

// A helper for ButtonItem
export const SafeButtonItem: FC<any> = (props) => {
  if (!ButtonItem) {
    console.warn('DeckRay: ButtonItem is undefined in @decky/ui!');
    return (
      <button 
        onClick={props.onClick}
        disabled={props.disabled}
        style={{ width: '100%', padding: '10px', background: '#3a5f8f', color: '#fff', border: 'none', borderRadius: '4px', cursor: props.disabled ? 'not-allowed' : 'pointer', opacity: props.disabled ? 0.5 : 1, marginBottom: '8px' }}
      >
        {props.children || props.label || 'Button'}
      </button>
    );
  }
  // @ts-ignore
  return <ButtonItem {...props} />;
};

// A helper for DialogButton
export const SafeDialogButton: FC<any> = (props) => {
  if (!DialogButton) {
    return (
      <button onClick={props.onClick} disabled={props.disabled} style={props.style}>
        {props.children}
      </button>
    );
  }
  // @ts-ignore
  return <DialogButton {...props} />;
};

// A helper for DialogButtonPrimary
export const SafeDialogButtonPrimary: FC<any> = (props) => {
  if (!DialogButtonPrimary) {
    return (
      <button onClick={props.onClick} disabled={props.disabled} style={props.style}>
        {props.children}
      </button>
    );
  }
  // @ts-ignore
  return <DialogButtonPrimary {...props} />;
};

// A helper for TextField
export const SafeTextField: FC<any> = (props) => {
  if (!TextField) {
    console.warn('DeckRay: TextField is undefined in @decky/ui!');
    return (
      <div style={{ padding: '10px', background: '#1b2a3a', borderRadius: '4px', marginBottom: '8px' }}>
        <div style={{ fontWeight: 'bold', color: '#c7d5e0', marginBottom: '4px' }}>{props.label}</div>
        <input 
          type="text" 
          value={props.value} 
          onChange={props.onChange}
          disabled={props.disabled}
          style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
        />
        {props.description && <div style={{ fontSize: '12px', color: '#8f98a0', marginTop: '4px' }}>{props.description}</div>}
      </div>
    );
  }
  // @ts-ignore
  return <TextField {...props} />;
};

// A helper for PanelSection
export const SafePanelSection: FC<any> = (props) => {
  if (!PanelSection) {
    console.warn('DeckRay: PanelSection is undefined in @decky/ui!');
    return (
      <div style={{ padding: '0px', marginBottom: '10px' }}>
        {props.title && <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#c7d5e0', marginBottom: '8px', textTransform: 'uppercase' }}>{props.title}</div>}
        {props.children}
      </div>
    );
  }
  // @ts-ignore
  return <PanelSection {...props} />;
};

// A helper for PanelSectionRow
export const SafePanelSectionRow: FC<any> = (props) => {
  if (!PanelSectionRow) {
    console.warn('DeckRay: PanelSectionRow is undefined in @decky/ui!');
    return <div style={{ marginBottom: '8px' }}>{props.children}</div>;
  }
  // @ts-ignore
  return <PanelSectionRow {...props} />;
};

