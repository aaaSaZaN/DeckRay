import { FC, useEffect, useState } from 'react';
import { listXrayVersions, downloadXrayVersion, getXrayVersion } from '../services/api';
import { showModal, ConfirmModal, Field, ButtonItem, PanelSectionRow, TextField } from '@decky/ui';

export const XrayVersionSelector: FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<string>('');
  const [installedVersion, setInstalledVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshInstalled = async () => {
    try {
      const res = await getXrayVersion();
      if (res && res.success) {
        setInstalledVersion(res.installed || null);
      }
    } catch (e) {
      console.warn('DeckRay: Failed to fetch installed Xray version', e);
    }
  };

  useEffect(() => {
    const fetchLatestVersion = async () => {
      setIsLoading(true);
      try {
        const res = await listXrayVersions(1); // Fetch just the latest
        if (res.success && res.releases && res.releases.length > 0) {
          setSelectedVersion(res.releases[0].tag);
        } else {
          setError(res.error || 'Failed to fetch latest version');
        }
      } catch (e) {
        setError(String(e));
      }
      setIsLoading(false);
    };
    void fetchLatestVersion();
    void refreshInstalled();
  }, []);

  const handleDownload = async () => {
    const versionToInstall = selectedVersion.trim();
    if (!versionToInstall) return;
    
    showModal(
      <ConfirmModal
        strTitle={`Install Xray ${versionToInstall}`}
        strDescription={`Are you sure you want to download and install Xray Core version ${versionToInstall}? This will stop any active connection.`}
        onOK={async () => {
          setIsDownloading(true);
          setError(null);
          try {
            const res = await downloadXrayVersion(versionToInstall);
            if (!res.success) {
              setError(res.error || 'Failed to download version');
            } else {
              await refreshInstalled();
              showModal(
                <ConfirmModal
                  strTitle="Success"
                  strDescription={`Xray Core ${versionToInstall} was successfully installed and is now active.`}
                  bDestructiveWarning={false}
                />
              );
            }
          } catch (e) {
            setError(String(e));
          }
          setIsDownloading(false);
        }}
      />
    );
  };

  if (isLoading) {
    return <Field label="Xray Core Version" description="Loading latest version..." />;
  }

  return (
    <>
      <Field
        label="Installed Xray Version"
        description={installedVersion || 'Not installed'}
      />

      <PanelSectionRow>
        {isDownloading ? (
          <Field label="Xray Version">
            <div style={{ color: '#8f98a0', fontSize: '14px', paddingTop: '10px' }}>
              Downloading {selectedVersion}...
            </div>
          </Field>
        ) : (
          <Field label="Xray Version">
            <div style={{ padding: '6px 0', display: 'flex', flexDirection: 'column' }}>
              <TextField
                value={selectedVersion}
                onChange={(e: any) => setSelectedVersion(e.target ? e.target.value : e)}
              />
              <span style={{ fontSize: '12px', color: '#8f98a0', marginTop: '4px' }}>
                Enter a version tag (e.g. 26.3.27 or v26.3.27). Pre-filled with latest available.
              </span>
            </div>
          </Field>
        )}
      </PanelSectionRow>
      
      {!isDownloading && selectedVersion.trim() !== '' && (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={handleDownload}
            disabled={isDownloading || !selectedVersion.trim()}
          >
            {installedVersion === selectedVersion.trim() || installedVersion === `v${selectedVersion.trim()}`
              ? 'Reinstall selected version' 
              : 'Install selected version'}
          </ButtonItem>
        </PanelSectionRow>
      )}

      {error && (
        <Field label="Error" description={<span style={{ color: '#ff6b6b' }}>{error}</span>} />
      )}
    </>
  );
};
