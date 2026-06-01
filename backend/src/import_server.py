"""
Import HTTP server for VLESS link import via web form.

Serves GET /import (HTML form), GET /import/static/* (CSS/JS), POST /import (validate and store VLESS).
Contract: specs/002-vless-import-qr/contracts/import-http-api.md
"""

import secrets
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from aiohttp import web

from .config_parser import (
    validate_vless_url,
    parse_vless_url,
    parse_hysteria2_url,
    parse_subscription_content,
    fetch_subscription_url,
    build_vless_config,
    build_hysteria2_config,
    build_native_json_config,
)


def generate_import_token() -> str:
    """Generate a URL-safe one-time import token (16 bytes → 22 chars)."""
    return secrets.token_urlsafe(16)


def create_import_app(
    settings,
    static_dir: Path,
    on_vless_saved: Optional[Callable[[], Awaitable[None]]] = None,
    import_token: Optional[str] = None,
) -> web.Application:
    """Create aiohttp app for import page. static_dir: path to backend/static."""
    app = web.Application()
    app["import_token"] = import_token

    async def get_import_page(_request: web.Request) -> web.StreamResponse:
        """GET /import — serve import page HTML. Same form when opened directly (no redirect or auth)."""
        html_path = static_dir / "import.html"
        if not html_path.is_file():
            return web.Response(status=404, text="import.html not found")
        return web.FileResponse(html_path, headers={"Content-Type": "text/html"})

    async def post_import(request: web.Request) -> web.Response:
        """
        POST /import or / — accept VLESS link (form or JSON), validate, store in SettingsManager.
        """
        link = None
        content_type = request.headers.get("Content-Type", "")

        if "application/json" in content_type:
            try:
                body = await request.json()
                link = (body or {}).get("link") or (body or {}).get("vless")
            except Exception:
                return web.json_response(
                    {"success": False, "error": "Invalid JSON body"},
                    status=400,
                )
        else:
            # form: application/x-www-form-urlencoded
            try:
                data = await request.post()
                link = data.get("link") or data.get("vless")
            except Exception:
                return web.json_response(
                    {"success": False, "error": "Invalid form body"},
                    status=400,
                )

        if not link or not isinstance(link, str):
            return web.json_response(
                {"success": False, "error": "Missing or invalid link"},
                status=400,
            )

        link = link.strip()
        if not link:
            return web.json_response(
                {"success": False, "error": "Empty link"},
                status=400,
            )

        is_valid, error_msg = validate_vless_url(link)
        if not is_valid:
            return web.json_response(
                {"success": False, "error": error_msg or "Invalid VLESS URL format"},
                status=400,
            )

        try:
            import uuid
            configs = settings.getSetting("vlessConfigs", [])
            subscriptions = settings.getSetting("subscriptions", [])
            
            sub_id = None
            parsed_configs = []

            # HTTPS subscription URL
            if link.startswith("https://") or link.startswith("http://"):
                content, fetch_error, metadata = await fetch_subscription_url(link, allow_insecure=True)
                if fetch_error:
                    return web.json_response(
                        {"success": False, "error": fetch_error},
                        status=400,
                    )
                parsed_configs, sub_fmt = parse_subscription_content(content)
                if not parsed_configs:
                    return web.json_response(
                        {"success": False, "error": "No valid configs in subscription"},
                        status=400,
                    )
                
                sub_id = str(uuid.uuid4())
                subscriptions.append({
                    "id": sub_id,
                    "url": link,
                    "custom_headers": None,
                    "title": metadata.get("profile-title", link),
                    "update_interval": metadata.get("profile-update-interval", 0),
                    "last_updated": int(time.time())
                })
            else:
                # Inline subscription content (base64/JSON/plain) or single
                parsed_configs, _ = parse_subscription_content(link)
                if not parsed_configs:
                    parsed = parse_vless_url(link)
                    if parsed:
                        config = build_vless_config(parsed, link, "single")
                        parsed_configs = [config]
                    else:
                        parsed_hy2 = parse_hysteria2_url(link)
                        if parsed_hy2:
                            config = build_hysteria2_config(parsed_hy2, link, "single")
                            parsed_configs = [config]

            if not parsed_configs:
                return web.json_response(
                    {"success": False, "error": "Failed to parse link or subscription"},
                    status=400,
                )

            new_configs = []
            for i, first in enumerate(parsed_configs):
                config = None
                if isinstance(first, dict) and "outbounds" in first:
                    config = build_native_json_config(first, link, "subscription" if sub_id else "single", index=i)
                else:
                    source_link = first.get("_sourceLink", link)
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
                
            active = settings.getSetting("activeConfigId", None)
            if not active and new_configs:
                settings.setSetting("activeConfigId", new_configs[0]["id"])
                
            if new_configs:
                settings.setSetting("vlessConfig", new_configs[0])

            settings.commit()

            if on_vless_saved is not None:
                await on_vless_saved()

            return web.json_response(
                {"success": True, "message": f"Saved {len(new_configs)} configs"},
                status=200,
            )
        except Exception as e:
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    app.router.add_get("/", get_import_page)
    app.router.add_post("/", post_import)
    app.router.add_get("/import", get_import_page)
    app.router.add_post("/import", post_import)
    app.router.add_routes([web.static("/import/static", str(static_dir))])

    return app
