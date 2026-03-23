# qobuz-rpc
A simple discord rich presence client for qobuz written in Python

Originally Windows-only. Now supports **Windows**, **Mac**, and **Linux** via browser (web player).

> **Linux note:** Qobuz has no native Linux app, so Linux support works through the web player in your browser. Not native, but it works.

## Features
- Album artwork fetched from iTunes API
- Track duration / progress bar in Discord
- Desktop app mode (Windows / Mac)
- Web browser mode (all platforms) via Chrome DevTools Protocol (CDP) or window title scanning

## Setup

Install the required packages:

```
pip install pypresence psutil pywin32 requests
```

> `pywin32` is only needed on Windows. On Linux/Mac you can skip it.

Run with:

```
python qobuz.py
```

On launch it will ask whether you're using the desktop app or the web browser.

## Browser mode (Web / Linux / Mac)

For reliable background tab detection (tab doesn't need to be active), launch Chrome/Brave/Edge with the remote debugging flag:

```
chrome.exe --remote-debugging-port=9222
```

On Windows a shortcut **Chrome (Qobuz RPC)** is automatically created on your Desktop when you first run in web mode.

Without the flag it falls back to scanning window titles, which only works when the Qobuz tab is the active tab.

Supported browsers: Chrome, Chromium, Brave, Firefox, Opera, Opera GX, Edge, Safari.

## TODO
 - ~~Find the Qobuz Endpoint where I get the duration of the track so I can add a xx:xx left or xx:xx elapsed time counter.~~ Done via iTunes API
 - ~~Use an image url directly for album art~~ Done
 - Native Linux support (waiting on Qobuz to release a Linux app)

#### Misc
Originally written by [Lockna](mailto:raphael.ob@protonmail.com) (`Lockna#5599`).
