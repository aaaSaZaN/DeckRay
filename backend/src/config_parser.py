"""
VLESS / Hysteria2 / Subscription Configuration Parser

Parses and validates VLESS URLs, Hysteria2 URLs, and subscription sources.

Supported subscription formats:
  1. HTTPS URL  → fetches content, then parses as (2) or (3)
  2. Base64-encoded text with one vless:// or hy2:// link per line
  3. JSON array of full xray-core configs (native JSON subscription)
"""

import re
import base64
import json
import time
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

import aiohttp


# VLESS URL pattern: vless://uuid@host:port?params#name
VLESS_URL_PATTERN = re.compile(
    r"^vless://([a-f0-9-]{36})@([^:]+):(\d+)/?(\?[^#]*)?(#.*)?$", re.IGNORECASE
)

# Hysteria2 URL pattern: hy2://password@host:port?params#name
# Password can contain any URL-safe characters (letters, digits, -, _, ., ~)
HYSTERIA2_URL_PATTERN = re.compile(
    r"^(?:hy2|hysteria2)://([^@]+)@([^:]+):(\d+)/?(\?[^#]*)?(#.*)?$", re.IGNORECASE
)



# ---------------------------------------------------------------------------
# Auto-generated server descriptions
#
# When a host has no ``serverDescription`` we build a short, human-readable
# label following a strict rule:
#
#     PROTOCOL / TRANSPORT / SECURITY
#
# e.g. "VLESS / WS / Reality", "VLESS / TCP / None", "Hysteria2 / QUIC / TLS".
# ---------------------------------------------------------------------------

# Friendly transport labels (xray network/transport name -> display name)
_TRANSPORT_LABELS = {
    "tcp": "TCP",
    "raw": "TCP",
    "ws": "WS",
    "websocket": "WS",
    "grpc": "gRPC",
    "gun": "gRPC",
    "h2": "HTTP/2",
    "http": "HTTP/2",
    "kcp": "mKCP",
    "mkcp": "mKCP",
    "quic": "QUIC",
    "httpupgrade": "HTTPUpgrade",
    "splithttp": "XHTTP",
    "xhttp": "XHTTP",
}

# Friendly security labels (xray security name -> display name)
_SECURITY_LABELS = {
    "": "None",
    "none": "None",
    "reality": "Reality",
    "tls": "TLS",
    "xtls": "XTLS",
}

# Friendly protocol labels (xray outbound protocol -> display name)
_PROTOCOL_LABELS = {
    "vless": "VLESS",
    "vmess": "VMess",
    "trojan": "Trojan",
    "hysteria2": "Hysteria2",
    "hysteria": "Hysteria",
    "shadowsocks": "Shadowsocks",
    "ss": "Shadowsocks",
    "socks": "SOCKS",
    "http": "HTTP",
}


def _transport_label(network: Optional[str]) -> str:
    """Map an xray network/transport name to a display label (default TCP)."""
    net = (network or "tcp").strip().lower()
    if not net:
        return "TCP"
    return _TRANSPORT_LABELS.get(net, net.upper())


def _security_label(security: Optional[str]) -> str:
    """Map an xray security name to a display label (default None)."""
    sec = (security or "none").strip().lower()
    if not sec:
        return "None"
    return _SECURITY_LABELS.get(sec, sec.capitalize())


def _protocol_label(protocol: Optional[str]) -> str:
    """Map an xray outbound protocol to a display label."""
    proto = (protocol or "").strip().lower()
    if not proto or proto == "unknown":
        return "JSON"
    return _PROTOCOL_LABELS.get(proto, proto.upper())


def build_auto_description(
    protocol_label: str,
    network: Optional[str],
    security: Optional[str],
) -> str:
    """
    Build a ``PROTOCOL / TRANSPORT / SECURITY`` description string.

    All three parts are always present, e.g. ``VLESS / TCP / None``.
    """
    return " / ".join(
        [
            protocol_label,
            _transport_label(network),
            _security_label(security),
        ]
    )


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID v4 format.

    Args:
        uuid_string: UUID string to validate

    Returns:
        True if valid UUID v4, False otherwise
    """
    try:
        uuid_obj = UUID(uuid_string, version=4)
        return str(uuid_obj).lower() == uuid_string.lower()
    except (ValueError, AttributeError):
        return False


def validate_port(port: int) -> bool:
    """
    Validate port number.

    Args:
        port: Port number to validate

    Returns:
        True if port is in valid range (1-65535), False otherwise
    """
    try:
        port_int = int(port)
        return 1 <= port_int <= 65535
    except (ValueError, TypeError):
        return False


def validate_hostname(hostname: str) -> bool:
    """
    Basic hostname/IP validation.

    Args:
        hostname: Hostname or IP address to validate

    Returns:
        True if hostname looks valid, False otherwise
    """
    if not hostname or len(hostname) > 253:
        return False

    # Basic IP address validation (IPv4)
    ipv4_pattern = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
    if ipv4_pattern.match(hostname):
        parts = hostname.split(".")
        return all(0 <= int(part) <= 255 for part in parts)

    # Basic hostname validation (simplified)
    hostname_pattern = re.compile(
        r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$",
        re.IGNORECASE,
    )
    return bool(hostname_pattern.match(hostname))


def parse_vless_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single VLESS URL into components.

    Args:
        url: VLESS URL string (vless://uuid@host:port?params#name)

    Returns:
        Dictionary with parsed components, or None if invalid
    """
    match = VLESS_URL_PATTERN.match(url.strip())
    if not match:
        return None

    uuid_str = match.group(1)
    host = match.group(2)
    port_str = match.group(3)
    params_str = match.group(4) or ""
    name_fragment = match.group(5) or ""

    # Validate UUID
    if not validate_uuid(uuid_str):
        return None

    # Validate port
    try:
        port = int(port_str)
        if not validate_port(port):
            return None
    except ValueError:
        return None

    # Validate hostname
    if not validate_hostname(host):
        return None

    # Parse query parameters
    params = {}
    if params_str.startswith("?"):
        params_str = params_str[1:]

    if params_str:
        for param in params_str.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[urllib.parse.unquote(key)] = urllib.parse.unquote(value)

    # Extract name from fragment or query string %23 fallback
    name = None
    if name_fragment.startswith("#"):
        name = urllib.parse.unquote(name_fragment[1:])
    else:
        # Check if %23 is hidden in params
        for k, v in params.items():
            if "%23" in v:
                parts = v.split("%23", 1)
                params[k] = urllib.parse.unquote(parts[0])
                name = urllib.parse.unquote(parts[1])
            elif "#" in v:
                parts = v.split("#", 1)
                params[k] = urllib.parse.unquote(parts[0])
                name = urllib.parse.unquote(parts[1])

    # Some providers embed ?serverDescription= inside the fragment
    if name and "?" in name:
        base_name, fragment_qs = name.split("?", 1)
        name = base_name
        for param in fragment_qs.split("&"):
            if "=" in param:
                k, v = param.split("=", 1)
                params[k] = v

    if not name:
        name = f"{host}:{port}"

    return {
        "uuid": uuid_str.lower(),
        "address": host,
        "port": port,
        "params": params,
        "name": name,
    }


# ---------------------------------------------------------------------------
# Subscription parsing — supports 3 content formats
# ---------------------------------------------------------------------------

# User-Agent sent when fetching HTTPS subscription URLs.
# Mimics Happ/v2rayN clients so the server returns the right format.
SUBSCRIPTION_USER_AGENT = "Happ/1.0 (SteamOS; deckray)"

_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


async def fetch_subscription_url(
    url: str,
    custom_headers: Optional[str] = None,
    allow_insecure: bool = False
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Fetch subscription content from an HTTPS URL.

    Args:
        url: HTTPS subscription URL
        custom_headers: Optional raw HTTP headers (e.g., "Header-Name: Value")
        allow_insecure: If True, skips SSL verification (used after user prompt).

    Returns:
        Tuple of (content_string, error_message, metadata_dict).
        On success error_message is None; on failure content is None.
    """
    headers = {
        "User-Agent": SUBSCRIPTION_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    if custom_headers:
        for line in custom_headers.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
            elif "=" in line:
                k, v = line.split("=", 1)
                headers[k.strip()] = v.strip()
            else:
                headers[line] = "1"

    metadata = {}
    try:
        async with aiohttp.ClientSession(timeout=_FETCH_TIMEOUT) as session:
            try:
                async with session.get(url, headers=headers, ssl=not allow_insecure) as resp:
                    if resp.status != 200:
                        return None, f"HTTP {resp.status} from subscription server", metadata
                    
                    profile_title = resp.headers.get("profile-title")
                    if profile_title:
                        if profile_title.startswith("base64:"):
                            try:
                                metadata["profile-title"] = base64.b64decode(profile_title[7:]).decode("utf-8")
                            except Exception:
                                metadata["profile-title"] = profile_title[7:]
                        else:
                            metadata["profile-title"] = profile_title
                            
                    update_interval = resp.headers.get("profile-update-interval")
                    if update_interval and update_interval.isdigit():
                        metadata["profile-update-interval"] = int(update_interval)
                        
                    announce = resp.headers.get("announce")
                    if announce:
                        if announce.startswith("base64:"):
                            try:
                                enc = announce[7:].strip().replace('\n', '').replace('\r', '')
                                padded = enc + "=" * (-len(enc) % 4)
                                metadata["announce"] = base64.b64decode(padded).decode("utf-8")
                            except Exception:
                                metadata["announce"] = announce[7:]
                        else:
                            metadata["announce"] = announce

                    body = await resp.text(encoding="utf-8")
                    if not body or not body.strip():
                        return None, "Subscription server returned empty response", metadata
                    return body.strip(), None, metadata
            except Exception as ssl_exc:
                exc_str = str(ssl_exc).lower()
                if "ssl" in exc_str or "cert" in exc_str or "verify" in exc_str:
                    if not allow_insecure:
                        return None, "SSL_ERROR", metadata
                    else:
                        return None, f"SSL error even with allow_insecure: {ssl_exc}", metadata
                else:
                    raise ssl_exc
    except aiohttp.ClientError as exc:
        return None, f"Failed to fetch subscription: {exc}", metadata
    except Exception as exc:
        return None, f"Unexpected error fetching subscription: {exc}", metadata


def parse_subscription_content(content: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Parse subscription content in any of the supported formats.

    Supported formats (auto-detected):
      1. **Native JSON configs** — a JSON array where each element is a
         full xray-core config dict with ``outbounds``, ``remarks`` etc.
         (used by Happ, v2rayN JSON subscriptions, and panel APIs).
      2. **Base64-encoded link list** — standard format used by most
         subscription services.  Each line after decoding is a
         ``vless://`` or ``hy2://`` URL.
      3. **Plain-text link list** — one ``vless://`` or ``hy2://`` URL
         per line (no base64 encoding).

    Args:
        content: Raw subscription content string

    Returns:
        Tuple of (parsed_configs_list, format_detected).
        parsed_configs_list may be empty if nothing could be parsed.
        format_detected is one of: 'json', 'base64', 'plaintext', 'unknown'.
    """
    content = content.strip()

    # --- Try 1: Native JSON array of xray-core configs ---
    try:
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            # Check if elements are full xray-core config dicts
            first = data[0]
            if isinstance(first, dict) and "outbounds" in first:
                # Native JSON subscription!
                return data, "json"
            # Could be a JSON array of URL strings
            if isinstance(first, str):
                parsed = _parse_link_list(data)
                if parsed:
                    return parsed, "json"
    except (json.JSONDecodeError, TypeError):
        pass

    # --- Try 2: Plain-text links (vless://, hy2://) ---
    if content.startswith("vless://") or content.startswith("hy2://") or content.startswith("hysteria2://"):
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        parsed = _parse_link_list(lines)
        if parsed:
            return parsed, "plaintext"

    # --- Try 3: Base64-encoded content ---
    try:
        clean = content.replace('\n', '').replace('\r', '').replace(' ', '')
        padded = clean + "=" * (-len(clean) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")

        # Decoded could be JSON (rare) or line-separated links
        try:
            data = json.loads(decoded)
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict) and "outbounds" in first:
                    return data, "base64"
                if isinstance(first, str):
                    parsed = _parse_link_list(data)
                    if parsed:
                        return parsed, "base64"
        except (json.JSONDecodeError, TypeError):
            pass

        # Line-separated links after base64 decode
        lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]
        if lines:
            parsed = _parse_link_list(lines)
            if parsed:
                return parsed, "base64"
    except (base64.binascii.Error, UnicodeDecodeError, ValueError):
        pass

    return [], "unknown"


def _parse_link_list(links: List[str]) -> List[Dict[str, Any]]:
    """Parse a list of vless:// and hy2:// URL strings into config dicts."""
    results: List[Dict[str, Any]] = []
    for link in links:
        if not isinstance(link, str):
            continue
        link = link.strip()
        parsed = parse_vless_url(link)
        if parsed:
            parsed["_sourceLink"] = link
            results.append(parsed)
            continue
        parsed = parse_hysteria2_url(link)
        if parsed:
            parsed["_sourceLink"] = link
            parsed["_protocol"] = "hysteria2"
            results.append(parsed)
    return results


def parse_subscription_url(content: str) -> List[Dict[str, Any]]:
    """
    Parse subscription content (backward-compatible wrapper).

    Supports base64-encoded link lists, JSON arrays, and plain-text links.

    Args:
        content: Subscription content (base64, JSON, or plain-text)

    Returns:
        List of parsed configurations, empty list if invalid
    """
    configs, fmt = parse_subscription_content(content)
    return configs


def parse_hysteria2_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Parse a Hysteria2 URL into components.

    Format: hy2://password@host:port?params#name

    Args:
        url: Hysteria2 URL string

    Returns:
        Dictionary with parsed components, or None if invalid
    """
    match = HYSTERIA2_URL_PATTERN.match(url.strip())
    if not match:
        return None

    password = urllib.parse.unquote(match.group(1))
    host = match.group(2)
    port_str = match.group(3)
    params_str = match.group(4) or ""
    name_fragment = match.group(5) or ""

    # Validate port
    try:
        port = int(port_str)
        if not validate_port(port):
            return None
    except ValueError:
        return None

    # Validate hostname
    if not validate_hostname(host):
        return None

    # Parse query parameters
    params = {}
    if params_str.startswith("?"):
        params_str = params_str[1:]
    if params_str:
        for param in params_str.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[urllib.parse.unquote(key)] = urllib.parse.unquote(value)

    # Extract name from fragment
    name = None
    if name_fragment.startswith("#"):
        name = urllib.parse.unquote(name_fragment[1:])
    else:
        for k, v in params.items():
            if "%23" in v:
                parts = v.split("%23", 1)
                params[k] = urllib.parse.unquote(parts[0])
                name = urllib.parse.unquote(parts[1])
            elif "#" in v:
                parts = v.split("#", 1)
                params[k] = urllib.parse.unquote(parts[0])
                name = urllib.parse.unquote(parts[1])

    # Some providers embed ?serverDescription= inside the fragment
    if name:
        if "?" in name:
            base_name, fragment_qs = name.split("?", 1)
            name = base_name
            for param in fragment_qs.split("&"):
                if "=" in param:
                    k, v = param.split("=", 1)
                    params[k] = v
        # Handle cases where the URL doesn't use ? and just appends ServerDescription
        # which can happen with base64 decoded subscriptions
        if " serverDescription " in name or " ServerDescription " in name:
            idx = name.lower().find(" serverdescription ")
            if idx != -1:
                base_name = name[:idx].strip()
                desc_value = name[idx + len(" serverdescription "):].strip()
                name = base_name
                params["serverDescription"] = desc_value

    if not name:
        name = f"hy2_{host}:{port}"

    return {
        "password": password,
        "address": host,
        "port": port,
        "params": params,
        "name": name,
    }


def validate_vless_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a VLESS URL, Hysteria2 URL, subscription content, or HTTPS
    subscription URL.

    Accepted inputs:
      - ``vless://...`` single node URL
      - ``hy2://...`` or ``hysteria2://...`` single node URL
      - ``https://...`` subscription URL (will be fetched by the caller)
      - Base64-encoded subscription content
      - JSON array subscription content

    Args:
        url: Input to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "Invalid URL format"

    url = url.strip()

    # HTTPS subscription URL — accepted for async fetch by the caller
    if url.startswith("https://") or url.startswith("http://"):
        return True, None

    # Try VLESS single node
    parsed = parse_vless_url(url)
    if parsed:
        return True, None

    # Try Hysteria2
    parsed_hy2 = parse_hysteria2_url(url)
    if parsed_hy2:
        return True, None

    # Try subscription content (base64, JSON, plain-text links)
    parsed_configs = parse_subscription_url(url)
    if parsed_configs:
        return True, None

    # If nothing matches, return error
    return (
        False,
        "Invalid URL format. Expected vless://..., hy2://..., https://... subscription, or base64 content",
    )


def build_vless_config(
    parsed: Dict[str, Any], source_url: str, config_type: str
) -> Dict[str, Any]:
    """
    Build a complete VLESSConfig dictionary from parsed components.

    Args:
        parsed: Parsed URL components
        source_url: Original source URL
        config_type: 'single' or 'subscription'

    Returns:
        Complete VLESSConfig dictionary
    """
    import time

    config = {
        "sourceUrl": source_url,
        "configType": config_type,
        "uuid": parsed["uuid"],
        "address": parsed["address"],
        "port": parsed["port"],
        "name": parsed.get("name"),
        "importedAt": int(time.time()),
        "isValid": True,
    }

    # Extract optional fields from params
    params = parsed.get("params", {})
    if "flow" in params:
        config["flow"] = params["flow"]
    
    server_desc = params.get("serverDescription", "")
    if not server_desc.startswith("base64:") and server_desc:
        # If it doesn't have a prefix but is raw base64 (which happens often in query params)
        if len(server_desc) % 4 == 0 or "=" in server_desc:
            # Let's try decoding it as base64 implicitly just in case
            try:
                base64.b64decode(server_desc).decode("utf-8")
                server_desc = "base64:" + server_desc
            except Exception:
                pass
    
    if server_desc.startswith("base64:"):
        try:
            enc = server_desc[7:].strip().replace('\n', '').replace('\r', '')
            padded = enc + "=" * (-len(enc) % 4)
            server_desc = base64.b64decode(padded).decode("utf-8")
        except Exception:
            server_desc = params.get("serverDescription", "")
            
    if server_desc:
        config["serverDescription"] = server_desc
    if "encryption" in params:
        config["encryption"] = params["encryption"]
    if "type" in params or "network" in params:
        config["network"] = params.get("type") or params.get("network")
    if "security" in params:
        config["security"] = params["security"]

    # Extract Reality-specific fields
    if config.get("security") == "reality":
        reality_config = {}
        if "pbk" in params or "publicKey" in params:
            reality_config["publicKey"] = params.get("pbk") or params.get("publicKey")
        if "sid" in params or "shortId" in params:
            reality_config["shortId"] = params.get("sid") or params.get("shortId")
        if "sni" in params or "serverName" in params:
            reality_config["serverName"] = params.get("sni") or params.get("serverName")
        if "fp" in params or "fingerprint" in params:
            reality_config["fingerprint"] = params.get("fp") or params.get(
                "fingerprint"
            )

        if reality_config:
            config["realityConfig"] = reality_config

    # Extract transport-specific parameters (WebSocket, gRPC, HTTP/2, etc.)
    # These are parsed from the VLESS URL query string and passed through
    # to xray_manager._build_xray_config for stream settings generation.
    network = config.get("network", "tcp")

    if network == "ws":
        # WebSocket: path and Host header are critical for CDN-proxied setups
        ws_path = params.get("path", "/")
        ws_host = params.get("host", "")
        config["wsPath"] = ws_path
        if ws_host:
            config["wsHost"] = ws_host

    if network == "grpc":
        # gRPC: serviceName is required for gRPC transport
        service_name = params.get("serviceName", "")
        if service_name:
            config["grpcServiceName"] = service_name

    if network == "h2" or network == "http":
        # HTTP/2: path and host
        h2_path = params.get("path", "/")
        h2_host = params.get("host", "")
        config["h2Path"] = h2_path
        if h2_host:
            config["h2Host"] = h2_host

    # Extract name
    if parsed.get("name"):
        config["name"] = parsed["name"]

    # Auto-generate serverDescription if not provided:
    # PROTOCOL / TRANSPORT / SECURITY (e.g. "VLESS / WS / Reality").
    if not config.get("serverDescription"):
        config["serverDescription"] = build_auto_description(
            "VLESS",
            config.get("network", "tcp"),
            config.get("security", "none"),
        )

    return config


def build_hysteria2_config(
    parsed: Dict[str, Any], source_url: str, config_type: str
) -> Dict[str, Any]:
    """
    Build a Hysteria2Config dictionary from parsed Hysteria2 URL components.

    The returned dict uses ``protocol: "hysteria2"`` so the XrayManager
    can dispatch to the correct outbound builder.

    Args:
        parsed: Parsed Hysteria2 URL components (from parse_hysteria2_url)
        source_url: Original source URL
        config_type: 'single' or 'subscription'

    Returns:
        Complete Hysteria2Config dictionary
    """
    import time

    params = parsed.get("params", {})

    config: Dict[str, Any] = {
        "protocol": "hysteria2",
        "sourceUrl": source_url,
        "configType": config_type,
        "password": parsed["password"],
        "address": parsed["address"],
        "port": parsed["port"],
        "name": parsed.get("name"),
        "importedAt": int(time.time()),
        "isValid": True,
    }

    # SNI / serverName
    sni = params.get("sni") or params.get("serverName")
    if sni:
        config["sni"] = sni

    # Fingerprint (uTLS)
    fp = params.get("fp") or params.get("fingerprint")
    if fp:
        config["fingerprint"] = fp

    # ALPN
    alpn = params.get("alpn")
    if alpn:
        config["alpn"] = alpn.split(",") if "," in alpn else [alpn]

    # Obfuscation (salamander)
    obfs = params.get("obfs")
    if obfs:
        config["obfs"] = obfs
        obfs_pw = params.get("obfs-password") or params.get("obfsPassword")
        if obfs_pw:
            config["obfsPassword"] = obfs_pw

    # Bandwidth hints
    up = params.get("up") or params.get("up_mbps")
    down = params.get("down") or params.get("down_mbps")
    if up:
        config["up_mbps"] = up
    if down:
        config["down_mbps"] = down

    # Name
    if parsed.get("name"):
        config["name"] = parsed["name"]

    # Extract optional fields from params (like serverDescription)
    server_desc = params.get("serverDescription", "") or params.get("ServerDescription", "")
    if not server_desc.startswith("base64:") and server_desc:
        if len(server_desc) % 4 == 0 or "=" in server_desc:
            try:
                import base64
                base64.b64decode(server_desc).decode("utf-8")
                server_desc = "base64:" + server_desc
            except Exception:
                pass

    if server_desc.startswith("base64:"):
        try:
            import base64
            enc = server_desc[7:].strip().replace('\n', '').replace('\r', '')
            padded = enc + "=" * (-len(enc) % 4)
            server_desc = base64.b64decode(padded).decode("utf-8")
        except Exception:
            server_desc = params.get("serverDescription", "") or params.get("ServerDescription", "")

    if server_desc:
        config["serverDescription"] = server_desc

    # Auto-generate serverDescription if not provided:
    # PROTOCOL / TRANSPORT / SECURITY. Hysteria2 always runs over QUIC with
    # mandatory TLS, so transport/security are fixed for this protocol.
    if not config.get("serverDescription"):
        config["serverDescription"] = build_auto_description(
            "Hysteria2", "quic", "tls"
        )

    return config


def build_native_json_config(
    raw_config: Dict[str, Any],
    source_url: str,
    config_type: str,
    index: int = 0,
) -> Dict[str, Any]:
    """
    Build an internal config from a native JSON xray-core subscription entry.

    Native JSON subscriptions (used by Happ, v2rayN, and panel APIs) return
    full xray-core configs with ``outbounds``, ``routing``, ``dns`` etc.
    We store the *entire* raw config under the key ``nativeConfig`` so the
    XrayManager can use it verbatim instead of constructing one from parts.

    We also extract display metadata (name, address, protocol) for the UI.

    Args:
        raw_config: One element from the JSON subscription array
        source_url: Original subscription URL
        config_type: 'subscription'
        index: Index of this config in the subscription array

    Returns:
        Internal config dictionary compatible with settings storage
    """
    outbounds = raw_config.get("outbounds", [])
    proxy_outbound = None
    for ob in outbounds:
        tag = ob.get("tag", "")
        proto = ob.get("protocol", "")
        if tag == "proxy" or proto in ("vless", "vmess", "trojan", "hysteria2", "hysteria", "shadowsocks"):
            proxy_outbound = ob
            break
    if not proxy_outbound and outbounds:
        proxy_outbound = outbounds[0]

    # Extract display info
    remarks = raw_config.get("remarks", "")
    meta = raw_config.get("meta", {})
    protocol = proxy_outbound.get("protocol", "unknown") if proxy_outbound else "unknown"

    # Extract transport / security from the outbound stream settings so the
    # auto-generated description can follow the PROTOCOL / TRANSPORT / SECURITY
    # rule (e.g. "VLESS / WS / Reality").
    stream_settings = proxy_outbound.get("streamSettings", {}) if proxy_outbound else {}
    native_network = stream_settings.get("network") or stream_settings.get("transport")
    native_security = stream_settings.get("security")

    address = ""
    port = 443
    if proxy_outbound:
        settings = proxy_outbound.get("settings", {})
        vnext = settings.get("vnext", [])
        if vnext:
            address = vnext[0].get("address", "")
            port = vnext[0].get("port", 443)
        servers = settings.get("servers", [])
        if servers and not address:
            address = servers[0].get("address", "")
            port = servers[0].get("port", 443)
        if not address:
            address = settings.get("address", "")
            port = settings.get("port", port)

    server_desc = meta.get("serverDescription", "")
    if server_desc.startswith("base64:"):
        try:
            enc = server_desc[7:].strip().replace('\n', '').replace('\r', '')
            padded = enc + "=" * (-len(enc) % 4)
            server_desc = base64.b64decode(padded).decode("utf-8")
        except Exception:
            pass

    config: Dict[str, Any] = {
        "protocol": "native_json",
        "sourceUrl": source_url,
        "configType": config_type,
        "address": address,
        "port": port,
        "name": remarks or f"{protocol}@{address}:{port}",
        "serverDescription": server_desc,
        "importedAt": int(time.time()),
        "isValid": True,
        "nativeProtocol": protocol,
        "nativeConfig": raw_config,
        "subscriptionIndex": index,
    }

    # Auto-generate serverDescription if empty:
    # PROTOCOL / TRANSPORT / SECURITY (e.g. "VLESS / gRPC / TLS").
    if not config.get("serverDescription"):
        config["serverDescription"] = build_auto_description(
            _protocol_label(protocol),
            native_network,
            native_security,
        )

    return config
