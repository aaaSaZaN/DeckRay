import { FC, useState, useEffect } from 'react';
import { showModal, ModalRoot, Field, ButtonItem, DialogButton, Focusable, PanelSectionRow } from '@decky/ui';
import { MenuSelector } from './MenuSelector';
import { getXrayLogs, clearXrayLogs, setLogLevel, getLogLevel } from '../services/api';

const LOG_LEVELS = [
  { label: 'Debug', data: 'debug' },
  { label: 'Info', data: 'info' },
  { label: 'Warning', data: 'warning' },
  { label: 'Error', data: 'error' },
  { label: 'None', data: 'none' },
];

const LOG_LINES_OPTIONS = [
  { label: '50', data: 50 },
  { label: '100', data: 100 },
  { label: '300', data: 300 },
  { label: '1000', data: 1000 },
];

const LogModal: FC<{ closeModal?: () => void }> = ({ closeModal }) => {
  const [logs, setLogs] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [linesLimit, setLinesLimit] = useState<number>(300);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await getXrayLogs(linesLimit);
      if (res.success && res.logs) {
        setLogs(res.logs.join('\n'));
      } else {
        setLogs(res.error || 'Failed to fetch logs');
      }
    } catch (e) {
      setLogs(`Exception: ${e}`);
    }
    setLoading(false);
  };

  const handleClear = async () => {
    await clearXrayLogs();
    setLogs('');
  };

  useEffect(() => {
    fetchLogs();
  }, [linesLimit]);

  return (
    <ModalRoot onCancel={closeModal}>
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '10px', height: '80vh', boxSizing: 'border-box' }}>
        <h3 style={{ margin: 0, color: 'white' }}>Xray Logs</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', color: '#8f98a0' }}>Lines:</span>
          <MenuSelector
            label="Log Lines"
            value={linesLimit}
            options={LOG_LINES_OPTIONS as any[]}
            onChange={(opt: any) => setLinesLimit(opt as number)}
          />
        </div>
        
        <Focusable
          style={{
            backgroundColor: '#1b2838',
            padding: '8px',
            borderRadius: '4px',
            flex: 1,
            overflowY: 'auto',
            fontFamily: 'monospace',
            fontSize: '11px',
            color: '#c7d5e0',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {logs || 'No logs available.'}
        </Focusable>
        
        <Focusable
          {...{ 'flow-children': 'right' }}
          style={{ display: 'flex', gap: '8px', marginTop: '10px', justifyContent: 'flex-end' }}
        >
          <DialogButton onClick={fetchLogs} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </DialogButton>
          <DialogButton onClick={handleClear}>
            Clear
          </DialogButton>
          <DialogButton onClick={closeModal}>
            Close
          </DialogButton>
        </Focusable>
      </div>
    </ModalRoot>
  );
};

export const LogViewer: FC = () => {
  const [level, setLevel] = useState<string>('warning');

  useEffect(() => {
    getLogLevel().then(res => {
      if (res && res.logLevel) {
        setLevel(res.logLevel);
      }
    }).catch(console.error);
  }, []);

  const handleLevelChange = async (newLevel: string) => {
    setLevel(newLevel);
    await setLogLevel(newLevel);
  };

  return (
    <>
      <PanelSectionRow>
        <MenuSelector
          label="Log Level"
          value={level}
          options={LOG_LEVELS as any[]}
          onChange={(opt: any) => handleLevelChange(opt as string)}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            showModal(<LogModal />);
          }}
        >
          View Logs
        </ButtonItem>
      </PanelSectionRow>
    </>
  );
};
