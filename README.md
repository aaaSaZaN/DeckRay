# DeckRay

[🇷🇺 Читать на русском языке](README.ru.md)

Clean and powerful Decky Loader plugin for Steam Deck that enables VLESS and Hysteria2 proxy connections with Reality protocol and advanced routing.

---

## Features

- **Import Configurations** — via URL (single node or subscription) and QR Code.
- **Connection Toggle** — turn the proxy on/off directly from the Quick Access Menu in Gaming Mode.
- **TUN Mode** — routes all system and game traffic automatically by default. No manual setup required.
- **Kill Switch** — blocks traffic when proxy unexpectedly disconnects (optional).
- **Auto-Updates** — supports automatic update checks and installation of xray-core.

---

## Installation

### Method 1: Desktop Installer (Primary & Easiest) ✅

> [!IMPORTANT]
> **Sudo Password Required:** This desktop installer script requires a `sudo` (admin) password on your Steam Deck to copy files and restart Decky.
> If you haven't set a password yet:
> 1. Open the **Konsole** app in Desktop Mode.
> 2. Type `passwd` and press **Enter**.
> 3. Enter your new password and press **Enter** (note: characters will *not* show on the screen as you type).
> 4. Retype the password to confirm.

Double-click the installer directly in Steam Deck Desktop Mode!
1. Download [Install-DeckRay.desktop](https://raw.githubusercontent.com/aaaSaZaN/DeckRay/main/scripts/Install-DeckRay.desktop) to your Steam Deck.
2. Right-click the file → **Properties** → **Permissions** tab → check **Is executable**.
3. Double-click the file and choose **Run** or **Execute**. The script will automatically download the latest version, install all required assets, and configure system paths.


### Method 2: Manual Installation (No Sudo Password Required) 🔒
*Perfect if you don't have a `sudo` password set and don't want to create one.*
1. Download the [latest release](https://github.com/aaaSaZaN/DeckRay/releases/latest) zip archive.
2. Go to **Decky Loader Settings** → **Developer** → **Install Plugin from URL** (paste the zip link).


---

## How It Works

By default, DeckRay routes all your network traffic system-wide using **TUN mode**. This ensures that Steam, system services, and all your games go through the proxy seamlessly in both Gaming Mode and Desktop Mode. 

Without TUN mode, standard SOCKS/HTTP proxying does not cover games and system services in Gaming Mode because Steam ignores system proxy configurations. With DeckRay, **TUN mode is active automatically out-of-the-box**, requiring no additional configuration.

---

## Development

If you want to modify or compile the project from source code:

### Prerequisites
- Node.js v18+
- pnpm v9+ (mandatory)

### Setup
```bash
# Install frontend dependencies
pnpm install

# Compile the React/TypeScript frontend into dist/
pnpm run build
```

The Python backend runs natively using SteamOS/Decky Loader's pre-installed libraries and does not require installing external python packages.

### Project Structure
Here is an overview of the codebase layout:
```
deckray/
├── backend/
│   ├── src/          # Python backend core (Xray, TUN, Kill Switch, settings)
│   └── static/       # Local web server assets for QR subscription import
├── docs/             # GitHub Pages website and guides
├── scripts/          # One-click desktop installers (.desktop & install.sh)
├── src/              # React / TypeScript frontend for Steam Gaming Mode UI
├── main.py           # Main plugin backend entry point
├── plugin.json       # Decky Loader plugin metadata & permissions
├── package.json      # pnpm dependencies and compilation scripts
└── tsconfig.json     # TypeScript compiler configuration
```


---

## License

MIT — see [LICENSE.md](LICENSE.md).

## Credits

This project is a standalone fork of the original [xray-decky](https://github.com/VadimOnix/xray-decky) project created by [VadimOnix](https://github.com/VadimOnix). Huge thanks to the original author for the solid foundation!

### Built With & Documentation
- [xray-decky Repository](https://github.com/VadimOnix/xray-decky) — original parent plugin repository.
- [xray-core documentation](https://xtls.github.io/) — core proxy backend documentation.
- [Decky Loader Wiki](https://wiki.deckbrew.xyz/) — official documentation for Steam Deck plugin development.


