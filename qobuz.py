import time
import sys
import requests
from pypresence import Presence
import psutil

IS_WINDOWS = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes
    import win32gui
    import win32process
    GetWindowText       = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible     = ctypes.windll.user32.IsWindowVisible

CLIENT_ID    = "1483417404993175625"
HTTP_HEADERS = {"User-Agent": "QobuzRPC/1.0"}
art_cache    = {}

BROWSER_PATHS = {
    "win32": [
        (r"C:\Program Files\Google\Chrome\Application\chrome.exe",          "chrome"),
        (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",    "chrome"),
        (r"C:\Users\{user}\AppData\Local\Google\Chrome\Application\chrome.exe", "chrome"),
        (r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe", "brave"),
        (r"C:\Users\{user}\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe", "brave"),
        (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",   "edge"),
        (r"C:\Program Files\Opera GX\launcher.exe",                         "operagx"),
        (r"C:\Program Files\Opera\launcher.exe",                            "opera"),
    ],
    "darwin": [
        ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",    "chrome"),
        ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",    "brave"),
        ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",  "edge"),
        ("/Applications/Opera GX.app/Contents/MacOS/Opera GX",              "operagx"),
        ("/Applications/Opera.app/Contents/MacOS/Opera",                    "opera"),
    ],
}

CDP_PORTS        = [9222, 9223, 9224]
QOBUZ_WEB_SUFFIX = "- Qobuz Web Player"
BROWSER_SUFFIXES = [
    " - Google Chrome",
    " - Chromium",
    " - Mozilla Firefox",
    " - Firefox",
    " - Brave",
    " - Opera GX",
    " - Opera",
    " - Microsoft Edge",
    " - Edge",
    " - Safari",
]


def fetch_art_and_duration(song, artist):
    key = f"{song}|{artist}"
    if key in art_cache:
        return art_cache[key]
    try:
        search = requests.utils.quote(f"{song} {artist}")
        url    = f"https://itunes.apple.com/search?term={search}&entity=song&limit=1"
        data   = requests.get(url, headers=HTTP_HEADERS, timeout=5).json()
        if data.get("resultCount", 0) > 0:
            result  = data["results"][0]
            art_url = result.get("artworkUrl100")
            dur_ms  = result.get("trackTimeMillis")
            if art_url:
                art_url = art_url.replace("100x100bb", "512x512bb")
            art_cache[key] = (art_url, dur_ms)
            return art_url, dur_ms
    except Exception as e:
        print(f"  iTunes error: {e}")
    art_cache[key] = (None, None)
    return None, None


def find_qobuz_via_cdp():
    for port in CDP_PORTS:
        try:
            resp = requests.get(
                f"http://localhost:{port}/json",
                timeout=1,
                headers={"User-Agent": "QobuzRPC/1.0"}
            )
            for tab in resp.json():
                title = tab.get("title", "")
                if QOBUZ_WEB_SUFFIX in title:
                    clean = title[: title.rfind(QOBUZ_WEB_SUFFIX)].strip().rstrip("-").strip()
                    if " - " in clean:
                        return clean
        except Exception:
            pass
    return None


def cdp_available():
    for port in CDP_PORTS:
        try:
            requests.get(f"http://localhost:{port}/json", timeout=1)
            return True
        except Exception:
            pass
    return False


def ensure_cdp():
    import subprocess, os
    if cdp_available():
        return True

    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    paths = BROWSER_PATHS.get(sys.platform, [])

    for template, name in paths:
        path = template.replace("{user}", user)
        if not os.path.exists(path):
            continue

        proc_names = {"chrome": "chrome", "brave": "brave", "edge": "msedge",
                      "operagx": "opera", "opera": "opera"}
        running = any(proc_names[name] in p.name().lower()
                      for p in psutil.process_iter() if p.name())

        if running:
            print(f"  {name} is running without CDP. Close it and reopen — or just keep going (window title fallback will be used).")
            return False

        print(f"  Launching {name} with CDP enabled...")
        subprocess.Popen([path, "--remote-debugging-port=9222"])
        time.sleep(3)
        return cdp_available()

    return False


def get_all_window_titles_linux():
    try:
        import subprocess
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name", ""],
            capture_output=True, text=True, timeout=3
        )
        titles = []
        for wid in result.stdout.strip().split():
            r = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True, timeout=1
            )
            t = r.stdout.strip()
            if t:
                titles.append(t)
        return titles
    except Exception as e:
        print(f"  xdotool error: {e}")
        return []


def get_all_window_titles_windows():
    titles = []
    def callback(hwnd, _):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buf, length + 1)
                t = buf.value.strip()
                if t:
                    titles.append(t)
        return True
    win32gui.EnumWindows(callback, None)
    return titles


def get_all_window_titles_mac():
    browsers = ["Google Chrome", "Firefox", "Safari", "Brave Browser",
                "Opera", "Opera GX", "Microsoft Edge"]
    titles = []
    try:
        import subprocess
        for browser in browsers:
            script = f'''
            tell application "{browser}"
                if it is running then
                    repeat with w in windows
                        repeat with t in tabs of w
                            set tTitle to title of t
                            if tTitle is not missing value then
                                set titles to titles & tTitle
                            end if
                        end repeat
                    end repeat
                end if
            end tell
            '''
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=3)
            for line in r.stdout.strip().split(", "):
                t = line.strip()
                if t:
                    titles.append(t)
    except Exception:
        pass
    return titles


def find_qobuz_via_window_titles():
    if IS_WINDOWS:
        titles = get_all_window_titles_windows()
    elif IS_MAC:
        titles = get_all_window_titles_mac()
    else:
        titles = get_all_window_titles_linux()

    for title in titles:
        if QOBUZ_WEB_SUFFIX in title:
            clean = title[: title.rfind(QOBUZ_WEB_SUFFIX)].strip().rstrip("-").strip()
            if " - " in clean:
                return clean
        if "Qobuz" in title:
            clean = title
            for suffix in BROWSER_SUFFIXES:
                if clean.endswith(suffix):
                    clean = clean[: -len(suffix)]
                    break
            if "— Qobuz" in clean:
                clean = clean[: clean.rfind("— Qobuz")].strip()
            if " - " in clean and len(clean) < 200:
                return clean
    return None


def find_qobuz_web_title():
    result = find_qobuz_via_cdp()
    if result:
        return result
    return find_qobuz_via_window_titles()


def get_desktop_title_windows():
    for proc in psutil.process_iter():
        try:
            if "Qobuz" not in proc.name():
                continue
        except Exception:
            continue
        pid = proc.pid
        hwnds = []
        def callback(hwnd, _, _pid=pid):
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == _pid and IsWindowVisible(hwnd):
                hwnds.append(hwnd)
            return True
        win32gui.EnumWindows(callback, None)
        for hwnd in hwnds:
            length = GetWindowTextLength(hwnd)
            if length == 0:
                continue
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buf, length + 1)
            t = buf.value.strip()
            if t and t != "Qobuz":
                return t
    return None


def get_desktop_title_mac():
    try:
        import subprocess
        script = 'tell application "Qobuz" to get name of front window'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=3)
        t = result.stdout.strip()
        if t and t != "Qobuz":
            return t
    except Exception:
        pass
    return None


def get_desktop_title():
    if IS_WINDOWS:
        return get_desktop_title_windows()
    if IS_MAC:
        return get_desktop_title_mac()
    return None


def update_rpc(rpc, title, last_title):
    if title == last_title:
        return last_title

    parts = title.split(" - ", 1)
    if len(parts) < 2:
        return last_title

    song, artist = parts[0].strip(), parts[1].strip()
    print(f"\n  Now playing : {song}")
    print(f"  Artist      : {artist}")
    print(f"  Fetching art & duration...")

    art_url, dur_ms = fetch_art_and_duration(song, artist)

    if art_url:
        print(f"  Art found.")
    else:
        print(f"  No art — using Qobuz logo.")

    start_time = int(time.time())
    end_time   = (start_time + dur_ms // 1000) if dur_ms else None

    if end_time:
        mins, secs = divmod(dur_ms // 1000, 60)
        print(f"  Duration    : {mins}:{secs:02d}")
    else:
        print(f"  Duration    : unknown — showing elapsed timer.")

    update_args = dict(
        details     = song,
        state       = f"by {artist}",
        large_image = art_url if art_url else "qobuz",
        large_text  = f"{song} - {artist}",
        start       = start_time,
    )
    if end_time:
        update_args["end"] = end_time

    rpc.update(**update_args)
    return title


def choose_mode():
    print("=" * 45)
    print("         Qobuz Discord RPC")
    print("=" * 45)

    if IS_LINUX:
        print("\nLinux detected — using Web mode.")
        print("Make sure xdotool is installed:  sudo apt install xdotool\n")
        return "web"

    print("\nHow are you running Qobuz?")
    print("  1) Desktop app  (Windows / Mac)")
    print("  2) Web browser  (all platforms)")
    while True:
        choice = input("\nEnter 1 or 2: ").strip()
        if choice == "1":
            return "desktop"
        if choice == "2":
            return "web"
        print("Please enter 1 or 2.")


if __name__ == "__main__":
    mode = choose_mode()

    if mode == "web":
        if not IS_LINUX:
            if ensure_cdp():
                print("\n  CDP active — reading all browser tabs directly.")
            else:
                print("\n  CDP unavailable — using window title fallback.")
                print("  Note: Qobuz tab must be the active tab for this to work.")

    print(f"\nConnecting to Discord...")
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    print("Connected!\n")

    if mode == "desktop":
        print("Waiting for Qobuz desktop app...")
        while get_desktop_title() is None:
            time.sleep(2)
        print("Qobuz found.\n")
    else:
        print("Scanning for Qobuz web player...")
        while find_qobuz_web_title() is None:
            time.sleep(2)
        print("Qobuz web player found.\n")

    print("Listening for track changes. Press Ctrl+C to stop.")
    print("-" * 45)

    last_title  = ""
    was_playing = False

    while True:
        try:
            if mode == "desktop":
                raw = get_desktop_title()
                if raw is None:
                    if was_playing:
                        print("\n  Qobuz closed — clearing presence.")
                        rpc.clear()
                        last_title  = ""
                        was_playing = False
                    time.sleep(3)
                    continue
                if raw.strip() == "Qobuz":
                    if was_playing:
                        print("\n  Paused / idle — clearing presence.")
                        rpc.clear()
                        last_title  = ""
                        was_playing = False
                    time.sleep(2)
                    continue
                new = update_rpc(rpc, raw, last_title)
                if new != last_title:
                    last_title  = new
                    was_playing = True

            else:
                raw = find_qobuz_web_title()
                if raw is None:
                    if was_playing:
                        print("\n  Qobuz tab not found — clearing presence.")
                        rpc.clear()
                        last_title  = ""
                        was_playing = False
                    time.sleep(3)
                    continue
                new = update_rpc(rpc, raw, last_title)
                if new != last_title:
                    last_title  = new
                    was_playing = True

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nStopping...")
            rpc.clear()
            rpc.close()
            break
        except Exception as e:
            print(f"\n  Error: {e}")
            time.sleep(3)
