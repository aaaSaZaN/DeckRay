import { FC, useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Field } from '@decky/ui';
import { getImportServerUrl, ImportServerUrlResponse } from '../services/api';
import { HelpPopover } from './ui/HelpPopover';
import type { HelpTopic } from '../types/ui';

interface QRImportBlockProps {
  helpTopicQr?: HelpTopic;
  helpTopicLan?: HelpTopic;
}

export const QRImportBlock: FC<QRImportBlockProps> = ({ helpTopicQr, helpTopicLan }) => {
  const [urlInfo, setUrlInfo] = useState<ImportServerUrlResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchUrl = async () => {
      try {
        const res = await getImportServerUrl();
        if (!cancelled) {
          setUrlInfo(res);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const errMsg = err instanceof Error ? err.message : String(err);
          setError(errMsg);
          setUrlInfo(null);
        }
      }
    };

    fetchUrl();

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <Field
        label="Import via QR"
        description={<span style={{ color: '#ff6b6b' }}>{error}</span>}
      />
    );
  }

  if (!urlInfo) {
    return (
      <Field
        label="Import via QR"
        description="Loading import address…"
      />
    );
  }

  const importUrl = urlInfo.baseUrl.replace(/\/$/, '') + urlInfo.path;

  return (
    <>
      <Field
        label={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Import via QR</span>
            {helpTopicQr && <HelpPopover label="Help: QR import" topic={helpTopicQr} />}
          </div>
        }
        description="Scan with your phone or open the link below to import your VLESS configuration."
      >
        <div style={{ padding: '8px', backgroundColor: '#fff', borderRadius: '4px', display: 'inline-block' }}>
          <QRCodeSVG value={importUrl} size={128} />
        </div>
      </Field>

      <Field
        label={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Import URL</span>
            {helpTopicLan && <HelpPopover label="Help: LAN address" topic={helpTopicLan} />}
          </div>
        }
        description={
          <span style={{ color: '#66c0f4', wordBreak: 'break-all', fontFamily: 'monospace' }}>
            {importUrl}
          </span>
        }
      />
    </>
  );
};
