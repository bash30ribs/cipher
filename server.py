import os
import re
import sys
import json
import platform
import subprocess
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    import requests as _requests
except ImportError:
    _requests = None
try:
    import psutil as _psutil
except ImportError:
    _psutil = None
try:
    import pyperclip as _pyperclip
except ImportError:
    _pyperclip = None

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
from google.genai import types

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")
if not API_KEY:
    print("[CIPHER] WARNING: GEMINI_API_KEY not set in .env")

client = genai.Client(api_key=API_KEY)

# ── Flask & CORS ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

# ── Chat history (in-memory) ────────────────────────────────────────────────
chat_history = []
chat_lock = threading.Lock()

# ── OS detection ──────────────────────────────────────────────────────────────
OS = platform.system()  # 'Windows' | 'Darwin' | 'Linux'

# ── Known app launchers ───────────────────────────────────────────────────────
APP_MAP = {
    "notepad":    {"Windows": "notepad.exe",             "Darwin": "open -a TextEdit",              "Linux": "gedit"},
    "calculator": {"Windows": "calc.exe",                "Darwin": "open -a Calculator",            "Linux": "gnome-calculator"},
    "files":      {"Windows": "explorer.exe",            "Darwin": "open ~",                        "Linux": "nautilus"},
    "explorer":   {"Windows": "explorer.exe",            "Darwin": "open ~",                        "Linux": "nautilus"},
    "terminal":   {"Windows": "start cmd",               "Darwin": "open -a Terminal",              "Linux": "gnome-terminal"},
    "cmd":        {"Windows": "start cmd",               "Darwin": "open -a Terminal",              "Linux": "gnome-terminal"},
    "browser":    {"Windows": "start chrome",            "Darwin": "open -a 'Google Chrome'",       "Linux": "google-chrome"},
    "chrome":     {"Windows": "start chrome",            "Darwin": "open -a 'Google Chrome'",       "Linux": "google-chrome"},
    "edge":       {"Windows": "start msedge",            "Darwin": "open -a 'Microsoft Edge'",      "Linux": "microsoft-edge"},
    "firefox":    {"Windows": "start firefox",           "Darwin": "open -a Firefox",               "Linux": "firefox"},
    "spotify":    {"Windows": "start spotify",           "Darwin": "open -a Spotify",              "Linux": "spotify"},
    "vscode":     {"Windows": "code",                    "Darwin": "open -a 'Visual Studio Code'",  "Linux": "code"},
    "code":       {"Windows": "code",                    "Darwin": "open -a 'Visual Studio Code'",  "Linux": "code"},
    "vs code":    {"Windows": "code",                    "Darwin": "open -a 'Visual Studio Code'",  "Linux": "code"},
    "settings":   {"Windows": "start ms-settings:",     "Darwin": "open -a 'System Preferences'",  "Linux": "gnome-control-center"},
    "paint":      {"Windows": "mspaint",                 "Darwin": "open -a Preview",               "Linux": "kolourpaint"},
    "word":       {"Windows": "start winword",           "Darwin": "open -a 'Microsoft Word'",      "Linux": "libreoffice --writer"},
    "excel":      {"Windows": "start excel",             "Darwin": "open -a 'Microsoft Excel'",     "Linux": "libreoffice --calc"},
    "powerpoint": {"Windows": "start powerpnt",          "Darwin": "open -a 'Microsoft PowerPoint'","Linux": "libreoffice --impress"},
    "discord":    {"Windows": "start discord:",          "Darwin": "open -a Discord",              "Linux": "discord"},
    "slack":      {"Windows": "start slack:",            "Darwin": "open -a Slack",                "Linux": "slack"},
    "zoom":       {"Windows": "start zoommtg:",          "Darwin": "open -a zoom.us",              "Linux": "zoom"},
    "teams":      {"Windows": "start msteams:",          "Darwin": "open -a 'Microsoft Teams'",    "Linux": "teams"},
    "whatsapp":   {"Windows": "start whatsapp:",         "Darwin": "open -a WhatsApp",             "Linux": "whatsapp-desktop"},
    "telegram":   {"Windows": "start telegram:",         "Darwin": "open -a Telegram",             "Linux": "telegram-desktop"},
    "vlc":        {"Windows": "start vlc",               "Darwin": "open -a VLC",                  "Linux": "vlc"},
    "task manager":{"Windows": "start taskmgr",          "Darwin": "",                              "Linux": "gnome-system-monitor"},
    "taskmgr":    {"Windows": "start taskmgr",           "Darwin": "",                              "Linux": "gnome-system-monitor"},
    "control panel":{"Windows": "start control",         "Darwin": "",                              "Linux": "gnome-control-center"},
}

# ── Process names for closing apps via taskkill ───────────────────────────────
PROCESS_MAP = {
    "notepad":      "notepad.exe",
    "calculator":   "CalculatorApp.exe",
    "explorer":     "explorer.exe",
    "files":        "explorer.exe",
    "chrome":       "chrome.exe",
    "browser":      "chrome.exe",
    "edge":         "msedge.exe",
    "firefox":      "firefox.exe",
    "spotify":      "Spotify.exe",
    "vscode":       "Code.exe",
    "code":         "Code.exe",
    "word":         "WINWORD.EXE",
    "excel":        "EXCEL.EXE",
    "powerpoint":   "POWERPNT.EXE",
    "discord":      "Discord.exe",
    "slack":        "slack.exe",
    "zoom":         "Zoom.exe",
    "teams":        "Teams.exe",
    "whatsapp":     "WhatsApp.exe",
    "telegram":     "Telegram.exe",
    "vlc":          "vlc.exe",
    "paint":        "mspaint.exe",
    "task manager": "Taskmgr.exe",
    "obs":          "obs64.exe",
    "steam":        "steam.exe",
}

# ── Website shortcuts ─────────────────────────────────────────────────────────
SITE_MAP = {
    "youtube":   "https://www.youtube.com",
    "github":    "https://www.github.com",
    "gmail":     "https://mail.google.com",
    "google":    "https://www.google.com",
    "chatgpt":   "https://chat.openai.com",
    "claude":    "https://claude.ai",
    "reddit":    "https://www.reddit.com",
    "twitter":   "https://twitter.com",
    "x":         "https://twitter.com",
    "linkedin":  "https://www.linkedin.com",
    "netflix":   "https://www.netflix.com",
    "instagram": "https://www.instagram.com",
    "whatsapp":  "https://web.whatsapp.com",
    "maps":      "https://maps.google.com",
    "drive":     "https://drive.google.com",
    "facebook":  "https://www.facebook.com",
    "amazon":    "https://www.amazon.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "naukri":    "https://www.naukri.com",
    "indeed":    "https://www.indeed.com",
    "leetcode":  "https://leetcode.com",
    "notion":    "https://www.notion.so",
    "figma":     "https://www.figma.com",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_cmd(cmd: str) -> bool:
    """Run a shell command silently. Returns True on success."""
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"[CIPHER] CMD error: {e}")
        return False


def universal_launch(app_name: str) -> dict:
    """Try to launch ANY installed Windows app by name. Returns proper status."""
    if OS != "Windows":
        return {"action": "open_app", "app": app_name, "status": "not_found",
                "reply": f"{app_name.capitalize()} wasn't found on your device."}
    try:
        # Use powershell to check if the app exists before trying to launch
        check = subprocess.run(
            f'powershell -c "try {{ Start-Process \'\'{app_name}\'\'  -ErrorAction Stop; exit 0 }} catch {{ exit 1 }}"',
            shell=True, timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        if check.returncode == 0:
            return {"action": "open_app", "app": app_name, "status": "ok",
                    "reply": f"Opening {app_name.capitalize()}."}

        # Also try via 'start' command (handles PATH + App Paths registry)
        result = subprocess.run(
            f'cmd /c start "" "{app_name}"',
            shell=True, timeout=3,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        # 'start' returns 0 even if app not found, check stderr
        stderr_text = result.stderr.decode(errors='replace').lower()
        if result.returncode == 0 and 'not found' not in stderr_text and 'cannot find' not in stderr_text:
            return {"action": "open_app", "app": app_name, "status": "ok",
                    "reply": f"Opening {app_name.capitalize()}."}

        return {"action": "open_app", "app": app_name, "status": "not_found",
                "reply": f"{app_name.capitalize()} wasn't found on your device. Make sure it's installed."}
    except subprocess.TimeoutExpired:
        # Timeout usually means app launched fine (it's running)
        return {"action": "open_app", "app": app_name, "status": "ok",
                "reply": f"Opening {app_name.capitalize()}."}
    except Exception as e:
        print(f"[CIPHER] Universal launch error: {e}")
        return {"action": "open_app", "app": app_name, "status": "not_found",
                "reply": f"{app_name.capitalize()} wasn't found on your device."}


def close_app(name: str) -> dict:
    """Close an app by name using taskkill."""
    name_lower = name.lower().strip()
    process = PROCESS_MAP.get(name_lower)
    if not process and OS == "Windows":
        # Guess: appname.exe
        process = name_lower.replace(" ", "") + ".exe"
    if OS == "Windows" and process:
        result = subprocess.run(
            f'taskkill /F /IM "{process}" /T',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            return {"action": "close_app", "app": name, "reply": f"{name.capitalize()} has been closed."}
        # If exact match failed, try without quotes (handles cases like Zoom.exe)
        result2 = subprocess.run(
            f'taskkill /F /IM {process} /T',
            shell=True, capture_output=True, text=True
        )
        if result2.returncode == 0:
            return {"action": "close_app", "app": name, "reply": f"{name.capitalize()} has been closed."}
    return {"action": "close_app", "app": name, "reply": f"Could not find a running process for '{name}'. Make sure it is open."}


def close_window_by_title(keyword: str) -> dict:
    """Close a window (e.g. browser tab/window) whose title contains keyword."""
    if OS != "Windows":
        return {"action": "close_window", "reply": f"Window close by title is only supported on Windows."}
    try:
        import ctypes
        found_windows = []

        def enum_handler(hwnd, _):
            try:
                import ctypes
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if keyword.lower() in title.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
                        found_windows.append((hwnd, title))
            except:
                pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)

        if found_windows:
            hwnd, title = found_windows[0]
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return {"action": "close_window", "title": title, "reply": f"Closing '{keyword}' window."}
        return {"action": "close_window", "reply": f"No window found matching '{keyword}'."}
    except Exception as e:
        print(f"[CIPHER] close_window error: {e}")
        return {"action": "close_window", "reply": f"Could not close '{keyword}': {e}"}


def open_website(url: str, site_name: str = "") -> dict:
    """Open a URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if not site_name:
        # Derive a clean name from the URL
        site_name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0].capitalize()
    webbrowser.open(url)
    return {"action": "open_website", "url": url, "site_name": site_name, "status": "ok"}


def open_app(name: str) -> dict:
    """Open a known desktop application."""
    name = name.lower().strip()
    cmd = APP_MAP.get(name, {}).get(OS)
    if cmd:
        run_cmd(cmd)
        return {"action": "open_app", "app": name, "status": "ok"}
    return {"action": "open_app", "app": name, "status": "not_found"}


def get_system_info() -> dict:
    """Return basic system information."""
    return {
        "os": OS,
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%A, %B %d %Y"),
    }


def screenshot() -> dict:
    """Take a screenshot and save to Desktop."""
    try:
        from PIL import ImageGrab
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        fname = desktop / f"cipher_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img = ImageGrab.grab()
        img.save(fname)
        return {"action": "screenshot", "path": str(fname), "status": "ok"}
    except ImportError:
        return {"action": "screenshot", "status": "error", "detail": "Pillow not installed"}
    except Exception as e:
        return {"action": "screenshot", "status": "error", "detail": str(e)}


def set_volume(level: int) -> dict:
    """Set system volume (0-100). Windows/macOS/Linux."""
    level = max(0, min(100, level))
    if OS == "Windows":
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = interface.QueryInterface(IAudioEndpointVolume)
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        except Exception as e:
            print(f"[Volume] {e}")
    elif OS == "Darwin":
        run_cmd(f"osascript -e 'set volume output volume {level}'")
    elif OS == "Linux":
        run_cmd(f"amixer -q sset Master {level}%")
    return {"action": "set_volume", "level": level, "status": "ok"}


# ── Weather ──────────────────────────────────────────────────────────────
def get_weather(city: str) -> dict:
    """Get weather via wttr.in (free, no API key needed)."""
    if not _requests:
        return {"action": "weather", "reply": "Weather unavailable: install requests."}
    try:
        city_q = city.replace(' ', '+')
        r = _requests.get(f"https://wttr.in/{city_q}?format=j1", timeout=5)
        r.raise_for_status()
        j = r.json()
        cur = j['current_condition'][0]
        desc = cur['weatherDesc'][0]['value']
        temp_c = cur['temp_C']
        feels = cur['FeelsLikeC']
        humidity = cur['humidity']
        wind = cur['windspeedKmph']
        reply = (f"Weather in {city.title()}: {desc}, {temp_c}°C "
                 f"(feels like {feels}°C). Humidity {humidity}%, Wind {wind} km/h.")
        return {"action": "weather", "reply": reply, "status": "ok"}
    except Exception as e:
        return {"action": "weather", "reply": f"Couldn't fetch weather for '{city}': {e}"}


# ── Clipboard ────────────────────────────────────────────────────────────
def clipboard_read() -> dict:
    if not _pyperclip:
        return {"action": "clipboard", "reply": "Clipboard unavailable: install pyperclip."}
    try:
        content = _pyperclip.paste()
        if not content.strip():
            return {"action": "clipboard", "reply": "Clipboard is empty."}
        short = content[:300] + ('...' if len(content) > 300 else '')
        return {"action": "clipboard", "reply": f"Clipboard: {short}"}
    except Exception as e:
        return {"action": "clipboard", "reply": f"Couldn't read clipboard: {e}"}

def clipboard_write(text: str) -> dict:
    if not _pyperclip:
        return {"action": "clipboard", "reply": "Clipboard unavailable: install pyperclip."}
    try:
        _pyperclip.copy(text)
        short = text[:80] + ('...' if len(text) > 80 else '')
        return {"action": "clipboard", "reply": f"Copied to clipboard: '{short}'"}
    except Exception as e:
        return {"action": "clipboard", "reply": f"Couldn't copy: {e}"}


# ── File / folder opener ──────────────────────────────────────────────────
FOLDER_MAP = {
    "downloads":  Path.home() / "Downloads",
    "documents":  Path.home() / "Documents",
    "desktop":    Path.home() / "Desktop",
    "pictures":   Path.home() / "Pictures",
    "music":      Path.home() / "Music",
    "videos":     Path.home() / "Videos",
    "appdata":    Path(os.environ.get("APPDATA", Path.home())),
    "temp":       Path(os.environ.get("TEMP", "/tmp")),
}
def open_folder(name: str) -> dict:
    key = name.lower().strip()
    folder = FOLDER_MAP.get(key)
    if not folder:
        # Try it as a literal path
        folder = Path(name)
    if folder and folder.exists():
        if OS == "Windows":
            subprocess.Popen(f'explorer "{folder}"')
        elif OS == "Darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return {"action": "open_folder", "reply": f"Opening {folder.name or name} folder."}
    return {"action": "open_folder", "reply": f"Folder '{name}' not found."}


# ── Battery & CPU ──────────────────────────────────────────────────────────
def get_battery_cpu() -> dict:
    if not _psutil:
        return {"action": "battery_cpu", "reply": "psutil not installed. Run: pip install psutil"}
    try:
        cpu = _psutil.cpu_percent(interval=0.5)
        mem = _psutil.virtual_memory()
        mem_used = round(mem.used / 1e9, 1)
        mem_total = round(mem.total / 1e9, 1)
        battery = _psutil.sensors_battery()
        parts = [f"CPU: {cpu}%", f"RAM: {mem_used}GB / {mem_total}GB ({mem.percent}%)"]
        if battery:
            status = "charging" if battery.power_plugged else "on battery"
            parts.append(f"Battery: {round(battery.percent)}% ({status})")
        else:
            parts.append("Battery: not detected (desktop?)")
        return {"action": "battery_cpu", "reply": " | ".join(parts)}
    except Exception as e:
        return {"action": "battery_cpu", "reply": f"Could not get system stats: {e}"}


# ── Quick Notes ─────────────────────────────────────────────────────────────
NOTES_FILE = Path(__file__).parent / "notes.txt"
def save_note(text: str) -> dict:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")
        short = text[:80] + ('...' if len(text) > 80 else '')
        return {"action": "note", "reply": f"Note saved: '{short}'"}
    except Exception as e:
        return {"action": "note", "reply": f"Couldn't save note: {e}"}

def read_notes(n: int = 5) -> dict:
    try:
        if not NOTES_FILE.exists():
            return {"action": "note", "reply": "No notes saved yet. Say 'note: ...' to add one."}
        lines = NOTES_FILE.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return {"action": "note", "reply": "Notes file is empty."}
        recent = lines[-n:]
        return {"action": "note", "reply": "Recent notes:\n" + "\n".join(recent)}
    except Exception as e:
        return {"action": "note", "reply": f"Couldn't read notes: {e}"}


# ── Focus Mode ─────────────────────────────────────────────────────────────
DISTRACTION_SITES = ["youtube", "instagram", "twitter", "facebook", "reddit", "netflix", "tiktok"]
DISTRACTION_APPS  = ["spotify", "discord", "steam", "whatsapp"]
def focus_mode_on() -> dict:
    closed = []
    for site in DISTRACTION_SITES:
        r = close_window_by_title(site.capitalize())
        if "Closing" in r.get("reply", ""):
            closed.append(site)
    for app in DISTRACTION_APPS:
        r = close_app(app)
        if "closed" in r.get("reply", "").lower():
            closed.append(app)
    msg = f"Focus mode ON. Closed: {', '.join(closed)}." if closed else "Focus mode ON. No distractions were open."
    return {"action": "focus_mode", "reply": msg}

def focus_mode_off() -> dict:
    return {"action": "focus_mode", "reply": "Focus mode OFF. You're free to relax again."}


# ── Window foreground (switch to a running app) ─────────────────────────────
def switch_to_window(keyword: str) -> dict:
    if OS != "Windows":
        return {"action": "switch_window", "reply": "Window switching is only supported on Windows."}
    try:
        import ctypes
        found = []
        def enum_handler(hwnd, _):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0 and ctypes.windll.user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if keyword.lower() in buf.value.lower():
                    found.append(hwnd)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
        if found:
            hwnd = found[0]
            # Restore if minimized, then bring to front
            ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return {"action": "switch_window", "reply": f"Switched to '{keyword}' window."}
        return {"action": "switch_window", "reply": f"No window found matching '{keyword}'. Is it open?"}
    except Exception as e:
        return {"action": "switch_window", "reply": f"Couldn't switch window: {e}"}


# ── Intent router ─────────────────────────────────────────────────────────────

def route_intent(text: str):
    """
    Try to match a local OS intent before calling Gemini.
    Returns a dict result if handled locally, else None.
    """
    global chat_history
    original = text
    t = text.lower().strip()
    # Remove trailing punctuation
    t = re.sub(r'[.!?]+$', '', t).strip()

    print(f"[CIPHER] Processing: {t}")

    # ── Open app (check FIRST before website so "open calculator" never misroutes) ──
    open_trigger = re.search(r'\b(?:open|launch|start|run)\b', t)
    if open_trigger:
        # Build sorted list (longest keys first) to avoid partial matches
        sorted_apps = sorted(APP_MAP.keys(), key=len, reverse=True)
        for app_name in sorted_apps:
            pattern = r'\b(?:open|launch|start|run)\s+(?:the\s+)?' + re.escape(app_name) + r'\b'
            if re.search(pattern, t):
                result = open_app(app_name)
                if result["status"] == "ok":
                    return result
                # Not found on this OS — fall through

        # Universal fallback: extract what comes after the trigger word
        # and try to launch it directly (handles any installed Windows app)
        raw_m = re.search(r'\b(?:open|launch|start|run)\s+(?:the\s+)?(.+?)\s*$', t)
        if raw_m:
            raw_name = raw_m.group(1).strip()
            # Only if it's not a known website and not too long (probably a question)
            if raw_name not in SITE_MAP and '.' not in raw_name and len(raw_name.split()) <= 3:
                result = universal_launch(raw_name)
                return result

    # ── Open website ──────────────────────────────────────────────────────────
    # Priority 1: Explicit "open" trigger
    if open_trigger:
        # Extract word after open/go to/navigate etc.
        m = re.search(r'\b(?:open|go\s+to|navigate\s+to|visit|show)\s+(?:website\s+)?(?:the\s+)?([a-z0-9.\-]+)', t)
        if m:
            target = m.group(1).strip()
            if target in SITE_MAP:
                return open_website(SITE_MAP[target], target.capitalize())
            # Bare name like "gmail" not in SITE_MAP but looks like a site
            if target not in APP_MAP:  # avoid re-opening apps
                url_target = target if '.' in target else f"{target}.com"
                return open_website(url_target, target.capitalize())

    # Priority 2: Site name anywhere with a navigation verb
    NAV_VERBS = ['open', 'go to', 'navigate', 'visit', 'show', 'launch']
    sorted_sites = sorted(SITE_MAP.keys(), key=len, reverse=True)
    for site_name in sorted_sites:
        if site_name in t:
            if any(v in t for v in NAV_VERBS) and not any(w in t for w in ['what', 'explain', 'tell', 'about', 'how']):
                return open_website(SITE_MAP[site_name], site_name.capitalize())

    # ── YouTube search ────────────────────────────────────────────────────────
    yt_patterns = [
        r'(?:search|play|find|look\s+up)\s+(.+?)\s+on\s+youtube',
        r'youtube\s+(?:search\s+for|search|for)\s+(.+)',
        r'play\s+(.+?)\s+(?:on\s+)?youtube',
        r'^play\s+(.+)',
    ]
    for pattern in yt_patterns:
        match = re.search(pattern, t)
        if match:
            query = match.group(1).strip().replace(" ", "+")
            return open_website(f"https://www.youtube.com/results?search_query={query}", f"YouTube: {match.group(1).strip()}")

    # ── Google search ─────────────────────────────────────────────────────────
    google_patterns = [
        r'(?:search|google)\s+(?:for\s+)?(.+)',
        r'look\s+up\s+(.+)',
        r'find\s+(.+?)\s+(?:on\s+)?google',
    ]
    for pattern in google_patterns:
        match = re.search(pattern, t)
        if match:
            query = match.group(1).strip()
            safe_kws = ['open', 'screenshot', 'volume', 'system', 'lock', 'mute']
            if not any(kw in query for kw in safe_kws):
                return open_website(f"https://www.google.com/search?q={query.replace(' ', '+')}", f"Google: {query}")

    # ── System info ───────────────────────────────────────────────────────────
    if any(kw in t for kw in ["system info", "system information", "what os", "my system", "about my computer", "computer info"]):
        info = get_system_info()
        return {
            "action": "system_info",
            "reply": (
                f"System: {info['os']} {info['version']}\n"
                f"Machine: {info['machine']} | Processor: {info['processor']}\n"
                f"Time: {info['time']}  Date: {info['date']}"
            ),
        }

    # ── Screenshot ────────────────────────────────────────────────────────────
    if any(kw in t for kw in ["screenshot", "screen shot", "take a screenshot", "capture screen"]):
        return screenshot()

    # ── Volume ────────────────────────────────────────────────────────────────
    vol_patterns = [
        r'set\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)',
        r'volume\s+(\d+)',
        r'change\s+volume\s+to\s+(\d+)',
    ]
    for pattern in vol_patterns:
        match = re.search(pattern, t)
        if match:
            return set_volume(int(match.group(1)))

    # Volume up/down
    if any(kw in t for kw in ["volume up", "increase volume", "turn up"]):
        return set_volume(75)  # Default to 75%
    if any(kw in t for kw in ["volume down", "decrease volume", "turn down"]):
        return set_volume(25)  # Default to 25%

    # ── Mute ──────────────────────────────────────────────────────────────────
    if "mute" in t and "unmute" not in t:
        if OS == "Darwin":
            run_cmd("osascript -e 'set volume output muted true'")
        elif OS == "Linux":
            run_cmd("amixer -q sset Master mute")
        elif OS == "Windows":
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from comtypes import CLSCTX_ALL
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol = interface.QueryInterface(IAudioEndpointVolume)
                vol.SetMute(1, None)
            except:
                pass
        return {"action": "mute", "status": "ok", "reply": "Volume muted."}

    if "unmute" in t:
        if OS == "Darwin":
            run_cmd("osascript -e 'set volume output muted false'")
        elif OS == "Linux":
            run_cmd("amixer -q sset Master unmute")
        elif OS == "Windows":
            try:
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                from comtypes import CLSCTX_ALL
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol = interface.QueryInterface(IAudioEndpointVolume)
                vol.SetMute(0, None)
            except:
                pass
        return {"action": "unmute", "status": "ok", "reply": "Volume unmuted."}

    # ── Date / time ───────────────────────────────────────────────────────────
    if any(kw in t for kw in ["what time", "what's the time", "current time", "time is it"]):
        return {"action": "time", "reply": f"It's {datetime.now().strftime('%H:%M:%S')}."}

    if any(kw in t for kw in ["what date", "what's today", "today's date", "what day"]):
        return {"action": "date", "reply": f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."}

    # ── Lock Screen ───────────────────────────────────────────────────────────
    if any(kw in t for kw in ["lock computer", "lock screen", "lock my computer", "lock the computer"]):
        if OS == "Windows":
            run_cmd("rundll32.exe user32.dll,LockWorkStation")
        elif OS == "Darwin":
            run_cmd("pmset displaysleepnow")
        elif OS == "Linux":
            run_cmd("xdg-screensaver lock")
        return {"action": "lock", "reply": "Locking the screen."}

    # ── Clear Chat ────────────────────────────────────────────────────────────
    if any(t == kw for kw in ["clear chat", "clear screen", "reset chat", "start over", "close chat"]):
        chat_history = []
        return {"action": "clear", "reply": "Chat history cleared."}

    # ── Weather ──────────────────────────────────────────────────────
    weather_m = re.search(r'(?:weather|temperature|forecast|how(?:\'s| is) the weather)\s+(?:in|at|for)?\s*([a-z\s]+?)\s*$', t)
    if weather_m:
        city = weather_m.group(1).strip()
        if city and len(city) >= 2:
            return get_weather(city)
    if re.search(r'^(?:weather|weather here|weather today|current weather)$', t):
        return get_weather("auto")  # wttr.in auto-detects by IP

    # ── Clipboard ─────────────────────────────────────────────────
    if any(kw in t for kw in ["what's in my clipboard", "read clipboard", "show clipboard", "clipboard content", "paste content"]):
        return clipboard_read()
    copy_m = re.search(r'(?:copy|copy this|copy text)\s+["\']?(.+?)["\']?\s*$', t)
    if copy_m:
        return clipboard_write(copy_m.group(1).strip())

    # ── Open folder ─────────────────────────────────────────────────
    folder_m = re.search(r'(?:open|show|go to)\s+(?:my\s+)?(?:the\s+)?(downloads?|documents?|desktop|pictures?|music|videos?|appdata|temp)(?:\s+folder)?', t)
    if folder_m:
        return open_folder(folder_m.group(1).rstrip('s'))  # normalize plural

    # ── Battery & CPU ────────────────────────────────────────────────
    if any(kw in t for kw in ["battery", "cpu usage", "ram usage", "memory usage", "cpu load", "battery status", "system stats", "performance"]):
        return get_battery_cpu()

    # ── Quick Notes ──────────────────────────────────────────────────
    note_m = re.search(r'^note(?:s)?[:\s]+(.+)', t)
    if note_m:
        return save_note(note_m.group(1).strip())
    if any(kw in t for kw in ["show notes", "read notes", "my notes", "show my notes", "list notes"]):
        return read_notes()

    # ── Focus Mode ──────────────────────────────────────────────────
    if any(kw in t for kw in ["focus mode on", "enable focus", "start focus", "focus on", "do not disturb"]):
        return focus_mode_on()
    if any(kw in t for kw in ["focus mode off", "disable focus", "stop focus", "end focus"]):
        return focus_mode_off()

    # ── Switch to window (tab switcher) ──────────────────────────────
    switch_m = re.search(r'(?:switch to|go to|bring up|show)\s+(?:the\s+)?([a-z0-9]+)\s+(?:tab|window|app)', t)
    if switch_m:
        return switch_to_window(switch_m.group(1))

    # ── Close browser tab by title ────────────────────────────────────────────
    # e.g. "close youtube tab", "close the linkedin window"
    close_tab_match = re.search(
        r'\bclose\b.+?\b([a-z0-9]+)\s+(?:tab|window|page)\b', t
    )
    if close_tab_match:
        keyword = close_tab_match.group(1)
        # If it's a known site, use the site name for better matching
        if keyword in SITE_MAP:
            site_url = SITE_MAP[keyword]
            site_hostname = site_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            return close_window_by_title(site_hostname.split(".")[0].capitalize())
        return close_window_by_title(keyword)

    # ── Close app by name ─────────────────────────────────────────────────────
    # e.g. "close whatsapp", "close spotify app", "close word"
    close_app_match = re.search(
        r'\b(?:close|quit|exit|kill)\b\s+(?:the\s+)?(.+?)\s*(?:\bapp\b|\bapplication\b)?\s*$', t
    )
    if close_app_match:
        target = close_app_match.group(1).strip().rstrip()
        # Exclude cases that are already handled above (tabs/windows)
        if not any(w in t for w in ['tab', 'window', 'page']):
            return close_app(target)

    return None  # Not handled locally → fall through to Gemini


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "CIPHER running", "os": OS, "version": "2.5"})


@app.route("/app")
def serve_app():
    """Serve the cipher.html interface at http://localhost:5000/app"""
    return send_from_directory(Path(__file__).parent, 'cipher.html')


@app.route("/cipher_logo.png")
def serve_logo():
    """Serve the logo so the app interface finds it."""
    return send_from_directory(Path(__file__).parent, 'cipher_logo.png')


# ── Trap helpers ──────────────────────────────────────────────────────────────
TRAPS_FILE = Path(__file__).parent / "traps.json"

def load_traps() -> dict:
    try:
        if TRAPS_FILE.exists():
            return json.loads(TRAPS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[CIPHER] traps load error: {e}")
    return {}

def save_traps(data: dict):
    try:
        TRAPS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[CIPHER] traps save error: {e}")

def execute_trap(trap: dict) -> dict:
    """Launch all apps + websites in a trap. Returns summary."""
    opened, failed = [], []

    for app_name in trap.get("apps", []):
        name_lower = app_name.lower().strip()
        # Try APP_MAP first
        cmd = APP_MAP.get(name_lower, {}).get(OS)
        if cmd:
            success = run_cmd(cmd)
            if success:
                opened.append(app_name)
                continue
        # Universal fallback
        result = universal_launch(app_name)
        if result.get("status") == "ok":
            opened.append(app_name)
        else:
            failed.append(app_name)

    for site in trap.get("sites", []):
        site_lower = site.lower().strip()
        url = SITE_MAP.get(site_lower, site if '.' in site else f"https://{site}.com")
        try:
            open_website(url, site)
            opened.append(site)
        except Exception:
            failed.append(site)

    parts = []
    if opened:
        parts.append(f"Opened: {', '.join(opened)}.")
    if failed:
        parts.append(f"Not found: {', '.join(failed)}.")
    reply = " ".join(parts) if parts else "Trap is empty."
    return {"action": "trap_run", "opened": opened, "failed": failed, "reply": reply}


@app.route("/traps", methods=["GET"])
def list_traps():
    return jsonify(load_traps())

@app.route("/traps", methods=["POST"])
def save_trap():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip().lower()
    if not name:
        return jsonify({"error": "Trap name required"}), 400
    traps = load_traps()
    traps[name] = {"name": data.get("name", name), "apps": data.get("apps", []), "sites": data.get("sites", [])}
    save_traps(traps)
    return jsonify({"status": "saved", "trap": traps[name]})

@app.route("/traps/<trap_name>", methods=["DELETE"])
def delete_trap(trap_name):
    traps = load_traps()
    key = trap_name.lower()
    if key in traps:
        del traps[key]
        save_traps(traps)
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Trap not found"}), 404

@app.route("/traps/<trap_name>/run", methods=["POST"])
def run_trap_route(trap_name):
    traps = load_traps()
    trap = traps.get(trap_name.lower())
    if not trap:
        return jsonify({"error": f"Trap '{trap_name}' not found"}), 404
    result = execute_trap(trap)
    return jsonify(result)


def close_trap(trap: dict) -> dict:
    """Close all apps + browser windows associated with a trap."""
    closed, failed, not_open = [], [], []

    # Close apps via taskkill
    for app_name in trap.get("apps", []):
        name_lower = app_name.lower().strip()
        result = close_app(name_lower)
        if "closed" in result.get("reply", "").lower():
            closed.append(app_name)
        else:
            not_open.append(app_name)

    # Close browser windows/tabs by site title keyword
    for site in trap.get("sites", []):
        site_lower = site.lower().strip()
        # Resolve to readable keyword (e.g. "youtube" → "YouTube")
        keyword = site_lower.capitalize()
        if site_lower in SITE_MAP:
            url = SITE_MAP[site_lower]
            keyword = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0].capitalize()
        result = close_window_by_title(keyword)
        if "Closing" in result.get("reply", ""):
            closed.append(site)
        else:
            not_open.append(site)

    parts = []
    if closed:
        parts.append(f"Closed: {', '.join(closed)}.")
    if not_open:
        parts.append(f"Already closed or not found: {', '.join(not_open)}.")
    reply = " ".join(parts) if parts else "Nothing was running from this trap."
    return {"action": "trap_close", "closed": closed, "not_found": not_open, "reply": reply}


@app.route("/traps/<trap_name>/close", methods=["POST"])
def close_trap_route(trap_name):
    traps = load_traps()
    trap = traps.get(trap_name.lower())
    if not trap:
        return jsonify({"error": f"Trap '{trap_name}' not found"}), 404
    result = close_trap(trap)
    return jsonify(result)


@app.route("/chat", methods=["POST"])
def chat():
    global chat_history
    data = request.get_json(silent=True) or {}
    user_input = (data.get("message") or "").strip()
    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    print(f"[CIPHER] Received: {user_input}")

    # ── "answer this" bypass → skip local routing, force Gemini ──────────────
    answer_this = re.match(r'^(?:answer\s+this|gemini\s+answer|ai\s+answer)\s+(.+)', user_input, re.IGNORECASE)
    if answer_this:
        user_input = answer_this.group(1).strip()
        # fall straight through to Gemini below (skip local intent)
    else:
        # 1. Try local intent
        local = route_intent(user_input)
        if local:
            print(f"[CIPHER] Local action: {local.get('action')}")
            reply = local.get("reply") or _build_local_reply(local)
            return jsonify({"reply": reply, "action": local.get("action"), "meta": local})

        # ── Trap voice trigger ────────────────────────────────────────────────
        trap_match = re.match(r'^(?:run\s+|activate\s+|launch\s+)?trap\s+(\S+)$', user_input.lower().strip())
        if trap_match:
            trap_name = trap_match.group(1)
            traps = load_traps()
            trap = traps.get(trap_name)
            if trap:
                result = execute_trap(trap)
                return jsonify({"reply": result["reply"], "action": "trap_run", "meta": result})
            return jsonify({"reply": f"Trap '{trap_name}' doesn't exist. Create it in the Trap Manager.", "action": "trap_run"})

    # 2. Fall back to Gemini
    print("[CIPHER] Forwarding to Gemini...")
    try:
        with chat_lock:
            chat_history.append({"role": "user", "parts": [{"text": user_input}]})
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=chat_history,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are CIPHER, a fast, intelligent desktop AI assistant. "
                        "Respond concisely and helpfully. Never refuse basic desktop assistant tasks."
                    ),
                ),
            )
            reply = response.text.strip()
            chat_history.append({"role": "model", "parts": [{"text": reply}]})
        print(f"[CIPHER] Gemini replied: {reply[:100]}...")
        return jsonify({"reply": reply, "action": "gemini"})
    except Exception as e:
        print(f"[CIPHER] Gemini error: {e}")
        # Remove last user message from history on error
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return jsonify({"error": str(e), "reply": "Sorry, I ran into an error with Gemini."}), 500


@app.route("/reset", methods=["POST"])
def reset_chat():
    global chat_history
    with chat_lock:
        chat_history = []
    return jsonify({"status": "Chat history cleared."})


@app.route("/sysinfo", methods=["GET"])
def sysinfo():
    return jsonify(get_system_info())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_local_reply(result: dict) -> str:
    action = result.get("action", "")
    status = result.get("status", "")
    if action == "open_website":
        site_name = result.get("site_name", "")
        if not site_name:
            url = result.get("url", "")
            site_name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0].split(".")[0].capitalize()
        return f"Opening {site_name} in your browser."
    if action == "open_app":
        name = result.get("app", "the app").capitalize()
        if status == "not_found":
            return result.get("reply") or f"{name} wasn't found on your device. Make sure it's installed."
        return result.get("reply") or f"Opening {name}."
    if action == "screenshot":
        if status == "ok":
            return f"Screenshot saved to {result.get('path')}."
        return f"Screenshot failed: {result.get('detail')}"
    if action == "set_volume":
        return f"Volume set to {result.get('level')}%."
    if action in ("close_app", "close_window", "trap_run"):
        return result.get("reply", "Done.")
    return "Done."


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    port = int(os.environ.get("PORT", 5000))
    print("="*36)
    print("   CIPHER  --  Desktop AI Engine   ")
    print(f"   OS: {OS}")
    print(f"   Port: {port}")
    print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
    if os.environ.get("RENDER"):
        print("   Mode: CLOUD (Action features disabled)")
    print("="*36)
    print()
    print(f"[CIPHER] Server starting on port {port}")
    print(f"[CIPHER] Open the app at: http://localhost:{port}/app")
    print("[CIPHER] API ready at:    http://localhost:{}/chat".format(port))
    print()
    app.run(host="0.0.0.0", port=port, debug=False)