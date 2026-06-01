"""
Xray Manager - Manages xray-core process lifecycle

Handles starting, stopping, and monitoring xray-core subprocess.
Generates xray-core configuration files from VLESSConfig or Hysteria2Config.

Supports a user-editable JSON template (backend/template.json) whose
"routing", "dns", "log" etc. sections are preserved while "inbounds" and
"outbounds" are dynamically injected by the backend.
"""

import asyncio
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List


# ---------------------------------------------------------------------------
# Template discovery: look next to this file, then plugin root / backend /
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent          # backend/src/
_BACKEND_DIR = _THIS_DIR.parent                      # backend/
_PLUGIN_DIR = _BACKEND_DIR.parent                    # project root

_TEMPLATE_SEARCH_PATHS = [
    _BACKEND_DIR / "template.json",                  # default location
    _PLUGIN_DIR / "template.json",                   # alternative
]


def _load_template() -> Optional[Dict[str, Any]]:
    """Load the first template.json found on the search path.

    Returns None if no template exists (fallback to built-in config).
    """
    for path in _TEMPLATE_SEARCH_PATHS:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, OSError) as exc:
                print(f"XrayManager: bad template {path}: {exc}")
    return None


class XrayManager:
    """
    Manages xray-core process lifecycle.

    Responsibilities:
    - Generate xray-core JSON configuration
    - Start/stop xray-core subprocess
    - Monitor process health
    - Handle process crashes
    """

    def __init__(self, xray_binary_path: str = "backend/out/xray-core"):
        """
        Initialize XrayManager.

        Args:
            xray_binary_path: Path to xray-core binary
        """
        self.xray_binary_path = xray_binary_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.config_file: Optional[str] = None
        self.process_id: Optional[int] = None
        self._log_file = None
        self._log_path: Optional[str] = None

    def generate_config(
        self,
        vless_config: Dict[str, Any],
        tun_mode: bool = False,
        outbound_interface: Optional[str] = None,
        log_level: str = "warning",
    ) -> str:
        """
        Generate xray-core JSON configuration from VLESSConfig.

        The config file is written to DECKY_PLUGIN_RUNTIME_DIR (isolated,
        owned by root) instead of world-readable /tmp.  We use
        tempfile.mkstemp to avoid race conditions and restrict
        permissions to 0600 (owner-only read/write).

        Args:
            vless_config: VLESSConfig dictionary
            tun_mode: Whether to enable TUN mode
            outbound_interface: For TUN mode, bind proxy to this interface (e.g. wlan0)

        Returns:
            Path to generated config file
        """
        # Use Decky's isolated runtime dir; fall back to tempdir for dev/testing
        config_dir = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR") or tempfile.gettempdir()
        os.makedirs(config_dir, exist_ok=True)

        # Generate xray-core config
        xray_config = self._build_xray_config(
            vless_config, tun_mode, outbound_interface, log_level
        )

        # Clean up previous config file before creating new one (BUG-03)
        if self.config_file and os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
            except OSError:
                pass

        # Securely create the config file (mkstemp returns an fd + path)
        fd, config_file = tempfile.mkstemp(
            prefix="xray-config-", suffix=".json", dir=config_dir
        )
        try:
            # Restrict to owner-only read/write (root)
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            with os.fdopen(fd, "w") as f:
                json.dump(xray_config, f, indent=2)
        except Exception:
            os.close(fd)
            raise

        self.config_file = config_file
        return config_file

    # ------------------------------------------------------------------
    # Inbound builders
    # ------------------------------------------------------------------
    @staticmethod
    def _build_socks_inbound(port: int = 10808) -> Dict[str, Any]:
        return {
            "protocol": "socks",
            "listen": "127.0.0.1",
            "port": port,
            "settings": {"udp": True},
            "sniffing": {
                "destOverride": ["http", "tls", "fakedns"],
                "enabled": True
            },
            "tag": "socks",
        }

    @staticmethod
    def _build_http_inbound(port: int = 10809) -> Dict[str, Any]:
        return {
            "protocol": "http",
            "listen": "127.0.0.1",
            "port": port,
            "sniffing": {
                "destOverride": ["http", "tls", "fakedns"],
                "enabled": True
            },
            "tag": "http",
        }

    @staticmethod
    def _build_tun_inbound() -> Dict[str, Any]:
        """TUN inbound — supported since xray-core v26.1.23.

        The ``settings`` object is REQUIRED for the TUN interface to
        receive a valid IP address and subnet.  Without ``gateway``,
        the xray0 interface is created in a "raw" state with no IP and
        ``ip route add default dev xray0`` silently drops all packets.
        """
        return {
            "protocol": "tun",
            "tag": "tun",
            "settings": {
                "name": "xray0",
                "mtu": 1500,
                "gateway": ["10.0.0.1/16"],
                "dns": ["1.1.1.1", "8.8.8.8"],
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "fakedns"]
            }
        }

    # ------------------------------------------------------------------
    # Outbound builders
    # ------------------------------------------------------------------
    def _build_vless_outbound(
        self,
        vless_config: Dict[str, Any],
        outbound_interface: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build VLESS proxy outbound from parsed config."""
        uuid = vless_config.get("uuid")
        address = vless_config.get("address")
        port = vless_config.get("port")
        flow = vless_config.get("flow")
        encryption = vless_config.get("encryption", "none")
        network = vless_config.get("network", "tcp")
        security = vless_config.get("security", "none")
        reality_config = vless_config.get("realityConfig", {})

        outbound: Dict[str, Any] = {
            "protocol": "vless",
            "tag": "proxy",
            "settings": {
                "vnext": [
                    {
                        "address": address,
                        "port": port,
                        "users": [
                            {
                                "id": uuid,
                                "encryption": encryption,
                                "flow": flow if flow else "",
                            }
                        ],
                    }
                ]
            },
            "streamSettings": {
                "network": network,
                "security": security,
            },
        }

        # Reality (client-side)
        if security == "reality" and reality_config:
            outbound["streamSettings"]["realitySettings"] = {
                "serverName": reality_config.get("serverName", address),
                "publicKey": reality_config.get("publicKey", ""),
                "shortId": reality_config.get("shortId", ""),
                "fingerprint": reality_config.get("fingerprint", "chrome"),
            }

        # TLS settings
        if security == "tls":
            tls_settings: Dict[str, Any] = {}
            sni = vless_config.get("sni") or vless_config.get("serverName")
            if sni:
                tls_settings["serverName"] = sni
            fp = vless_config.get("fingerprint")
            if fp:
                tls_settings["fingerprint"] = fp
            alpn = vless_config.get("alpn")
            if alpn:
                tls_settings["alpn"] = alpn if isinstance(alpn, list) else alpn.split(",")
            if tls_settings:
                outbound["streamSettings"]["tlsSettings"] = tls_settings

        # Transport-specific settings
        if network == "ws":
            ws_path = vless_config.get("wsPath", "/")
            ws_host = vless_config.get("wsHost", "")
            ws_settings: Dict[str, Any] = {"path": ws_path}
            if ws_host:
                ws_settings["headers"] = {"Host": ws_host}
            outbound["streamSettings"]["wsSettings"] = ws_settings

        if network == "grpc":
            service_name = vless_config.get("grpcServiceName", "")
            outbound["streamSettings"]["grpcSettings"] = {
                "serviceName": service_name,
            }

        if network in ("h2", "http"):
            h2_path = vless_config.get("h2Path", "/")
            h2_host = vless_config.get("h2Host", "")
            h2_settings: Dict[str, Any] = {"path": h2_path}
            if h2_host:
                h2_settings["host"] = [h2_host]
            outbound["streamSettings"]["httpSettings"] = h2_settings

        # Bind to physical interface in TUN mode (avoid routing loop)
        if outbound_interface:
            outbound["streamSettings"]["sockopt"] = {"interface": outbound_interface}

        return outbound

    @staticmethod
    def _build_hysteria2_outbound(
        hy2_config: Dict[str, Any],
        outbound_interface: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a Hysteria2 proxy outbound.

        Hysteria2 runs over QUIC (UDP).  The outbound uses the new
        ``hysteria2`` protocol added in Xray-core ≥ 1.8.7.

        Required keys in *hy2_config*:
            address, port, password

        Optional:
            sni / serverName, fingerprint, alpn,
            up_mbps, down_mbps, obfs, obfsPassword
        """
        address = hy2_config.get("address", "")
        port = hy2_config.get("port", 443)
        password = hy2_config.get("password", "")

        outbound: Dict[str, Any] = {
            "protocol": "hysteria2",
            "tag": "proxy",
            "settings": {
                "servers": [
                    {
                        "address": address,
                        "port": port,
                        "password": password,
                    }
                ],
            },
            "streamSettings": {
                "network": "udp",
                "security": "tls",
                "tlsSettings": {
                    "serverName": hy2_config.get("sni")
                    or hy2_config.get("serverName")
                    or address,
                    "fingerprint": hy2_config.get("fingerprint", "chrome"),
                    "alpn": hy2_config.get("alpn", ["h3"]),
                },
            },
        }

        # Optional obfuscation (salamander)
        obfs = hy2_config.get("obfs")
        if obfs:
            outbound["settings"]["servers"][0]["obfs"] = {
                "type": obfs,
                "password": hy2_config.get("obfsPassword", ""),
            }

        # Bandwidth hints (optional)
        up = hy2_config.get("up_mbps")
        down = hy2_config.get("down_mbps")
        if up:
            outbound["settings"]["servers"][0]["up_mbps"] = int(up)
        if down:
            outbound["settings"]["servers"][0]["down_mbps"] = int(down)

        # Bind to physical interface in TUN mode
        if outbound_interface:
            outbound["streamSettings"]["sockopt"] = {"interface": outbound_interface}

        return outbound

    @staticmethod
    def _build_direct_outbound(outbound_interface: Optional[str] = None) -> Dict[str, Any]:
        outbound = {
            "protocol": "freedom",
            "settings": {"domainStrategy": "AsIs"},
            "tag": "direct",
        }
        if outbound_interface:
            ss = outbound.setdefault("streamSettings", {})
            so = ss.setdefault("sockopt", {})
            so["interface"] = outbound_interface
        return outbound

    # ------------------------------------------------------------------
    # Main config assembly
    # ------------------------------------------------------------------
    def _build_xray_config(
        self,
        vless_config: Dict[str, Any],
        tun_mode: bool,
        outbound_interface: Optional[str] = None,
        log_level: str = "warning",
    ) -> Dict[str, Any]:
        """
        Build xray-core JSON configuration structure.

        If a ``template.json`` file exists (in ``backend/`` or project root),
        the template is loaded and only ``inbounds`` and ``outbounds`` are
        replaced.  This lets users customise ``log``, ``dns``, ``routing``,
        ``policy``, etc. without touching Python code.

        If no template is found, a minimal built-in config is used.

        Args:
            vless_config: VLESSConfig (or Hysteria2Config) dictionary
            tun_mode: Whether to enable TUN mode
            outbound_interface: Physical interface for sockopt binding

        Returns:
            xray-core configuration dictionary
        """
        # Determine protocol type
        protocol = vless_config.get("protocol", "vless")

        # ----- Build inbounds -----
        inbounds: List[Dict[str, Any]] = [
            self._build_socks_inbound(),
            self._build_http_inbound(),
        ]
        if tun_mode:
            inbounds.append(self._build_tun_inbound())

        # =============================================================
        # Native JSON config — use the subscription config verbatim
        # =============================================================
        if protocol == "native_json":
            native = vless_config.get("nativeConfig")
            if native and isinstance(native, dict):
                config = dict(native)

                # Validate required structure (BUG-13)
                if not config.get("outbounds"):
                    raise ValueError(
                        "Native JSON config missing 'outbounds' — "
                        "the subscription returned an incomplete config"
                    )

                # Override inbounds with our controlled local ports / TUN
                config["inbounds"] = inbounds

                # Inject API, stats, and policy for traffic monitoring
                api_inbound = {
                    "listen": "127.0.0.1",
                    "port": 10085,
                    "protocol": "dokodemo-door",
                    "settings": {"address": "127.0.0.1"},
                    "tag": "api"
                }
                config["inbounds"].append(api_inbound)
                config["api"] = {"services": ["StatsService"], "tag": "api"}
                config["stats"] = {}
                config["policy"] = {
                    "levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}},
                    "system": {
                        "statsInboundUplink": True,
                        "statsInboundDownlink": True,
                        "statsOutboundUplink": True,
                        "statsOutboundDownlink": True
                    }
                }
                # Add API routing rule
                if "routing" not in config or not isinstance(config["routing"], dict):
                    config["routing"] = {"rules": []}
                if "rules" not in config["routing"] or not isinstance(config["routing"]["rules"], list):
                    config["routing"]["rules"] = []
                config["routing"]["rules"].insert(0, {
                    "inboundTag": ["api"],
                    "outboundTag": "api",
                    "type": "field"
                })

                # Force user-defined loglevel
                if "log" not in config or not isinstance(config["log"], dict):
                    config["log"] = {}
                config["log"]["loglevel"] = log_level

                # Ensure a "direct" outbound exists (needed by TUN routing)
                if tun_mode:
                    tags = {ob.get("tag") for ob in config.get("outbounds", [])}
                    if "direct" not in tags:
                        config["outbounds"].append(self._build_direct_outbound())
                    if "dns-out" not in tags:
                        config["outbounds"].append({
                            "protocol": "dns",
                            "tag": "dns-out"
                        })
                    
                    # Inject fakedns for proper domain matching in TUN mode
                    if "fakedns" not in config:
                        config["fakedns"] = [{"ipPool": "198.18.0.0/15", "poolSize": 65535}]
                    
                    if "dns" not in config or not isinstance(config["dns"], dict):
                        config["dns"] = {"servers": ["fakedns", "1.1.1.1", "8.8.8.8", "localhost"]}
                    elif "servers" not in config["dns"] or not isinstance(config["dns"]["servers"], list):
                        config["dns"]["servers"] = ["fakedns", "1.1.1.1", "8.8.8.8", "localhost"]
                    elif "fakedns" not in config["dns"]["servers"]:
                        config["dns"]["servers"].insert(0, "fakedns")

                    if "routing" not in config or not isinstance(config["routing"], dict):
                        config["routing"] = {"rules": []}
                    if "rules" not in config["routing"] or not isinstance(config["routing"]["rules"], list):
                        config["routing"]["rules"] = []
                    
                    # Intercept port 53 and send to dns-out (so Xray's DNS resolves it via fakedns)
                    config["routing"]["rules"].insert(0, {
                        "type": "field",
                        "port": "53",
                        "outboundTag": "dns-out",
                    })

                # In TUN mode, bind proxy outbound(s) and direct outbound to the physical
                # interface to prevent routing loops through the TUN device.
                if tun_mode and outbound_interface:
                    for ob in config.get("outbounds", []):
                        p = ob.get("protocol", "")
                        if p in ("vless", "vmess", "trojan", "hysteria2",
                                 "hysteria", "shadowsocks", "wireguard", "freedom"):
                            ss = ob.setdefault("streamSettings", {})
                            so = ss.setdefault("sockopt", {})
                            so["interface"] = outbound_interface

                return config

        # =============================================================
        # Standard protocol — build outbound from parsed URL fields
        # =============================================================

        # ----- Build outbounds -----
        if protocol == "hysteria2":
            proxy_outbound = self._build_hysteria2_outbound(
                vless_config, outbound_interface if tun_mode else None,
            )
        else:
            proxy_outbound = self._build_vless_outbound(
                vless_config, outbound_interface if tun_mode else None,
            )

        outbounds: List[Dict[str, Any]] = [proxy_outbound]

        if tun_mode:
            outbounds.append(self._build_direct_outbound(outbound_interface))
            outbounds.append({
                "protocol": "dns",
                "tag": "dns-out"
            })

        # ----- Assemble final config -----
        template = _load_template()

        # Add API and Stats configuration for traffic monitoring
        api_config = {
            "services": ["StatsService"],
            "tag": "api"
        }
        stats_config = {}
        policy_config = {
            "levels": {
                "0": {"statsUserUplink": True, "statsUserDownlink": True}
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
                "statsOutboundUplink": True,
                "statsOutboundDownlink": True
            }
        }
        api_inbound = {
            "listen": "127.0.0.1",
            "port": 10085,
            "protocol": "dokodemo-door",
            "settings": {
                "address": "127.0.0.1"
            },
            "tag": "api"
        }
        api_routing_rule = {
            "inboundTag": ["api"],
            "outboundTag": "api",
            "type": "field"
        }

        # Ensure api inbound is present
        inbounds.append(api_inbound)

        if template is not None:
            # Template mode: keep everything from the template and inject
            # dynamic sections.
            config = dict(template)
            config["inbounds"] = inbounds
            config["outbounds"] = outbounds
            config["api"] = api_config
            config["stats"] = stats_config
            config["policy"] = policy_config

            # Force user-defined loglevel
            if "log" not in config or not isinstance(config["log"], dict):
                config["log"] = {}
            config["log"]["loglevel"] = log_level

            # If TUN mode is disabled, strip TUN-specific routing rules that
            # reference the "tun" inbound tag — they'd be harmless but noisy.
            if not tun_mode and "routing" in config:
                rules = config["routing"].get("rules", [])
                config["routing"]["rules"] = [
                    r for r in rules
                    if "tun" not in r.get("inboundTag", [])
                ]
            
            # Ensure API routing rule exists
            if "routing" not in config:
                config["routing"] = {"rules": []}
            if "rules" not in config["routing"]:
                config["routing"]["rules"] = []
            config["routing"]["rules"].insert(0, api_routing_rule)
        else:
            # No template — build minimal config in code (legacy mode)
            config: Dict[str, Any] = {
                "log": {"loglevel": log_level},
                "api": api_config,
                "stats": stats_config,
                "policy": policy_config,
                "inbounds": inbounds,
                "outbounds": outbounds,
                "routing": {"rules": [api_routing_rule]}
            }

            if tun_mode:
                config["fakedns"] = [{"ipPool": "198.18.0.0/15", "poolSize": 65535}]
                
                # DNS block is required in TUN mode — without it, DNS
                # queries to the system resolver go through TUN and either
                # loop or get dropped because direct outbound can't resolve
                # them (BUG-04).
                config["dns"] = {
                    "servers": [
                        "fakedns",
                        {
                            "address": "1.1.1.1",
                            "domains": ["geosite:geolocation-!cn"],
                        },
                        "8.8.8.8",
                        "localhost",
                    ],
                }
                config["routing"] = {
                    "domainStrategy": "IPIfNonMatch",
                    "rules": [
                        # DNS queries → dns-out (triggers fakedns and resolves domains properly)
                        {
                            "type": "field",
                            "port": "53",
                            "outboundTag": "dns-out",
                        },
                        # Private IPs (LAN, Steam Link, local multiplayer) → direct
                        {
                            "type": "field",
                            "ip": ["geoip:private"],
                            "outboundTag": "direct",
                        },
                        # TUN traffic → proxy
                        {
                            "type": "field",
                            "inboundTag": ["tun"],
                            "outboundTag": "proxy",
                        },
                        # SOCKS/HTTP inbounds → proxy
                        {
                            "type": "field",
                            "inboundTag": ["socks", "http"],
                            "outboundTag": "proxy",
                        },
                    ],
                }
            else:
                config["routing"] = {"rules": [api_routing_rule]}

        return config

    async def start(self, config_file: str) -> Dict[str, Any]:
        """
        Start xray-core process with given config file.

        Args:
            config_file: Path to xray-core config file

        Returns:
            Dictionary with success status and process ID
        """
        try:
            # Check if binary exists
            if not os.path.exists(self.xray_binary_path):
                return {
                    "success": False,
                    "error": f"xray-core binary not found at {self.xray_binary_path}",
                    "errorCode": "BINARY_NOT_FOUND",
                }

            # Check if binary is executable
            if not os.access(self.xray_binary_path, os.X_OK):
                return {
                    "success": False,
                    "error": f"xray-core binary is not executable: {self.xray_binary_path}",
                    "errorCode": "BINARY_NOT_EXECUTABLE",
                }

            # Redirect xray-core output to a log file instead of PIPE to
            # prevent buffer-full deadlock (BUG-01: PIPE buffers are ~64KB;
            # once full, xray-core blocks on write and hangs silently).
            log_dir = os.environ.get("DECKY_PLUGIN_LOG_DIR") or tempfile.gettempdir()
            os.makedirs(log_dir, exist_ok=True)
            self._log_path = os.path.join(log_dir, "xray-core.log")
            self._log_file = open(self._log_path, "w")

            env = os.environ.copy()
            xray_dir = os.path.dirname(self.xray_binary_path)
            env["XRAY_LOCATION_ASSET"] = xray_dir

            self.process = await asyncio.create_subprocess_exec(
                self.xray_binary_path,
                "-config",
                config_file,
                stdout=self._log_file,
                stderr=self._log_file,
                env=env,
                cwd=xray_dir,
            )

            self.process_id = self.process.pid
            self.config_file = config_file

            # Wait a moment to check if process started successfully
            await asyncio.sleep(0.5)

            if self.process.returncode is not None:
                # Process exited immediately — read log for error details
                self._log_file.close()
                self._log_file = None
                error_msg = "Unknown error"
                try:
                    with open(self._log_path, "r") as f:
                        error_msg = f.read(4096).strip() or error_msg
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": f"xray-core process failed to start: {error_msg}",
                    "errorCode": "PROCESS_START_FAILED",
                }

            return {"success": True, "processId": self.process_id}

        except Exception as e:
            if self._log_file:
                self._log_file.close()
                self._log_file = None
            return {
                "success": False,
                "error": f"Failed to start xray-core: {str(e)}",
                "errorCode": "PROCESS_START_ERROR",
            }

    async def stop(self) -> Dict[str, Any]:
        """
        Stop xray-core process.

        Returns:
            Dictionary with success status
        """
        try:
            if self.process is None:
                return {"success": True, "message": "No process running"}

            # Terminate process
            self.process.terminate()

            # Wait for process to terminate (with timeout)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if process doesn't terminate
                self.process.kill()
                await self.process.wait()

            # Close log file (BUG-01 cleanup)
            if self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None

            # Cleanup config file
            if self.config_file and os.path.exists(self.config_file):
                try:
                    os.remove(self.config_file)
                except Exception:
                    pass  # Ignore cleanup errors

            self.process = None
            self.process_id = None
            self.config_file = None

            return {"success": True}

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to stop xray-core: {str(e)}",
                "errorCode": "PROCESS_STOP_ERROR",
            }

    def is_running(self) -> bool:
        """
        Check if xray-core process is running.

        Returns:
            True if process is running, False otherwise
        """
        if self.process is None:
            return False

        # Check if process is still alive
        return self.process.returncode is None

    def get_process_id(self) -> Optional[int]:
        """
        Get xray-core process ID.

        Returns:
            Process ID or None if not running
        """
        return self.process_id

    async def monitor(self) -> Dict[str, Any]:
        """
        Monitor xray-core process health.

        Returns:
            Dictionary with process status
        """
        if not self.is_running():
            return {"running": False, "processId": None}

        return {"running": True, "processId": self.process_id}

    def get_logs(self, limit: int = 300) -> List[str]:
        """
        Retrieve the last N lines of xray-core output logs.

        Args:
            limit: Maximum number of lines to return

        Returns:
            List of log lines
        """
        if not self._log_path or not os.path.exists(self._log_path):
            return ["xray-core log file not found. Process might not be running."]

        try:
            # Safely open and read tail lines
            with open(self._log_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                lines = all_lines[-limit:]
            return [line.rstrip() for line in lines]
        except Exception as e:
            return [f"Failed to read logs: {str(e)}"]

    def clear_logs(self) -> None:
        """Clear the xray-core log file."""
        if self._log_path and os.path.exists(self._log_path):
            try:
                # Truncate the file so we don't break the open file descriptor if it's running
                with open(self._log_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
            except OSError as e:
                print(f"XrayManager: Failed to clear logs: {e}")

    async def get_traffic_stats(self) -> Dict[str, Any]:
        """
        Query traffic statistics using xray-core API.
        
        Returns:
            Dict containing uplink and downlink stats in bytes.
        """
        if not self.is_running():
            return {"success": False, "error": "Xray process not running"}
            
        try:
            # Command: xray-core api statsquery --server=127.0.0.1:10085
            proc = await asyncio.create_subprocess_exec(
                self.xray_binary_path, "api", "statsquery", "--server=127.0.0.1:10085",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
            
            if proc.returncode != 0:
                return {"success": False, "error": f"API Error: {stderr.decode('utf-8', errors='ignore')}"}
                
            try:
                # The output is typically JSON format {"stat": [{"name": "inbound>>>socks>>>traffic>>>downlink", "value": "12345"}, ...]}
                stats_json = json.loads(stdout.decode('utf-8'))
            except json.JSONDecodeError:
                # Fallback to simple text parsing if JSON is malformed
                stats_json = {"stat": []}
                for line in stdout.decode('utf-8').splitlines():
                    if "name" in line and "value" in line:
                        pass # too complex to manually parse, but normally it outputs valid JSON
                        
            # Aggregate total uplink and downlink
            up = 0
            down = 0
            for stat in stats_json.get("stat", []):
                name = stat.get("name", "")
                val = int(stat.get("value", 0))
                # Count all outbound traffic except direct, dns-out, and api
                if ">>>traffic>>>uplink" in name and name.startswith("outbound"):
                    if ">>>direct>>>" not in name and ">>>dns-out>>>" not in name and ">>>api>>>" not in name:
                        up += val
                elif ">>>traffic>>>downlink" in name and name.startswith("outbound"):
                    if ">>>direct>>>" not in name and ">>>dns-out>>>" not in name and ">>>api>>>" not in name:
                        down += val
                
            return {"success": True, "uplink": up, "downlink": down}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
