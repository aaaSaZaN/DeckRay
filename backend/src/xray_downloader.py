"""
Xray Downloader — Downloads and installs Xray-core releases from GitHub.

Fetches the latest (or a specific) release from
https://github.com/XTLS/Xray-core/releases and extracts the correct
platform binary (``Xray-linux-64.zip`` for Steam Deck) into the
plugin's ``bin/`` directory.

All network I/O uses ``aiohttp`` (already a dependency via Decky Loader)
so the download is fully async and won't block the plugin event loop.

Security:
  - GitHub base URL is hardcoded — no dynamic domains.
  - Zip extraction validates paths with os.path.abspath to prevent Zip Slip.
"""

import asyncio
import io
import os
import stat
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

import aiohttp


# ---------------------------------------------------------------------------
# Constants — hardcoded GitHub URLs (auditable, no dynamic domains)
# ---------------------------------------------------------------------------
GITHUB_BASE_URL = "https://github.com/XTLS/Xray-core"
GITHUB_API_BASE = "https://api.github.com/repos/XTLS/Xray-core"

GITHUB_API_LATEST = f"{GITHUB_API_BASE}/releases/latest"
GITHUB_API_RELEASES = f"{GITHUB_API_BASE}/releases"

# Steam Deck runs SteamOS (Arch-based, x86_64).
# The matching asset name in Xray-core releases is ``Xray-linux-64.zip``.
ASSET_NAME = "Xray-linux-64.zip"

# Files we need from the zip (ignore LICENSE, README, etc.)
_REQUIRED_FILES = {"xray", "geoip.dat", "geosite.dat"}

# HTTP request timeout (seconds)
_TIMEOUT = aiohttp.ClientTimeout(total=300, connect=15)


class XrayDownloader:
    """
    Downloads and installs Xray-core from GitHub Releases.

    Usage::

        dl = XrayDownloader(plugin_dir=Path("/home/deck/homebrew/plugins/deckray"))
        info = await dl.check_update()       # -> {"latest": "v26.3.27", "installed": "v26.2.6", ...}
        result = await dl.download_latest()  # -> {"success": True, "version": "v26.3.27"}
    """

    def __init__(self, plugin_dir: Path):
        self._plugin_dir = plugin_dir
        self._bin_dir = plugin_dir / "bin"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_installed_version(self) -> Optional[str]:
        """Return the installed xray-core version string, or None."""
        xray_bin = self._bin_dir / "xray-core"
        if not xray_bin.exists():
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(xray_bin), "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            # First line looks like: "Xray 26.3.27 (Xray, Penetrates Everything.) ..."
            first_line = stdout.decode("utf-8", errors="ignore").strip().split("\n")[0]
            parts = first_line.split()
            if len(parts) >= 2:
                ver = parts[1]
                return f"v{ver}" if not ver.startswith("v") else ver
        except Exception:
            pass
        return None

    async def check_update(self) -> Dict[str, Any]:
        """
        Check whether a newer version is available on GitHub.

        Returns::

            {
                "success": True,
                "installed": "v26.2.6" | None,
                "latest": "v26.3.27",
                "updateAvailable": True,
                "downloadUrl": "https://github.com/…/Xray-linux-64.zip",
                "releaseUrl": "https://github.com/…/releases/tag/v26.3.27",
                "assetSize": 21136402,
            }
        """
        try:
            installed = await self.get_installed_version()
            release = await self._fetch_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Failed to fetch latest release from GitHub",
                    "errorCode": "NETWORK_ERROR",
                }

            tag = release.get("tag_name", "")
            html_url = release.get("html_url", "")
            asset = self._find_asset(release)

            result: Dict[str, Any] = {
                "success": True,
                "installed": installed,
                "latest": tag,
                "releaseUrl": html_url,
            }

            if asset:
                result["downloadUrl"] = asset["browser_download_url"]
                result["assetSize"] = asset.get("size", 0)
            else:
                result["downloadUrl"] = None
                result["assetSize"] = 0

            result["updateAvailable"] = (
                installed is None or installed != tag
            )

            return result

        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to check for updates: {exc}",
                "errorCode": "NETWORK_ERROR",
            }

    async def download_latest(self) -> Dict[str, Any]:
        """
        Download and install the latest Xray-core release.

        Steps:
        1. Fetch latest release metadata from GitHub API.
        2. Find the ``Xray-linux-64.zip`` asset.
        3. Download it into memory.
        4. Extract ``xray``, ``geoip.dat``, ``geosite.dat`` into ``bin/``.
        5. Rename ``xray`` → ``xray-core`` and set executable permission.

        Returns a success/error dict.
        """
        try:
            release = await self._fetch_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Failed to fetch latest release from GitHub",
                    "errorCode": "NETWORK_ERROR",
                }

            tag = release.get("tag_name", "unknown")
            return await self._download_and_install(release, tag)

        except Exception as exc:
            return {
                "success": False,
                "error": f"Download failed: {exc}",
                "errorCode": "NETWORK_ERROR",
            }

    async def download_version(self, version: str) -> Dict[str, Any]:
        """
        Download and install a specific Xray-core version (e.g. ``v26.3.27``).
        """
        try:
            if not version.startswith("v"):
                version = f"v{version}"

            # Hardcoded GitHub API URL — no dynamic domains
            url = f"{GITHUB_API_BASE}/releases/tags/{version}"
            release = await self._fetch_json(url)
            if not release or "tag_name" not in release:
                return {
                    "success": False,
                    "error": f"Release {version} not found on GitHub",
                    "errorCode": "NETWORK_ERROR",
                }

            return await self._download_and_install(release, version)

        except Exception as exc:
            return {
                "success": False,
                "error": f"Download failed: {exc}",
                "errorCode": "NETWORK_ERROR",
            }

    async def list_releases(self, limit: int = 100) -> Dict[str, Any]:
        """
        List Xray-core releases available on GitHub, starting from v25.1.0.

        Returns::

            {
                "success": True,
                "releases": [
                    {"tag": "v26.3.27", "date": "2026-03-27T17:51:11Z", "url": "..."},
                    ...
                ]
            }
        """
        try:
            all_releases = []
            page = 1
            per_page = 100
            while len(all_releases) < limit:
                url = f"{GITHUB_API_RELEASES}?per_page={per_page}&page={page}"
                data = await self._fetch_json(url)
                if not data or not isinstance(data, list) or len(data) == 0:
                    break

                for r in data:
                    tag = r.get("tag_name", "")
                    if self._version_gte(tag, "v25.1.0"):
                        all_releases.append({
                            "tag": tag,
                            "name": r.get("name", ""),
                            "date": r.get("published_at", ""),
                            "url": r.get("html_url", ""),
                            "prerelease": r.get("prerelease", False),
                        })

                # If we got a tag older than v25.1.0, stop paginating
                last_tag = data[-1].get("tag_name", "")
                if not self._version_gte(last_tag, "v25.1.0"):
                    break

                if len(data) < per_page:
                    break
                page += 1

            # GitHub returns releases ordered by publish date, which is not
            # guaranteed to match semantic version order (e.g. a back-ported
            # patch to an older line). Sort strictly by version, newest first,
            # so the dropdown is ordered and releases[0] is the highest version.
            all_releases.sort(key=lambda r: self._parse_ver(r["tag"]), reverse=True)

            return {"success": True, "releases": all_releases[:limit]}

        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to list releases: {exc}",
                "errorCode": "NETWORK_ERROR",
            }

    @staticmethod
    def _parse_ver(tag: str) -> tuple:
        """Parse a version tag like 'v25.1.0' into a comparable tuple (25, 1, 0)."""
        t = (tag or "").lstrip("v")
        parts = []
        for p in t.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    @staticmethod
    def _version_gte(tag: str, min_tag: str) -> bool:
        """Check if version tag >= min_tag. Tags are like 'v25.1.0' or 'v26.3.27'."""
        try:
            return XrayDownloader._parse_ver(tag) >= XrayDownloader._parse_ver(min_tag)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_json(self, url: str) -> Any:
        """GET *url* and parse JSON. Returns None on failure."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "deckray-plugin/1.0",
        }
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=headers, ssl=False) as resp:
                if resp.status != 200:
                    print(f"XrayDownloader: HTTP {resp.status} for {url}")
                    return None
                return await resp.json()

    async def _fetch_latest_release(self) -> Optional[Dict[str, Any]]:
        """Fetch latest non-prerelease from GitHub."""
        return await self._fetch_json(GITHUB_API_LATEST)

    @staticmethod
    def _find_asset(release: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the ``Xray-linux-64.zip`` asset in a release."""
        for asset in release.get("assets", []):
            if asset.get("name") == ASSET_NAME:
                return asset
        return None

    async def _download_and_install(
        self, release: Dict[str, Any], tag: str
    ) -> Dict[str, Any]:
        """Download zip asset and install to bin/."""
        asset = self._find_asset(release)
        if not asset:
            return {
                "success": False,
                "error": f"Asset {ASSET_NAME} not found in release {tag}",
                "errorCode": "NETWORK_ERROR",
            }

        download_url = asset["browser_download_url"]
        asset_size = asset.get("size", 0)

        # Download into memory
        zip_bytes = await self._download_file(download_url)
        if not zip_bytes:
            return {
                "success": False,
                "error": "Failed to download release archive",
                "errorCode": "NETWORK_ERROR",
            }

        # Extract with Zip Slip protection
        try:
            self._extract_and_install(zip_bytes)
        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to extract archive: {exc}",
                "errorCode": "UNKNOWN_ERROR",
            }

        # Verify binary works
        installed = await self.get_installed_version()

        return {
            "success": True,
            "version": tag,
            "installedVersion": installed,
            "assetSize": asset_size,
            "binDir": str(self._bin_dir),
        }

    async def _download_file(self, url: str) -> Optional[bytes]:
        """Download a file (following redirects) and return raw bytes."""
        headers = {"User-Agent": "deckray-plugin/1.0"}
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(url, headers=headers, ssl=False) as resp:
                    if resp.status != 200:
                        print(f"XrayDownloader: HTTP {resp.status} downloading {url}")
                        return None
                    return await resp.read()
        except Exception as exc:
            print(f"XrayDownloader: download error: {exc}")
            return None

    def _extract_and_install(self, zip_bytes: bytes) -> None:
        """
        Extract required files from zip into bin/ directory.

        Security: validates every entry path with os.path.abspath to prevent
        Zip Slip (path traversal) attacks. Any entry that would resolve outside
        bin/ is rejected.
        """
        self._bin_dir.mkdir(parents=True, exist_ok=True)
        bin_dir_resolved = os.path.abspath(str(self._bin_dir))

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                basename = os.path.basename(info.filename)
                if basename not in _REQUIRED_FILES:
                    continue

                # Determine target filename (xray -> xray-core)
                target_name = "xray-core" if basename == "xray" else basename
                target_path = os.path.join(str(self._bin_dir), target_name)

                # --- Zip Slip protection ---
                # Resolve the absolute path and verify it stays within bin/
                abs_target = os.path.abspath(target_path)
                if not abs_target.startswith(bin_dir_resolved + os.sep) and abs_target != bin_dir_resolved:
                    raise ValueError(
                        f"Zip Slip detected: entry '{info.filename}' resolves "
                        f"to '{abs_target}', which is outside '{bin_dir_resolved}'"
                    )

                # Extract file
                data = zf.read(info.filename)
                Path(abs_target).write_bytes(data)

                # Set executable bit for the binary
                if basename == "xray":
                    os.chmod(
                        abs_target,
                        stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP,  # 0o750
                    )

