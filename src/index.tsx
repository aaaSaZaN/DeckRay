import { definePlugin } from '@decky/api';
import { Component, ErrorInfo, ReactNode, Suspense, useEffect, useState } from 'react';
import { ConfiguredLayout } from './components/layouts/ConfiguredLayout';
import { SetupLayout } from './components/layouts/SetupLayout';
import { usePluginPanelState } from './hooks/usePluginPanelState';

interface ErrorBoundaryProps {
  children?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class SafeErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('DeckRay UI Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '15px', color: '#ff6b6b', backgroundColor: '#3a1e1e', borderRadius: '6px' }}>
          <h4>An error occurred in the UI</h4>
          <pre style={{ fontSize: '11px', whiteSpace: 'pre-wrap', marginTop: '10px' }}>
            {this.state.error?.toString()}
          </pre>
          <div style={{ fontSize: '12px', marginTop: '10px' }}>
            *Try updating the plugin or Decky Loader if you are on Steam Beta.*
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const PluginIcon = () => (
  <svg viewBox="0 0 640 512" width="1em" height="1em" fill="currentColor">
    <path d="M640 264v-16c0-8.84-7.16-16-16-16H344v-40h72c17.67 0 32-14.33 32-32V32c0-17.67-14.33-32-32-32H224c-17.67 0-32 14.33-32 32v128c0 17.67 14.33 32 32 32h72v40H16c-8.84 0-16 7.16-16 16v16c0 8.84 7.16 16 16 16h104v40H64c-17.67 0-32 14.33-32 32v128c0 17.67 14.33 32 32 32h160c17.67 0 32-14.33 32-32V352c0-17.67-14.33-32-32-32h-56v-40h304v40h-56c-17.67 0-32 14.33-32 32v128c0 17.67 14.33 32 32 32h160c17.67 0 32-14.33 32-32V352c0-17.67-14.33-32-32-32h-56v-40h104c8.84 0 16-7.16 16-16zM256 128V64h128v64H256zm-64 320H96v-64h96v64zm352 0h-96v-64h96v64z" />
  </svg>
);

function Content() {
  const {
    layout,
    configSummary,
    connection,
    options,
    configs,
    subscriptions,
    activeConfigId,
    isLoading,
    saveConfig,
    resetConfig,
    toggleConnection,
    toggleTUNMode,
    toggleKillSwitch,
    deactivateKillSwitch,
    checkTUNPrivileges,
    setActiveConfig,
    deleteConfig,
    deleteSubscription,
    updateSubscription,
  } = usePluginPanelState();

  const [vlessUrl, setVlessUrl] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('main');

  useEffect(() => {
    if (layout === 'setup') {
      setSaveError(null);
      setSaveSuccess(null);
      setVlessUrl('');
    }
  }, [layout]);

  // Inject global focus styles for D-pad navigation
  useEffect(() => {
    const styleId = 'deckray-focus-styles';
    if (document.getElementById(styleId)) return;
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .deckray-config-row:focus,
      .deckray-config-row.gpfocus {
        border-color: #ffffff !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 0 0 2px #ffffff !important;
      }
      .deckray-profile-row:focus,
      .deckray-profile-row.gpfocus {
        border-color: #ffffff !important;
        box-shadow: 0 0 0 2px #ffffff !important;
      }
      .deckray-focusable.gpfocus,
      .deckray-focusable.gpfocuswithin {
        outline: 2px solid #ffffff !important;
        outline-offset: -2px;
        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.4) !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      const el = document.getElementById(styleId);
      if (el) el.remove();
    };
  }, []);

  const handleSave = async () => {
    setSaveError(null);
    setSaveSuccess(null);
    setIsSaving(true);
    try {
      const result = await saveConfig(vlessUrl);
      if (result.success) {
        setSaveSuccess('Configuration saved');
        setTimeout(() => setSaveSuccess(null), 3000);
      } else {
        setSaveError(result.error || 'Failed to save configuration');
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading && layout === 'setup') {
    return <div style={{ padding: '10px', color: '#8f98a0' }}>Loading…</div>;
  }

  return (
    <>
      {layout === 'setup' ? (
        <SetupLayout
          vlessUrl={vlessUrl}
          onVlessUrlChange={setVlessUrl}
          onSave={handleSave}
          isSaving={isSaving}
          error={saveError}
          successMessage={saveSuccess}
        />
      ) : (
        <ConfiguredLayout
          configSummary={configSummary}
          connection={connection}
          options={options}
          configs={configs}
          subscriptions={subscriptions}
          activeConfigId={activeConfigId}
          onSetActiveConfig={setActiveConfig}
          onDeleteConfig={deleteConfig}
          onDeleteSubscription={deleteSubscription}
          onUpdateSubscription={updateSubscription}
          onAddProvider={saveConfig}
          onToggleConnection={toggleConnection}
          onToggleTUNMode={toggleTUNMode}
          onCheckTUNPrivileges={checkTUNPrivileges}
          onToggleKillSwitch={toggleKillSwitch}
          onDeactivateKillSwitch={deactivateKillSwitch}
          onResetConfig={resetConfig}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />
      )}
    </>
  );
}

export default definePlugin(() => {
  try {
    console.log('Xray Decky plugin initializing...');

    const pluginObj = {
      name: 'DeckRay',
      content: window.SP_REACT.createElement(
        SafeErrorBoundary, 
        null,
        window.SP_REACT.createElement(
          Suspense, 
          { fallback: window.SP_REACT.createElement('div', { style: { padding: '15px' } }, 'Loading UI chunks...') },
          window.SP_REACT.createElement(Content, null)
        )
      ),
      icon: window.SP_REACT.createElement(PluginIcon, null),
      onDismount() {
        console.log('DeckRay plugin unloading');
      },
    };

    console.log('DeckRay plugin object constructed successfully:', pluginObj);
    return pluginObj;
  } catch (err) {
    console.error('CRITICAL DECKRAY LOAD ERROR:', err);
    throw err;
  }
});
