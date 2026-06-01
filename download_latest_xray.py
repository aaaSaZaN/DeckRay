import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path("./backend/src").resolve()))
from xray_downloader import XrayDownloader

async def main():
    out_dir = Path("./backend/out").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    downloader = XrayDownloader(plugin_dir=out_dir.parent)
    downloader._bin_dir = out_dir
    print("Checking update...")
    result = await downloader.download_latest()
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
