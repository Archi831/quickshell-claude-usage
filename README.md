# quickshell-claude-usage

A pill widget for [ilyamiro's Quickshell TopBar](https://github.com/ilyamiro/nixos-configuration) that shows your Claude.ai usage limits in real time.

![pill showing 󱙺 51%, expands on hover to show reset times and 7-day usage]

**Normal:** `󱙺 51%` — 5-hour utilization, color-coded (teal → yellow → red)  
**Hover:** `󱙺 51%  1h00m  (26%)  13h20m` — reset times for both windows inline

Refreshes every 3 minutes. Click opens claude.ai.

## Requirements

- [ilyamiro's Quickshell config](https://github.com/ilyamiro/nixos-configuration) installed and running
- Chromium logged into claude.ai (cookies are read from `~/.config/chromium/Default/Cookies`)
- GNOME Keyring running (provides the cookie decryption key — standard on this setup)
- `secret-tool`, `openssl`, `curl`, `python3` — all present by default on the ilyamiro setup

## Install

```bash
git clone https://github.com/Archi831/quickshell-claude-usage
cd quickshell-claude-usage
python3 install.py
```

The script:
1. Checks dependencies
2. Patches `TopBar.qml` with the pill (backs up the original to `TopBar.qml.bak`)
3. Copies `claude_fetch.sh` to the watchers directory
4. Reloads Quickshell via IPC

## Uninstall

```bash
python3 install.py --uninstall
```

Removes all injected code and the fetch script, reloads Quickshell.

## How it works

`claude_fetch.sh` reads your Chromium session cookies (decrypting them with the key from GNOME Keyring), then calls `https://claude.ai/api/organizations/{org}/usage` — the same endpoint the web UI uses. Results are cached for 3 minutes at `/tmp/waybar_claude_cache.json`.

The TopBar patch injects three things into `TopBar.qml`:
- Properties (`claudeFiveHour`, `claudeSevenDay`, reset times, dynamic color)
- A `Process` poller + `Timer` (every 3 min)
- A pill `Rectangle` in `sysLayout`, just before the battery pill

## Compatibility

Tested against ilyamiro's config as of May 2026. The install script anchors on three stable strings in `TopBar.qml`; if a future update moves them it will tell you which anchor failed.
