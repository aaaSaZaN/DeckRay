"""
Xray Decky Plugin - Backend Entry Point | Плагин Xray Decky — Точка входа бэкенда
This module provides the Plugin class that serves as the backend entry point
for the Decky Loader plugin. All backend methods are defined here.

Этот модуль содержит класс Plugin, который служит точкой входа бэкенда
для плагина Decky Loader. Все бэкенд-методы определены здеся.
"""

import os
import sys
import uuid
import ssl
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional


def _get_lan_ip() -> str:
    """
    Determine the host's LAN IP (not 127.0.0.1) so the import page URL is reachable
    from other devices on the same network. Tries: (1) outgoing socket to 8.8.8.8,
    (2) hostname -I, (3) ip route get 8.8.8.8. Falls back to 127.0.0.1 only if all fail
    """
    # 1) Outgoing UDP socket: usually gives the interface IP used for default route \\ udp сокет обычно дает ip интерфейса используемого для машрута по дефолту
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and ip != "127.0.0.1":
                return ip
    except Exception:
        pass
    # 2) Linux: hostname -I returns space-separated IPs; first is typically primary \\ в пингвине : команда hostname -I возвращает IP через пробел; первый обычно основной
    try:
        out = subprocess.check_output(
            ["hostname", "-I"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        for part in out.strip().split():
            part = part.strip()
            if part and not part.startswith("127."):
                return part
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pass
    # 3) ip route get 8.8.8.8 → parse "src" address \\ команда ip route get 8.8.8.8 парсит адрес src
    try:
        out = subprocess.check_output(
            ["ip", "-4", "route", "get", "8.8.8.8"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        for line in out.splitlines():
            if "src" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "src" and i + 1 < len(parts):
                        ip = parts[i + 1].strip()
                        if ip and ip != "127.0.0.1":
                            return ip
                        break
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pass
    return "127.0.0.1"


# Add plugin directory to Python path for backend module imports || Добавление директорий плагина в python path для импорта модулей
PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from settings import SettingsManager
from backend.src.config_parser import (
    validate_vless_url,
    parse_vless_url,
    parse_hysteria2_url,
    parse_subscription_url,
    parse_subscription_content,
    fetch_subscription_url,
    build_vless_config,
    build_hysteria2_config,
    build_native_json_config,
)
from backend.src.error_codes import (
    ErrorCode,
    create_error_response,
    create_success_response,
)
from backend.src.xray_manager import XrayManager
from backend.src.connection_manager import get_connection_state, ConnectionStatus
from backend.src.tun_manager import TUNManager
from backend.src.kill_switch import KillSwitch
from backend.src.system_proxy import SystemProxyManager
from backend.src.import_server import create_import_app, generate_import_token
from backend.src.cert_utils import ensure_cert_key
from backend.src.xray_downloader import XrayDownloader
import aiohttp
from aiohttp import web


# Initialize SettingsManager \\ менеджер настроек
settings_dir = os.environ.get("DECKY_PLUGIN_SETTINGS_DIR", "")
if not settings_dir:
    raise RuntimeError("DECKY_PLUGIN_SETTINGS_DIR environment variable not set")

settings = SettingsManager(name="settings", settings_directory=settings_dir)
settings.read()


# Resolve xray-core path: deployed uses bin/, dev uses backend/out/ \\ путь к бинарнику XRAY , в релизе = bin/ , дев = backend/out/
def _resolve_xray_path(plugin_dir: Path) -> str:
    for candidate in (
        plugin_dir / "bin" / "xray-core",
        plugin_dir / "backend" / "out" / "xray-core",
    ):
        if candidate.exists():
            return str(candidate)
    return str(
        plugin_dir / "backend" / "out" / "xray-core"
    )  # fallback for clearer error


# Initialize XrayManager, TUNManager, KillSwitch, and SystemProxyManager \\ модули управления xray tun килл свитч и систем прокси
xray_manager = XrayManager(xray_binary_path=_resolve_xray_path(PLUGIN_DIR))
tun_manager = TUNManager()
kill_switch = KillSwitch()
system_proxy_manager = SystemProxyManager()
xray_downloader = XrayDownloader(plugin_dir=PLUGIN_DIR)


class Plugin:
    """
    Main plugin class for DeckRay.

    All backend methods that can be called from the frontend are defined here.
    Methods are async and return dictionaries with success/error information.

    Все методы бэкенда, которое можно взять из фронта определенны здесь. Методы являются асинхронными и возвращают словари с инфо об выполнении или ошибке.
    """

    async def _main(self):
        """
        Long-running code that executes for the plugin's lifetime.
        Called when the plugin is loaded.

        долгоживущий код который живет на протяжении работы всего плагина. вызывается при загрузке плагина.
        """
        print("DeckRay: Backend initialized")
        # Load connection state from settings // загрузка сост. подключения из настроек.
        from backend.src.connection_manager import load_connection_state_from_settings

        load_connection_state_from_settings(settings)

        # Start import HTTP server \\ старт локал http сервера
        # ImportServerConfig: port from settings, default 8765, range 1024–65535.
        # Bind to 0.0.0.0 so the import page is reachable from LAN (QR scan). If preferred port is in use, try next ports. \\ слушание локалки 0.0.0.0 для доступа из локальной сети. если порт занят - перебирание других портов
        self._import_token = generate_import_token()
        import_server_config = settings.getSetting("importServer", {"port": 8765})
        port = int(import_server_config.get("port", 8765))
        port = max(1024, min(65535, port))
        static_dir = Path(__file__).resolve().parent / "backend" / "static"
        runtime_dir = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", "")
        ssl_context = None
        if static_dir.is_dir():

            async def _notify_vless_saved():
                """Notify frontend that VLESS config was saved (e.g. from import page

                Уведомляет фронт о том, что конфиг влесс был сохранен - например, страница импорта.
                """

                try:
                    from decky import emit

                    await emit("vless_config_updated")
                except Exception as e:
                    print(
                        f"DeckRay: Failed to emit vless_config_updated: {e}"
                    )

            self._import_runner = None
            runner = None
            for attempt in range(11):  # try port, port+1, ... port+10
                try_port = port + attempt
                if try_port > 65535:
                    break
                try:
                    import_app = create_import_app(
                        settings, static_dir,
                        on_vless_saved=_notify_vless_saved,
                        import_token=self._import_token,
                    )
                    runner = web.AppRunner(import_app)
                    await runner.setup()
                    site = web.TCPSite(
                        runner, "0.0.0.0", try_port
                    )
                    await site.start()
                    self._import_runner = runner
                    if try_port != port:
                        import_server_config["port"] = try_port
                        settings.setSetting("importServer", import_server_config)
                        settings.commit()
                        print(
                            f"DeckRay: Port {port} in use, using {try_port}. Import server listening on 0.0.0.0:{try_port} (HTTP)"
                        )
                    else:
                        print(
                            f"DeckRay: Import server listening on 0.0.0.0:{try_port} (HTTP)"
                        )
                    break
                except OSError as e:
                    if runner is not None:
                        await runner.cleanup()
                        runner = None
                    if attempt == 0:
                        print(
                            f"DeckRay: Port {try_port} failed: {e}, trying next ports..."
                        )
                    if attempt == 10:
                        self._import_runner = None
                        print(
                            f"DeckRay: Import server could not start on ports {port}-{port + 10}. Check firewall or free a port."
                        )
        elif not runtime_dir:
            self._import_runner = None
            print(
                "DeckRay: DECKY_PLUGIN_RUNTIME_DIR not set, import server not started"
            )
        elif not static_dir.is_dir():
            self._import_runner = None
            print(
                "DeckRay: backend/static not found, import server not started"
            )

    async def _auto_update_subscriptions(self):
        import asyncio
        while True:
            try:
                subs = settings.getSetting("subscriptions", [])
                now = int(time.time())
                updated_any = False
                for sub in subs:
                    interval = sub.get("update_interval", 0)
                    last_updated = sub.get("last_updated", 0)
                    if interval > 0 and (now - last_updated) >= interval * 3600:
                        url = sub.get("url")
                        headers = sub.get("custom_headers")
                        allow_insecure = False # Strict SSL verification \\ строгая проверка ssl
                        content_str, err, metadata = await fetch_subscription_url(url, headers, allow_insecure)
                        if not err and content_str:
                            parsed_configs, _ = parse_subscription_content(content_str)
                            if parsed_configs:
                                # Re-build configs
                                new_configs = []
                                for i, first in enumerate(parsed_configs):
                                    if isinstance(first, dict) and "outbounds" in first:
                                        config = build_native_json_config(first, url.strip(), "subscription", index=i)
                                    else:
                                        source_link = first.get("_sourceLink", url.strip())
                                        proto = first.get("_protocol", "")
                                        if proto == "hysteria2":
                                            config = build_hysteria2_config(first, source_link, "subscription")
                                        else:
                                            config = build_vless_config(first, source_link, "subscription")
                                    config["id"] = str(uuid.uuid4())
                                    config["sub_id"] = sub["id"]
                                    config["lastValidatedAt"] = int(time.time())
                                    new_configs.append(config)
                                
                                # Replace old configs for this sub
                                all_configs = settings.getSetting("vlessConfigs", [])
                                all_configs = [c for c in all_configs if c.get("sub_id") != sub["id"]]
                                all_configs.extend(new_configs)
                                settings.setSetting("vlessConfigs", all_configs)
                                sub["last_updated"] = now
                                if metadata.get("profile-update-interval"):
                                    sub["update_interval"] = metadata.get("profile-update-interval")
                                updated_any = True
                
                if updated_any:
                    settings.setSetting("subscriptions", subs)
                    settings.commit()
            except Exception as e:
                print(f"DeckRay: Auto-update error: {e}")
            await asyncio.sleep(3600)  # Check every hour \\ проверка каждый час

    async def _unload(self):
        """
        Cleanup code called when the plugin is unloaded.

        код очистки вызываемый при выгрузке плагина
        """
        print("DeckRay: Backend unloading")
        # Stop import HTTP server \\ остановка http сервера.
        if getattr(self, "_import_runner", None) is not None:
            await self._import_runner.cleanup()
            self._import_runner = None

        # Clear system proxy if active \\ очистка систем прокси - если того имеется
        system_proxy_pref = settings.getSetting("systemProxy", {})
        if system_proxy_pref.get("enabled", False):
            await system_proxy_manager.clear_system_proxy()
            system_proxy_pref["enabled"] = False
            settings.setSetting("systemProxy", system_proxy_pref)
            settings.commit()

        # Stop xray-core process if running \\ остановка хрей ядра если тот включен
        connection_state = get_connection_state()
        if connection_state.status == ConnectionStatus.CONNECTED:
            tun_pref = settings.getSetting("tunMode", {"enabled": True})
            if tun_pref.get("enabled", False):
                await tun_manager.remove_system_route()
                await tun_manager.cleanup_tun_interface()
            await xray_manager.stop()
            connection_state.set_disconnected()

        # Deactivate kill switch if active \\ отключение килл свича если включен
        if kill_switch.get_status().get("isActive", False):
            await kill_switch.deactivate()

    # SettingsManager wrapper methods  // методы обертки для сеттингс менеджер
    async def settings_read(self) -> Dict[str, Any]:
        """Read settings from SettingsManager // чтение настроек из SettingsManager."""
        try:
            settings.read()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def settings_commit(self) -> Dict[str, Any]:
        """Commit settings to SettingsManager // сохраняет настройки в settingsmanager."""
        try:
            settings.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def settings_getSetting(self, key: str, defaults: Any) -> Dict[str, Any]:
        """Get a setting value from SettingsManager // записывает значение настроек из SettingsManager."""
        try:
            value = settings.getSetting(key, defaults)
            return {"success": True, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def settings_setSetting(self, key: str, value: Any) -> Dict[str, Any]:
        """Set a setting value in SettingsManager // получает значение настроек из SettingsManager """
        try:
            settings.setSetting(key, value)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # VLESS Configuration Management // управление конфигурациями vless
    async def import_vless_config(self, url: str, custom_headers: Optional[str] = None, allow_insecure: bool = False) -> Dict[str, Any]:
        """Import a proxy configuration from a URL or raw content // импорт конфига прокси из url адреса или сырого содержимого."""
        try:
            is_valid, error_msg = validate_vless_url(url)
            if not is_valid:
                return create_error_response(ErrorCode.INVALID_URL, error_msg)

            configs = settings.getSetting("vlessConfigs", [])
            subscriptions = settings.getSetting("subscriptions", [])
            
            sub_id = None
            metadata = {}
            sub_format = None
            parsed_configs = []

            if url.strip().startswith("https://") or url.strip().startswith("http://"):
                content_str, fetch_error, metadata = await fetch_subscription_url(
                    url.strip(), custom_headers=custom_headers, allow_insecure=allow_insecure
                )
                if fetch_error:
                    return create_error_response(ErrorCode.NETWORK_ERROR, fetch_error)

                parsed_configs, sub_format = parse_subscription_content(content_str or "")
                if not parsed_configs:
                    return create_error_response(ErrorCode.INVALID_URL, "Subscription returned no valid configurations")
                
                sub_id = str(uuid.uuid4())
                subscriptions.append({
                    "id": sub_id,
                    "url": url.strip(),
                    "custom_headers": custom_headers,
                    "title": metadata.get("profile-title", url.strip()),
                    "announce": metadata.get("announce", ""),
                    "update_interval": metadata.get("profile-update-interval", 0),
                    "last_updated": int(time.time())
                })
            else:
                parsed_configs, sub_format = parse_subscription_content(url)
                if not parsed_configs:
                    parsed = parse_vless_url(url)
                    if parsed:
                        config = build_vless_config(parsed, url, "single")
                        parsed_configs = [config]
                    else:
                        parsed_hy2 = parse_hysteria2_url(url)
                        if parsed_hy2:
                            config = build_hysteria2_config(parsed_hy2, url, "single")
                            parsed_configs = [config]
            
            if not parsed_configs:
                return create_error_response(ErrorCode.INVALID_URL, "Failed to parse URL or subscription content")

            new_configs = []
            for i, first in enumerate(parsed_configs):
                config = None
                if isinstance(first, dict) and "outbounds" in first:
                    config = build_native_json_config(first, url.strip(), "subscription" if sub_id else "single", index=i)
                else:
                    source_link = first.get("_sourceLink", url.strip())
                    proto = first.get("_protocol", "")
                    ctype = "subscription" if sub_id else "single"
                    if proto == "hysteria2":
                        config = build_hysteria2_config(first, source_link, ctype)
                    else:
                        config = build_vless_config(first, source_link, ctype)
                        
                config["id"] = str(uuid.uuid4())
                config["sub_id"] = sub_id
                config["lastValidatedAt"] = int(time.time())
                new_configs.append(config)
                
            configs.extend(new_configs)
            settings.setSetting("vlessConfigs", configs)
            if sub_id:
                settings.setSetting("subscriptions", subscriptions)
            if new_configs and not settings.getSetting("activeConfigId", None):
                settings.setSetting("activeConfigId", new_configs[0]["id"])
            settings.commit()

            response_data = {"success": True, "availableNodes": len(new_configs)}
            if sub_format:
                response_data["subscriptionFormat"] = sub_format

            return create_success_response(response_data)

        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, f"Failed to import config: {str(e)}")

    async def get_all_configs(self) -> Dict[str, Any]:
        try:
            configs = settings.getSetting("vlessConfigs", [])
            subs = settings.getSetting("subscriptions", [])
            active = settings.getSetting("activeConfigId", None)
            return {"success": True, "configs": configs, "subscriptions": subs, "activeConfigId": active}
        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, str(e))
            
    async def set_active_config(self, config_id: str) -> Dict[str, Any]:
        try:
            settings.setSetting("activeConfigId", config_id)
            settings.commit()
            return {"success": True}
        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, str(e))
            
    async def get_vless_config(self) -> Dict[str, Any]:
        """
        Get stored VLESS configuration // получает сохраненный конфиг vless.

        Returns:
            {
                'config': VLESSConfig | None,
                'exists': bool
            }
        """
        try:
            configs = settings.getSetting("vlessConfigs", [])
            active = settings.getSetting("activeConfigId", None)
            config = next((c for c in configs if c.get("id") == active), None)
            if not config and configs:
                config = configs[0]
            # fallback \\ фоллбэк
            if not config:
                config = settings.getSetting("vlessConfig", None)
            exists = config is not None
            return {"config": config, "exists": exists}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to get config: {str(e)}"
            )

    async def delete_config(self, config_id: str) -> Dict[str, Any]:
        try:
            configs = settings.getSetting("vlessConfigs", [])
            configs = [c for c in configs if c.get("id") != config_id]
            settings.setSetting("vlessConfigs", configs)
            
            active = settings.getSetting("activeConfigId", None)
            if active == config_id:
                settings.setSetting("activeConfigId", configs[0]["id"] if configs else None)
            settings.commit()
            return {"success": True}
        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, str(e))

    async def delete_subscription(self, sub_id: str) -> Dict[str, Any]:
        try:
            subs = settings.getSetting("subscriptions", [])
            subs = [s for s in subs if s.get("id") != sub_id]
            settings.setSetting("subscriptions", subs)
            
            configs = settings.getSetting("vlessConfigs", [])
            configs = [c for c in configs if c.get("sub_id") != sub_id]
            settings.setSetting("vlessConfigs", configs)
            
            active = settings.getSetting("activeConfigId", None)
            if not any(c.get("id") == active for c in configs):
                settings.setSetting("activeConfigId", configs[0]["id"] if configs else None)
            settings.commit()
            return {"success": True}
        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, str(e))

    async def get_xray_log_level(self) -> Dict[str, Any]:
        """
        Get current xray-core log level // получение текущих уровня логирования хрей кор

        Returns:
            { 'logLevel': str }
        """
        try:
            log_level = settings.getSetting("xrayLogLevel", "warning")
            return {"logLevel": log_level}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to get log level: {str(e)}"
            )

    async def set_xray_log_level(self, log_level: str) -> Dict[str, Any]:
        """
        Set xray-core log level # установка уровней логов хрей

        Args:
            log_level: Log level ('debug', 'info', 'warning', 'error', 'none')

        Returns:
            { 'success': bool }
        """
        try:
            valid_levels = ["debug", "info", "warning", "error", "none"]
            if log_level not in valid_levels:
                return create_error_response(
                    ErrorCode.INVALID_CONFIG, f"Invalid log level: {log_level}"
                )
            settings.setSetting("xrayLogLevel", log_level)
            settings.commit()
            return {"success": True}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to set log level: {str(e)}"
            )

    async def get_import_server_url(self) -> Dict[str, Any]:
        """
        Get URL for the import page (for QR code). Resolves LAN IP (not 127.0.0.1)
        and port from importServer.port so devices on the same network can open the page.
        Returns https baseUrl so the page is in a secure context and Paste works.
        //
        Получает url адрес страницы импорта для qr code. определяет локал ip адрес но не 127.0.0.1.
        и порт из importServer.port чтобы устройства в той же сети могли открыть эту страницу.
        Возвращает baseURL чтобы страница находилась в безопасном контексте.
        Returns:
            { 'baseUrl': 'https://{lan_ip}:{port}', 'path': '/import' }
        """
        try:
            import_server_config = settings.getSetting("importServer", {"port": 8765})
            port = int(import_server_config.get("port", 8765))
            port = max(1024, min(65535, port))
            local_ip = _get_lan_ip()
            base_url = f"http://{local_ip}:{port}"
            path = "/"
            return {"baseUrl": base_url, "path": path}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to get import URL: {str(e)}"
            )

    async def get_xray_logs(self, limit: int = 300) -> Dict[str, Any]:
        """
        Get latest xray-core process logs // получение логов xray

        Args:
            limit: Maximum number of lines to return

        Returns:
            Dictionary with success and log lines
        """
        try:
            logs = xray_manager.get_logs(limit)
            return {"success": True, "logs": logs}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to get logs: {str(e)}"
            )

    async def clear_xray_logs(self) -> Dict[str, Any]:
        """
        Clear xray-core logs // очистка xray логов.
        """
        try:
            xray_manager.clear_logs()
            return {"success": True}
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to clear logs: {str(e)}"
            )

    async def validate_vless_config(self) -> Dict[str, Any]:
        """
        Re-validate stored VLESS configuration // повторная проверка сохраненного конфига vless .

        Returns:
            {
                'isValid': bool,
                'error': str | None
            }
        """
        try:
            config = settings.getSetting("vlessConfig", None)
            if not config:
                return {
                    "isValid": False,
                    "error": "No VLESS configuration stored",
                }

            # Re-validate the source URL // повторно проверяем исходный url адрес
            source_url = config.get("sourceUrl", "")
            if not source_url:
                config["isValid"] = False
                config["validationError"] = "Missing source URL"
                settings.setSetting("vlessConfig", config)
                settings.commit()
                return {
                    "isValid": False,
                    "error": "Missing source URL",
                }

            is_valid, error_msg = validate_vless_url(source_url)
            config["isValid"] = is_valid
            config["lastValidatedAt"] = int(time.time())

            if not is_valid:
                config["validationError"] = error_msg or "Validation failed"
                settings.setSetting("vlessConfig", config)
                settings.commit()
                return {
                    "isValid": False,
                    "error": error_msg or "Validation failed",
                }

            # Clear validation error if valid // стирание ошибки валидации если конфигурация верна
            if "validationError" in config:
                del config["validationError"]

            settings.setSetting("vlessConfig", config)
            settings.commit()

            return {
                "isValid": True,
            }

        except Exception as e:
            return {
                "isValid": False,
                "error": f"Validation error: {str(e)}",
            }

    async def get_all_configs(self) -> Dict[str, Any]:
        """
        Get all stored configs and subscriptions // получает все сохраненные конфиги и подписки.
        Returns:
            {
                'success': bool,
                'configs': List[dict],
                'subscriptions': List[dict],
                'activeConfigId': str | None,
            }
        """
        try:
            configs = settings.getSetting("vlessConfigs", [])
            subscriptions = settings.getSetting("subscriptions", [])
            active_id = settings.getSetting("activeConfigId", None)
            return {
                "success": True,
                "configs": configs,
                "subscriptions": subscriptions,
                "activeConfigId": active_id
            }
        except Exception as e:
            return create_error_response(ErrorCode.UNKNOWN_ERROR, str(e))

    async def get_traffic_stats(self) -> Dict[str, Any]:
        """
        Get traffic statistics from Xray API // статистика трафика из xray api .
        Returns: { success: bool, uplink: int, downlink: int }
        """
        try:
            return await xray_manager.get_traffic_stats()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def ping_host(self, host: str, method: str = "http_get") -> Dict[str, Any]:
        """
        Ping a host to measure latency // пинг хоста для измерение пинга
        Supports 'host' or 'host:port' format.
        Methods: 'tcp', 'icmp', 'http_get', 'http_head'
        Returns: { success: bool, latencyMs: int | null, error: str }
        """
        import time
        import asyncio
        try:
            port = 443
            if ':' in host and not host.startswith('['): # basic ipv6 exclusion
                parts = host.split(':', 1)
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    pass

            if method == "icmp":
                return await self._ping_icmp(host)
            elif method == "http_get":
                return await self._ping_http(host, port, "GET")
            elif method == "http_head":
                return await self._ping_http(host, port, "HEAD")
            else:  # tcp (default fallback)
                return await self._ping_tcp(host, port)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ping_tcp(self, host: str, port: int) -> Dict[str, Any]:
        """TCP connect ping // тсп пинг """
        import time
        import asyncio
        try:
            start_time = time.monotonic()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)
            writer.close()
            await writer.wait_closed()
            return {"success": True, "latencyMs": latency_ms}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ping_icmp(self, host: str) -> Dict[str, Any]:
        """ICMP ping via system ping command // icmp пинг."""
        import asyncio
        import re
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "5", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=7.0)
            if proc.returncode != 0:
                return {"success": False, "error": "Host unreachable"}
            output = stdout.decode("utf-8", errors="ignore")
            match = re.search(r"time[=<](\d+\.?\d*)", output)
            if match:
                latency_ms = int(float(match.group(1)))
                return {"success": True, "latencyMs": latency_ms}
            return {"success": True, "latencyMs": None}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ping_http(self, host: str, port: int, http_method: str = "GET") -> Dict[str, Any]:
        """HTTP GET/HEAD ping // via/get пинг."""
        import time
        try:
            scheme = "https" if port == 443 else "http"
            url = f"{scheme}://{host}:{port}"
            timeout = aiohttp.ClientTimeout(total=5, connect=5)
            start_time = time.monotonic()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                method_fn = session.get if http_method == "GET" else session.head
                async with method_fn(url, ssl=False, allow_redirects=False) as resp:
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    return {"success": True, "latencyMs": latency_ms}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_subscription(self, sub_id: str) -> Dict[str, Any]:
        """
        Force update a subscription by its ID. // принудительная обновление подписки по ее ID
        """
        try:
            subs = settings.getSetting("subscriptions", [])
            sub = next((s for s in subs if s.get("id") == sub_id), None)
            if not sub:
                return {"success": False, "error": "Subscription not found"}

            url = sub.get("url")
            headers = sub.get("custom_headers")
            content_str, err, metadata = await fetch_subscription_url(url, headers, allow_insecure=True)
            if err or not content_str:
                return {"success": False, "error": err or "Empty response from server"}

            parsed_configs, sub_format = parse_subscription_content(content_str)
            if not parsed_configs:
                return {"success": False, "error": "Failed to parse subscription content"}

            new_configs = []
            for i, first in enumerate(parsed_configs):
                if isinstance(first, dict) and "outbounds" in first:
                    config = build_native_json_config(first, url.strip(), "subscription", index=i)
                else:
                    source_link = first.get("_sourceLink", url.strip())
                    proto = first.get("_protocol", "")
                    if proto == "hysteria2":
                        config = build_hysteria2_config(first, source_link, "subscription")
                    else:
                        config = build_vless_config(first, source_link, "subscription")
                config["id"] = str(uuid.uuid4())
                config["sub_id"] = sub_id
                config["lastValidatedAt"] = int(time.time())
                new_configs.append(config)

            # Replace old configs for this sub \\ замена старых конфигураций для подписки
            all_configs = settings.getSetting("vlessConfigs", [])
            all_configs = [c for c in all_configs if c.get("sub_id") != sub_id]
            all_configs.extend(new_configs)
            settings.setSetting("vlessConfigs", all_configs)

            sub["last_updated"] = int(time.time())
            # Update metadata
            if "profile-title" in metadata:
                sub["title"] = metadata["profile-title"]
            if "announce" in metadata:
                sub["announce"] = metadata["announce"]
            if "profile-update-interval" in metadata:
                sub["update_interval"] = metadata["profile-update-interval"]
            
            settings.setSetting("subscriptions", subs)
            settings.commit()
            
            return {"success": True, "updatedNodes": len(new_configs)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_xray_versions(self, limit: int = 15) -> Dict[str, Any]:
        """List recent Xray-core versions from GitHub. // проверка последних версий с гитхаб """
        return await xray_downloader.list_releases(limit)

    async def download_xray_version(self, version: str) -> Dict[str, Any]:
        """Download and install a specific Xray-core version."""
        result = await xray_downloader.download_version(version)
        if result.get("success"):
            # Update the manager's binary path just in case \\ обновление пути к бинарнику в менеджере
            bin_dir = result.get("binDir")
            if bin_dir:
                xray_manager.xray_binary_path = os.path.join(bin_dir, "xray-core")
        return result

    async def set_active_config(self, config_id: str) -> Dict[str, Any]:
        try:
            configs = settings.getSetting("vlessConfigs", [])
            active_conf = next((c for c in configs if c.get("id") == config_id), None)
            if active_conf:
                settings.setSetting("activeConfigId", config_id)
                settings.setSetting("vlessConfig", active_conf)
                settings.commit()

                if xray_manager.is_running():
                    tun_mode = settings.getSetting("tunMode", {"enabled": True})
                    log_level = settings.getSetting("logLevel", "warning")
                    # Try to restart with the new config \\ перезапуск с новым конфигом
                    out_interface = "wlan0"  # Could grab from get_outbound_interface but this handles basic restart
                    from backend.src.network_utils import get_outbound_interface
                    out_interface = get_outbound_interface() or "wlan0"
                    
                    await self.toggle_connection(False)
                    await self.toggle_connection(True)
                    
                return {"success": True}
            return {"success": False, "error": "Config not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_config(self, config_id: str) -> Dict[str, Any]:
        try:
            configs = settings.getSetting("vlessConfigs", [])
            new_configs = [c for c in configs if c.get("id") != config_id]
            settings.setSetting("vlessConfigs", new_configs)
            
            active_id = settings.getSetting("activeConfigId", None)
            if active_id == config_id:
                if new_configs:
                    settings.setSetting("activeConfigId", new_configs[0]["id"])
                    settings.setSetting("vlessConfig", new_configs[0])
                else:
                    settings.setSetting("activeConfigId", None)
                    settings.setSetting("vlessConfig", None)
            settings.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_subscription(self, sub_id: str) -> Dict[str, Any]:
        try:
            subs = settings.getSetting("subscriptions", [])
            new_subs = [s for s in subs if s.get("id") != sub_id]
            settings.setSetting("subscriptions", new_subs)
            
            configs = settings.getSetting("vlessConfigs", [])
            new_configs = [c for c in configs if c.get("sub_id") != sub_id]
            settings.setSetting("vlessConfigs", new_configs)
            
            active_id = settings.getSetting("activeConfigId", None)
            if not any(c.get("id") == active_id for c in new_configs):
                if new_configs:
                    settings.setSetting("activeConfigId", new_configs[0]["id"])
                    settings.setSetting("vlessConfig", new_configs[0])
                else:
                    settings.setSetting("activeConfigId", None)
                    settings.setSetting("vlessConfig", None)
                    
            settings.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def reset_vless_config(self) -> Dict[str, Any]:
        """
        Clear stored VLESS configuration and return to setup state.
        Rejects if connection is active (connected/connecting/blocked).
        Clears system proxy so SOCKS is not left pointing at a stopped proxy.

        Returns:
            { 'success': bool, 'error': str | None }
        """
        connection_state = get_connection_state()
        status = connection_state.status
        if status in (
            ConnectionStatus.CONNECTED,
            ConnectionStatus.CONNECTING,
            ConnectionStatus.BLOCKED,
        ):
            return create_error_response(
                ErrorCode.CONNECTION_ACTIVE,
                "Disconnect before resetting configuration.",
            )
        try:
            # Clear system proxy unconditionally so SOCKS is not left on after reset \\ очистка систем прокси чтобы носок5 не был включен после сброса
            await system_proxy_manager.clear_system_proxy()
            system_proxy_pref = settings.getSetting("systemProxy", {})
            if system_proxy_pref.get("enabled", False):
                system_proxy_pref["enabled"] = False
                settings.setSetting("systemProxy", system_proxy_pref)

            settings.setSetting("vlessConfig", None)
            settings.commit()

            try:
                from decky import emit

                await emit("vless_config_updated")
            except Exception as e:
                print(f"DeckRay: Failed to emit vless_config_updated: {e}")

            return create_success_response()
        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR,
                f"Failed to reset configuration: {str(e)}",
            )

    # TUN Mode Management \\ менеджер tun мода
    async def check_tun_privileges(self) -> Dict[str, Any]:
        """
        Check if plugin has required privileges for TUN mode.

        Returns:
            {
                'hasPrivileges': bool,
                'error': str | None
            }
        """
        try:
            result = await tun_manager.check_privileges()

            # Update TUN mode preference with privilege status \\ обновление статуса тюн с root.
            tun_pref = settings.getSetting("tunMode", {"enabled": True})
            tun_pref["hasPrivileges"] = result.get("hasPrivileges", False)
            tun_pref["privilegeCheckAt"] = int(time.time())
            if "error" in result:
                tun_pref["privilegeError"] = result["error"]
            else:
                tun_pref.pop("privilegeError", None)
            settings.setSetting("tunMode", tun_pref)
            settings.commit()

            return result

        except Exception as e:
            return {
                "hasPrivileges": False,
                "error": f"Failed to check privileges: {str(e)}",
                "errorCode": "PRIVILEGE_CHECK_ERROR",
            }

    async def get_tun_mode_status(self) -> Dict[str, Any]:
        """
        Get TUN mode preference and status.

        Returns:
            {
                'enabled': bool,
                'hasPrivileges': bool,
                'tunInterface': str | None,
                'isActive': bool
            }
        """
        try:
            tun_pref = settings.getSetting("tunMode", {"enabled": True})
            enabled = tun_pref.get("enabled", False)
            has_privileges = tun_pref.get("hasPrivileges", False)

            # Re-validate privileges if the cache is stale (older than 24h) or
            # was never populated. This is checked regardless of the cached
            # value so that *revoked* privileges (cached True) are also caught,
            # not just newly-granted ones. The fresh result and its timestamp
            # are always persisted so a stale/absent privilege never triggers a
            # subprocess check on every subsequent status poll (the original bug
            # behind the slow plugin entry).
            last_check = tun_pref.get("privilegeCheckAt", 0)
            if last_check < time.time() - 86400:
                privilege_result = await tun_manager.check_privileges()
                has_privileges = privilege_result.get("hasPrivileges", False)
                tun_pref["hasPrivileges"] = has_privileges
                tun_pref["privilegeCheckAt"] = int(time.time())
                if "error" in privilege_result:
                    tun_pref["privilegeError"] = privilege_result["error"]
                else:
                    tun_pref.pop("privilegeError", None)
                settings.setSetting("tunMode", tun_pref)
                settings.commit()

            tun_status = tun_manager.get_status()
            tun_interface = tun_status.get("tunInterface")

            # Check if TUN is active (interface exists and connection is active) \\ существует ли интерфейс и активно ли соединение.
            connection_state = get_connection_state()
            is_active = (
                enabled
                and has_privileges
                and connection_state.status == ConnectionStatus.CONNECTED
                and tun_interface is not None
            )

            return {
                "enabled": enabled,
                "hasPrivileges": has_privileges,
                "tunInterface": tun_interface,
                "isActive": is_active,
            }

        except Exception as e:
            return {
                "enabled": False,
                "hasPrivileges": False,
                "tunInterface": None,
                "isActive": False,
                "error": str(e),
            }

    async def toggle_tun_mode(self, enabled: bool) -> Dict[str, Any]:
        """
        Toggle TUN mode preference.

        Args:
            enabled: True to enable, False to disable

        Returns:
            {
                'success': bool,
                'enabled': bool,
                'hasPrivileges': bool,
                'error': str | None
            }
        """
        try:
            # Check privileges first \\ сначала проверка наличие нужных привилегий
            privilege_result = await tun_manager.check_privileges()
            has_privileges = privilege_result.get("hasPrivileges", False)

            if enabled and not has_privileges:
                return create_error_response(
                    ErrorCode.PRIVILEGES_INSUFFICIENT,
                    "TUN mode requires elevated privileges. Please complete installation steps.",
                )

            # Update preference
            tun_pref = settings.getSetting("tunMode", {"enabled": True})
            tun_pref["enabled"] = enabled
            tun_pref["hasPrivileges"] = has_privileges
            if enabled:
                tun_pref["lastEnabledAt"] = int(time.time())
            else:
                tun_pref["lastDisabledAt"] = int(time.time())
            settings.setSetting("tunMode", tun_pref)
            settings.commit()

            return create_success_response(
                {"enabled": enabled, "hasPrivileges": has_privileges}
            )

        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to toggle TUN mode: {str(e)}"
            )

    # Connection Management
    async def toggle_connection(self, enable: bool) -> Dict[str, Any]:
        """
        Toggle proxy connection on/off.

        Args:
            enable: True to connect, False to disconnect

        Returns:
            {
                'success': bool,
                'status': str,  # 'connected', 'disconnected', 'error'
                'error': str | None,
                'processId': int | None
            }
        """
        connection_state = get_connection_state()

        try:
            if enable:
                # Connect
                # Check if already connected
                if connection_state.status == ConnectionStatus.CONNECTED:
                    return create_success_response(
                        {
                            "status": "connected",
                            "processId": connection_state.xray_process_id,
                        }
                    )

                # Load and validate config
                config = settings.getSetting("vlessConfig", None)
                if not config:
                    connection_state.set_error(
                        "No VLESS config stored", ErrorCode.NO_CONFIG
                    )
                    return create_error_response(ErrorCode.NO_CONFIG)

                if not config.get("isValid", False):
                    connection_state.set_error(
                        "VLESS config is invalid", ErrorCode.INVALID_CONFIG
                    )
                    return create_error_response(ErrorCode.INVALID_CONFIG)

                # Set connecting status
                connection_state.set_connecting()

                # Get TUN mode preference
                tun_pref = settings.getSetting("tunMode", {"enabled": True})
                tun_mode = tun_pref.get("enabled", False)

                # If TUN mode is enabled, check privileges
                if tun_mode:
                    has_privileges = tun_pref.get("hasPrivileges", False)
                    if not has_privileges:
                        # Re-check privileges
                        privilege_result = await tun_manager.check_privileges()
                        has_privileges = privilege_result.get("hasPrivileges", False)

                        if not has_privileges:
                            connection_state.set_error(
                                "TUN mode requires elevated privileges",
                                ErrorCode.PRIVILEGES_INSUFFICIENT,
                            )
                            return create_error_response(
                                ErrorCode.PRIVILEGES_INSUFFICIENT,
                                "TUN mode requires elevated privileges. Please complete installation steps.",
                            )

                    await tun_manager.create_tun_interface()

                # TUN: get physical interface for sockopt.interface (avoids routing loop) // получаем физ интерфейс для sockopt.interface во избежании петли машрутизации
                outbound_if = (
                    await tun_manager.get_physical_interface() if tun_mode else None
                )
                if tun_mode and not outbound_if:
                    connection_state.set_error(
                        "TUN: could not determine physical interface",
                        ErrorCode.UNKNOWN_ERROR,
                    )
                    return create_error_response(
                        ErrorCode.UNKNOWN_ERROR,
                        "TUN mode: could not get default route interface. Check network.",
                    )

                log_level = settings.getSetting("xrayLogLevel", "warning")
                config_file = xray_manager.generate_config(
                    config, tun_mode, outbound_if, log_level
                )

                # Start xray-core
                result = await xray_manager.start(config_file)

                if not result.get("success", False):
                    error_msg = result.get("error", "Failed to start xray-core")
                    error_code = result.get("errorCode", ErrorCode.PROCESS_FAILED)
                    connection_state.set_error(error_msg, error_code)
                    return create_error_response(error_code, error_msg)

                # TUN: setup system routing + system proxy.
                # NOTE: xray-core does not natively support TUN inbound, so
                # the TUN interface won't be created by xray. Route setup may
                # fail, but the SOCKS/HTTP proxy is still functional.
                if tun_mode:
                    route_result = await tun_manager.setup_system_route()
                    if not route_result.get("success"):
                        # TUN route failed — log but don't kill the connection.
                        # SOCKS proxy on 10808 and HTTP proxy on 10809 are still
                        # available and the connection is usable.
                        print(
                            f"DeckRay: TUN route failed (SOCKS proxy still works): "
                            f"{route_result.get('error', 'Unknown')}"
                        )

                    # Auto-enable System Proxy (gsettings for GTK/Qt apps) // авто включение систем прокси gsettings для гтк и qt приложений
                    proxy_result = await system_proxy_manager.set_system_proxy(
                        socks_port=10808, http_port=10809
                    )
                    if proxy_result.get("success"):
                        system_proxy_pref = settings.getSetting("systemProxy", {})
                        system_proxy_pref["enabled"] = True
                        system_proxy_pref["autoEnabled"] = True  # Mark as auto-enabled
                        system_proxy_pref["lastEnabledAt"] = int(time.time())
                        settings.setSetting("systemProxy", system_proxy_pref)
                    # Note: Don't fail connection if system proxy fails

                # Update connection state
                process_id = int(result.get("processId", 0))
                connection_state.set_connected(process_id, config_file, config)

                # Deactivate kill switch if active (connection restored)
                kill_switch_pref = settings.getSetting("killSwitch", {})
                if kill_switch_pref.get("isActive", False):
                    await kill_switch.deactivate()
                    kill_switch_pref["isActive"] = False
                    kill_switch_pref["deactivatedAt"] = int(time.time())
                    settings.setSetting("killSwitch", kill_switch_pref)
                    settings.commit()

                # Persist connection state
                settings.setSetting(
                    "connectionState",
                    {"status": "connected", "connectedAt": int(time.time())},
                )
                settings.commit()

                return create_success_response(
                    {"status": "connected", "processId": process_id}
                )

            else:
                # Disconnect
                if connection_state.status == ConnectionStatus.DISCONNECTED:
                    return create_success_response({"status": "disconnected"})

                # Always clear system proxy on disconnect so SOCKS is never left on
                await system_proxy_manager.clear_system_proxy()
                system_proxy_pref = settings.getSetting("systemProxy", {})
                if system_proxy_pref.get("enabled", False):
                    system_proxy_pref["enabled"] = False
                    settings.setSetting("systemProxy", system_proxy_pref)

                # TUN: remove route first, then stop xray
                tun_pref = settings.getSetting("tunMode", {"enabled": True})
                if tun_pref.get("enabled", False):
                    await tun_manager.remove_system_route()
                    await tun_manager.cleanup_tun_interface()

                # Stop xray-core // остановка хрей ядра xd
                result = await xray_manager.stop()

                if not result.get("success", False):
                    # Log error but still mark as disconnected
                    print(
                        f"Warning: Failed to stop xray-core cleanly: {result.get('error')}"
                    )

                # Update connection state
                connection_state.set_disconnected()

                # Check if kill switch should be activated (unexpected disconnect)
                kill_switch_pref = settings.getSetting("killSwitch", {})
                if (
                    kill_switch_pref.get("enabled", False)
                    and connection_state.xray_process_id
                ):
                    # This was an unexpected disconnect, activate kill switch
                    kill_result = await kill_switch.activate(
                        connection_state.xray_process_id
                    )
                    if kill_result.get("success"):
                        kill_switch_pref["isActive"] = True
                        kill_switch_pref["activatedAt"] = int(time.time())
                        connection_state.set_blocked()
                    settings.setSetting("killSwitch", kill_switch_pref)
                    settings.commit()

                # Persist connection state
                settings.setSetting(
                    "connectionState",
                    {
                        "status": "disconnected"
                        if not kill_switch_pref.get("isActive", False)
                        else "blocked",
                        "disconnectedAt": int(time.time()),
                    },
                )
                settings.commit()

                return create_success_response(
                    {
                        "status": "disconnected"
                        if not kill_switch_pref.get("isActive", False)
                        else "blocked"
                    }
                )

        except Exception as e:
            connection_state.set_error(
                f"Connection error: {str(e)}", ErrorCode.UNKNOWN_ERROR
            )
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Connection error: {str(e)}"
            )

    async def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status.

        Returns:
            {
                'status': str,  # 'disconnected', 'connecting', 'connected', 'error', 'blocked'
                'connectedAt': int | None,  # Unix timestamp
                'errorMessage': str | None,
                'processId': int | None,
                'uptime': int | None  # Seconds
            }
        """
        connection_state = get_connection_state()

        # Check if process is still running
        if connection_state.status == ConnectionStatus.CONNECTED:
            if not xray_manager.is_running():
                # Process died unexpectedly
                process_id = connection_state.xray_process_id
                connection_state.set_error(
                    "xray-core process terminated unexpectedly",
                    ErrorCode.PROCESS_FAILED,
                )

                # Check if kill switch should be activated
                kill_switch_pref = settings.getSetting("killSwitch", {})
                if kill_switch_pref.get("enabled", False) and process_id:
                    # Activate kill switch
                    kill_result = await kill_switch.activate(process_id)
                    if kill_result.get("success"):
                        kill_switch_pref["isActive"] = True
                        kill_switch_pref["activatedAt"] = int(time.time())
                        connection_state.set_blocked()
                        settings.setSetting("killSwitch", kill_switch_pref)
                        settings.commit()

                # Cleanup TUN route if was active
                tun_pref = settings.getSetting("tunMode", {"enabled": True})
                if tun_pref.get("enabled", False):
                    await tun_manager.remove_system_route()

                # Cleanup
                await xray_manager.stop()

        # Return current status
        return connection_state.to_dict()

    # Kill Switch Management
    async def toggle_kill_switch(self, enabled: bool) -> Dict[str, Any]:
        """
        Toggle kill switch preference.

        Args:
            enabled: True to enable, False to disable

        Returns:
            {
                'success': bool,
                'enabled': bool
            }
        """
        try:
            kill_switch_pref = settings.getSetting("killSwitch", {})
            kill_switch_pref["enabled"] = enabled

            if enabled:
                kill_switch_pref["lastEnabledAt"] = int(time.time())
            else:
                kill_switch_pref["lastDisabledAt"] = int(time.time())
                # Deactivate if currently active
                if kill_switch_pref.get("isActive", False):
                    await kill_switch.deactivate()
                    kill_switch_pref["isActive"] = False
                    kill_switch_pref["deactivatedAt"] = int(time.time())

                    # Update connection state if blocked
                    connection_state = get_connection_state()
                    if connection_state.status == ConnectionStatus.BLOCKED:
                        connection_state.set_disconnected()

            settings.setSetting("killSwitch", kill_switch_pref)
            settings.commit()

            return create_success_response({"enabled": enabled})

        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to toggle kill switch: {str(e)}"
            )

    async def get_kill_switch_status(self) -> Dict[str, Any]:
        """
        Get kill switch preference and active state.

        Returns:
            {
                'enabled': bool,
                'isActive': bool,  # Whether kill switch is currently blocking
                'activatedAt': int | None  # When kill switch was activated
            }
        """
        try:
            kill_switch_pref = settings.getSetting("killSwitch", {})
            enabled = kill_switch_pref.get("enabled", False)
            is_active = kill_switch_pref.get("isActive", False)
            activated_at = kill_switch_pref.get("activatedAt")

            # Sync with actual kill switch state
            kill_switch_status = kill_switch.get_status()
            is_active = kill_switch_status.get("isActive", False) or is_active

            return {
                "enabled": enabled,
                "isActive": is_active,
                "activatedAt": activated_at,
            }

        except Exception as e:
            return {"enabled": False, "isActive": False, "error": str(e)}

    async def deactivate_kill_switch(self) -> Dict[str, Any]:
        """
        Manually deactivate kill switch (when user reconnects or disables).

        Returns:
            {
                'success': bool,
                'error': str | None
            }
        """
        try:
            result = await kill_switch.deactivate()

            if result.get("success"):
                kill_switch_pref = settings.getSetting("killSwitch", {})
                kill_switch_pref["isActive"] = False
                kill_switch_pref["deactivatedAt"] = int(time.time())
                settings.setSetting("killSwitch", kill_switch_pref)
                settings.commit()

                # Update connection state if blocked
                connection_state = get_connection_state()
                if connection_state.status == ConnectionStatus.BLOCKED:
                    connection_state.set_disconnected()

                return create_success_response()
            else:
                return create_error_response(
                    ErrorCode.IPTABLES_FAILED,
                    result.get("error", "Failed to deactivate kill switch"),
                )

        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to deactivate kill switch: {str(e)}"
            )

    # System Proxy Management
    async def toggle_system_proxy(self, enabled: bool) -> Dict[str, Any]:
        """
        Toggle system proxy preference. When enabled, configures system to use
        local SOCKS/HTTP proxy (gsettings for GNOME, kwriteconfig5 for KDE).

        Args:
            enabled: True to enable, False to disable

        Returns:
            {
                'success': bool,
                'enabled': bool,
                'error': str | None
            }
        """
        try:
            system_proxy_pref = settings.getSetting("systemProxy", {})

            if enabled:
                # Check if connected - system proxy only works when xray is running
                connection_state = get_connection_state()
                if connection_state.status != ConnectionStatus.CONNECTED:
                    return create_error_response(
                        ErrorCode.NOT_CONNECTED,
                        "System proxy requires active connection. Please connect first.",
                    )

                # Set system proxy (SOCKS 10808, HTTP 10809)
                result = await system_proxy_manager.set_system_proxy(
                    socks_port=10808, http_port=10809
                )

                if not result.get("success"):
                    return create_error_response(
                        ErrorCode.UNKNOWN_ERROR,
                        result.get("error", "Failed to set system proxy"),
                    )

                system_proxy_pref["enabled"] = True
                system_proxy_pref["lastEnabledAt"] = int(time.time())
                system_proxy_pref["socksPort"] = 10808
                system_proxy_pref["httpPort"] = 10809
            else:
                # Clear system proxy
                await system_proxy_manager.clear_system_proxy()
                system_proxy_pref["enabled"] = False
                system_proxy_pref["lastDisabledAt"] = int(time.time())

            settings.setSetting("systemProxy", system_proxy_pref)
            settings.commit()

            return create_success_response(
                {
                    "enabled": enabled,
                    "socksPort": 10808 if enabled else None,
                    "httpPort": 10809 if enabled else None,
                }
            )

        except Exception as e:
            return create_error_response(
                ErrorCode.UNKNOWN_ERROR, f"Failed to toggle system proxy: {str(e)}"
            )

    async def get_system_proxy_status(self) -> Dict[str, Any]:
        """
        Get system proxy preference and status.

        Returns:
            {
                'enabled': bool,
                'isActive': bool,
                'socksPort': int | None,
                'httpPort': int | None
            }
        """
        try:
            system_proxy_pref = settings.getSetting("systemProxy", {})
            enabled = system_proxy_pref.get("enabled", False)

            # Get actual status from manager
            manager_status = system_proxy_manager.get_status()
            is_active = manager_status.get("isActive", False)

            return {
                "enabled": enabled,
                "isActive": is_active,
                "socksPort": manager_status.get("socksPort"),
                "httpPort": manager_status.get("httpPort"),
                "address": manager_status.get("address"),
            }

        except Exception as e:
            return {"enabled": False, "isActive": False, "error": str(e)}

    # ================================================================
    # Xray-core Update Management
    # ================================================================

    async def check_xray_update(self) -> Dict[str, Any]:
        """
        Check whether a newer Xray-core version is available on GitHub.

        Returns:
            {
                'success': bool,
                'installed': str | None,     # e.g. 'v26.2.6'
                'latest': str,               # e.g. 'v26.3.27'
                'updateAvailable': bool,
                'downloadUrl': str | None,
                'releaseUrl': str,
                'assetSize': int
            }
        """
        return await xray_downloader.check_update()

    async def get_xray_version(self) -> Dict[str, Any]:
        """
        Return the currently installed/active Xray-core version.

        This is a fast, fully-local call (it just runs ``xray-core version``)
        with no network access, so it is safe to call on every panel render
        to show a persistent "installed version" indicator.

        Returns:
            {
                'success': bool,
                'installed': str | None,   # e.g. 'v25.5.16', None if missing
            }
        """
        try:
            installed = await xray_downloader.get_installed_version()
            return {"success": True, "installed": installed}
        except Exception as e:
            return {"success": False, "installed": None, "error": str(e)}

    async def download_xray_latest(self) -> Dict[str, Any]:
        """
        Download and install the latest Xray-core release from GitHub.

        Downloads ``Xray-linux-64.zip``, extracts ``xray-core``,
        ``geoip.dat``, and ``geosite.dat`` into the plugin's ``bin/``
        directory.  After successful download, the XrayManager binary
        path is updated to point to the new binary.

        Returns:
            {
                'success': bool,
                'version': str,           # e.g. 'v26.3.27'
                'installedVersion': str,  # verified version string
                'error': str | None
            }
        """
        result = await xray_downloader.download_latest()
        if result.get("success"):
            # Update the manager's binary path to the newly downloaded binary
            new_path = _resolve_xray_path(PLUGIN_DIR)
            xray_manager.xray_binary_path = new_path
        return result

    async def download_xray_version(self, version: str) -> Dict[str, Any]:
        """
        Download and install a specific Xray-core version from GitHub.

        Args:
            version: Version tag (e.g. 'v26.3.27' or '26.3.27')

        Returns:
            Same format as download_xray_latest
        """
        result = await xray_downloader.download_version(version)
        if result.get("success"):
            new_path = _resolve_xray_path(PLUGIN_DIR)
            xray_manager.xray_binary_path = new_path
        return result

    async def list_xray_releases(self) -> Dict[str, Any]:
        """
        List recent Xray-core releases available on GitHub.

        Returns:
            {
                'success': bool,
                'releases': [
                    {'tag': 'v26.3.27', 'name': '...', 'date': '...', 'url': '...'},
                    ...
                ]
            }
        """
        return await xray_downloader.list_releases()
