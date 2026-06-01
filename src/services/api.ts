/**
 * API Service - Backend calls using @decky/api (new API)
 *
 * Uses callable() for typed backend method calls.
 * https://wiki.deckbrew.xyz/en/plugin-dev/backend-frontend-communication
 */

import { callable } from '@decky/api';

// Type definitions
export interface VLESSConfig {
  sourceUrl: string;
  configType: 'single' | 'subscription';
  uuid: string;
  address: string;
  port: number;
  flow?: string;
  encryption?: string;
  network?: string;
  security?: string;
  realityConfig?: {
    publicKey: string;
    shortId: string;
    serverName: string;
    fingerprint?: string;
  };
  name?: string;
  importedAt: number;
  lastValidatedAt?: number;
  isValid: boolean;
  validationError?: string;
  sub_id?: string;
  id?: string;
  protocol?: string;
  nativeConfig?: any;
}

export interface Subscription {
  id: string;
  url: string;
  custom_headers?: string;
  title: string;
  announce?: string;
  update_interval: number;
  last_updated: number;
}

export interface ImportConfigResponse {
  success: boolean;
  config?: VLESSConfig;
  error?: string;
}

export interface ResetConfigResponse {
  success: boolean;
  error?: string;
}

export interface GetConfigResponse {
  config?: VLESSConfig;
  exists: boolean;
}

export interface GetAllConfigsResponse {
  success: boolean;
  configs?: VLESSConfig[];
  subscriptions?: Subscription[];
  activeConfigId?: string;
  error?: string;
}

export interface DeleteResponse {
  success: boolean;
  error?: string;
}

export interface ValidateConfigResponse {
  isValid: boolean;
  error?: string;
}

export interface PingResponse {
  success: boolean;
  latencyMs?: number | null;
  error?: string;
}

export interface TrafficStatsResponse {
  success: boolean;
  uplink?: number;
  downlink?: number;
  error?: string;
}

export interface UpdateSubscriptionResponse {
  success: boolean;
  updatedNodes?: number;
  error?: string;
}

export interface XrayRelease {
  tag: string;
  name: string;
  date: string;
  url: string;
  prerelease?: boolean;
}

export interface ListVersionsResponse {
  success: boolean;
  releases?: XrayRelease[];
  error?: string;
}

export interface DownloadVersionResponse {
  success: boolean;
  version?: string;
  installedVersion?: string;
  assetSize?: number;
  error?: string;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'blocked';

export interface ConnectionStatusResponse {
  status: ConnectionStatus;
  connectedAt?: number;
  errorMessage?: string;
  processId?: number;
  uptime?: number;
}

export interface ToggleConnectionResponse {
  success: boolean;
  status: ConnectionStatus;
  error?: string;
  processId?: number;
}

export interface ToggleTUNModeResponse {
  success: boolean;
  enabled: boolean;
  hasPrivileges: boolean;
  error?: string;
}

export interface CheckPrivilegesResponse {
  hasPrivileges: boolean;
  error?: string;
}

export interface TUNModeStatusResponse {
  enabled: boolean;
  hasPrivileges: boolean;
  tunInterface?: string;
  isActive: boolean;
}

export interface ToggleKillSwitchResponse {
  success: boolean;
  enabled: boolean;
}

export interface KillSwitchStatusResponse {
  enabled: boolean;
  isActive: boolean;
  activatedAt?: number;
}

export interface DeactivateKillSwitchResponse {
  success: boolean;
  error?: string;
}

export interface ToggleSystemProxyResponse {
  success: boolean;
  enabled: boolean;
  error?: string;
  socksPort?: number | null;
  httpPort?: number | null;
}

export interface SystemProxyStatusResponse {
  enabled: boolean;
  isActive: boolean;
  socksPort?: number | null;
  httpPort?: number | null;
  address?: string | null;
  error?: string;
}

export interface ImportServerUrlResponse {
  baseUrl: string;
  path: string;
}

// Backend method handles using callable (new API)
// callable<[arg types], returnType>("method_name")

export const importVLESSConfig = callable<[url: string], ImportConfigResponse>(
  'import_vless_config'
);

export const getVLESSConfig = callable<[], GetConfigResponse>('get_vless_config');

export const getAllConfigs = callable<[], GetAllConfigsResponse>('get_all_configs');

export const setActiveConfig = callable<[config_id: string], { success: boolean; error?: string }>(
  'set_active_config'
);

export const deleteConfig = callable<[config_id: string], DeleteResponse>('delete_config');

export const deleteSubscription = callable<[sub_id: string], DeleteResponse>('delete_subscription');

export const resetVLESSConfig = callable<[], ResetConfigResponse>('reset_vless_config');

export const validateVLESSConfig = callable<[], ValidateConfigResponse>('validate_vless_config');

export const toggleConnection = callable<[enable: boolean], ToggleConnectionResponse>(
  'toggle_connection'
);

export const getConnectionStatus = callable<[], ConnectionStatusResponse>('get_connection_status');

export const toggleTUNMode = callable<[enabled: boolean], ToggleTUNModeResponse>('toggle_tun_mode');

export const checkTUNPrivileges = callable<[], CheckPrivilegesResponse>('check_tun_privileges');

export const getTUNModeStatus = callable<[], TUNModeStatusResponse>('get_tun_mode_status');

export const toggleKillSwitch = callable<[enabled: boolean], ToggleKillSwitchResponse>(
  'toggle_kill_switch'
);

export const getKillSwitchStatus = callable<[], KillSwitchStatusResponse>('get_kill_switch_status');

export const deactivateKillSwitch = callable<[], DeactivateKillSwitchResponse>(
  'deactivate_kill_switch'
);

export const toggleSystemProxy = callable<[enabled: boolean], ToggleSystemProxyResponse>(
  'toggle_system_proxy'
);

export const getSystemProxyStatus = callable<[], SystemProxyStatusResponse>(
  'get_system_proxy_status'
);

export const getImportServerUrl = callable<[], ImportServerUrlResponse>('get_import_server_url');

export const pingHost = callable<[host: string, method?: string], PingResponse>('ping_host');

export const getTrafficStats = callable<[], TrafficStatsResponse>('get_traffic_stats');

export const updateSubscription = callable<[sub_id: string], UpdateSubscriptionResponse>('update_subscription');

export const listXrayVersions = callable<[limit?: number], ListVersionsResponse>('list_xray_versions');

export const downloadXrayVersion = callable<[tag: string], { success: boolean; error?: string }>('download_xray_version');

export const setLogLevel = callable<[level: string], { success: boolean; error?: string }>('set_xray_log_level');
export const getLogLevel = callable<[], { logLevel: string }>('get_xray_log_level');

export const getXrayLogs = callable<[limit: number], { success: boolean; logs?: string[]; error?: string }>('get_xray_logs');

export const clearXrayLogs = callable<[], { success: boolean; error?: string }>('clear_xray_logs');

export const getXrayVersion = callable<[], { success: boolean; installed?: string | null; error?: string }>('get_xray_version');

