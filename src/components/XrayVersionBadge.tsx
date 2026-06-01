import { FC, useEffect, useState } from 'react';
import { Field } from '@decky/ui';
import { getXrayVersion } from '../services/api';

export const XrayVersionBadge: FC = () => {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchVer = async () => {
      try {
        const res = await getXrayVersion();
        if (!cancelled && res.success) {
          setVersion(res.installed || 'Not installed');
        } else if (!cancelled) {
          setVersion('Error');
        }
      } catch (e) {
        if (!cancelled) setVersion('Error');
      }
    };
    fetchVer();
    return () => { cancelled = true; };
  }, []);

  if (!version) return null;

  return (
    <Field
      label="Xray Core"
      description={
        <span style={{ 
          backgroundColor: '#3a5f8f', 
          color: '#fff', 
          padding: '2px 6px', 
          borderRadius: '4px', 
          fontSize: '12px',
          fontWeight: 'bold',
          display: 'inline-block'
        }}>
          {version}
        </span>
      }
    />
  );
};
