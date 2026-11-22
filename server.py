import os
import re
import sys
import json
import time
import socket
import ast
import operator
import platform
import subprocess
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ── Offline & Connectivity Helpers ───────────────────────────────────────────
def check_internet_connection(timeout: float = 1.0) -> bool:
    """Check if device has active internet access via fast DNS socket."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def is_offline_error(e: Exception) -> bool:
    """Detect if an exception is caused by lack of internet connectivity."""
    err_str = str(e).lower()
    offline_keywords = [
        "failed to resolve", "getaddrinfo failed", "name resolution", "connection error",
        "connection refused", "network is unreachable", "apiconnectionerror",
        "connectionreseterror", "nodename nor servname", "timed out", "timeout",
        "connection broken", "socket.gaierror", "cannot connect to host"
    ]
    return any(kw in err_str for kw in offline_keywords)

_SAFE_MATH_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _eval_math_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in _SAFE_MATH_OPS:
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        if isinstance(node.op, ast.Pow) and right > 100:
            raise ValueError("Exponent too large")
        return _SAFE_MATH_OPS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_MATH_OPS:
        return _SAFE_MATH_OPS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError("Unsupported operation")

def safe_eval_math(expr_str: str):
    """Safely parse and evaluate basic math expression without eval()."""
    tree = ast.parse(expr_str.strip(), mode='eval')
    return _eval_math_node(tree.body)

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

from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from google import genai
from google.genai import types

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY") or "").strip()
if not API_KEY:
    print("[CIPHER] WARNING: GEMINI_API_KEY/API_KEY not set in environment or .env file.")

client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"[CIPHER] ERROR initializing Gemini client: {e}")

# ── Flask & CORS ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='docs', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

# ── Chat history (in-memory) ────────────────────────────────────────────────
chat_history = []
chat_lock = threading.Lock()

# ── OS detection ──────────────────────────────────────────────────────────────
OS = platform.system()  # 'Windows' | 'Darwin' | 'Linux'

# ── Cloud detection ───────────────────────────────────────────────────────────
IS_CLOUD = os.environ.get("RENDER") == "true" or os.environ.get("RAILWAY_ENVIRONMENT") is not None

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
    "powershell":   {"Windows": "start powershell",      "Darwin": "pwsh",                          "Linux": "pwsh"},
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
    "powershell":   "powershell.exe",
}

# ── Website shortcuts ─────────────────────────────────────────────────────────
SITE_MAP = {
    "youtube":       "https://www.youtube.com",
    "github":        "https://www.github.com",
    "gmail":         "https://mail.google.com",
    "google":        "https://www.google.com",
    "chatgpt":       "https://chat.openai.com",
    "claude":        "https://claude.ai",
    "gemini":        "https://gemini.google.com",
    "reddit":        "https://www.reddit.com",
    "twitter":       "https://twitter.com",
    "x":             "https://twitter.com",
    "linkedin":      "https://www.linkedin.com",
    "netflix":       "https://www.netflix.com",
    "instagram":     "https://www.instagram.com",
    "snapchat":      "https://web.snapchat.com",
    "tiktok":        "https://www.tiktok.com",
    "pinterest":     "https://www.pinterest.com",
    "twitch":        "https://www.twitch.tv",
    "whatsapp":      "https://web.whatsapp.com",
    "maps":          "https://maps.google.com",
    "drive":         "https://drive.google.com",
    "facebook":      "https://www.facebook.com",
    "amazon":        "https://www.amazon.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia":     "https://www.wikipedia.org",
    "naukri":        "https://www.naukri.com",
    "indeed":        "https://www.indeed.com",
    "leetcode":      "https://leetcode.com",
    "notion":        "https://www.notion.so",
    "figma":         "https://www.figma.com",
    "spotify":       "https://open.spotify.com",
    "quora":         "https://www.quora.com",
    "medium":        "https://medium.com",
    "canva":         "https://www.canva.com",
    "calendar":      "https://calendar.google.com",
    "meet":          "https://meet.google.com",
    "docs":          "https://docs.google.com",
    "sheets":        "https://sheets.google.com",
    "slides":        "https://slides.google.com",
    "hotstar":       "https://www.hotstar.com",
    "prime":         "https://www.primevideo.com",
    "prime video":   "https://www.primevideo.com",
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
    if IS_CLOUD:
        return {"action": "open_app", "app": app_name, "status": "cloud_unsupported",
                "reply": "Launching local applications is only supported when running CIPHER locally on your device."}
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
    """Close an app by name. Uses psutil to scan all running processes,
    falls back to taskkill on Windows."""
    if IS_CLOUD:
        return {"action": "close_app", "app": name,
                "reply": "Closing local applications is only supported when running CIPHER locally on your device."}
    name_lower = name.lower().strip()
    # Remove trailing noise words that user might say (e.g. "close chrome app" -> "chrome")
    name_lower = re.sub(r'\s+(app|application|program|software|window)$', '', name_lower).strip()

    process_filename = PROCESS_MAP.get(name_lower)
    if not process_filename and OS == "Windows":
        process_filename = name_lower.replace(" ", "") + ".exe"
    elif not process_filename:
        process_filename = name_lower

    print(f"[CIPHER] close_app: looking for '{name_lower}' / process='{process_filename}'")

    killed_any = False
    if _psutil:
        procs_to_kill = []
        for proc in _psutil.process_iter(['pid', 'name']):
            try:
                proc_name = (proc.info.get('name') or '').strip()
                if not proc_name:
                    continue
                pn_lower = proc_name.lower()
                match = (
                    pn_lower == process_filename.lower() or
                    pn_lower == name_lower + ".exe" or
                    pn_lower == name_lower
                )
                if match:
                    procs_to_kill.append(proc)
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass

        for proc in procs_to_kill:
            try:
                proc.terminate()
                killed_any = True
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass

        if killed_any:
            # Give processes 2s to terminate gracefully, then force-kill
            import time as _time
            _time.sleep(0.5)
            for proc in procs_to_kill:
                try:
                    if proc.is_running():
                        proc.kill()
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    pass
            return {"action": "close_app", "app": name, "reply": f"{name.capitalize()} has been closed."}

    # Fallback: taskkill on Windows
    if OS == "Windows" and process_filename:
        result = subprocess.run(
            f'taskkill /F /IM "{process_filename}" /T',
            shell=True, capture_output=True, text=True
        )
        print(f"[CIPHER] taskkill result: rc={result.returncode} stderr={result.stderr[:100]}")
        if result.returncode == 0 or "SUCCESS" in result.stdout.upper():
            return {"action": "close_app", "app": name, "reply": f"{name.capitalize()} has been closed."}
        # Try without exe extension — user might have said app name only
        bare_name = name_lower.replace(" ", "")
        result2 = subprocess.run(
            f'taskkill /F /IM "{bare_name}.exe" /T',
            shell=True, capture_output=True, text=True
        )
        if result2.returncode == 0 or "SUCCESS" in result2.stdout.upper():
            return {"action": "close_app", "app": name, "reply": f"{name.capitalize()} has been closed."}

    return {"action": "close_app", "app": name, "reply": f"Could not find a running process for '{name}'. Make sure it is open."}


def close_window_by_title(keyword: str) -> dict:
    """Close a window (e.g. browser tab/window) whose title contains keyword."""
    if IS_CLOUD:
        return {"action": "close_window",
                "reply": "Closing browser windows/tabs is only supported when running CIPHER locally on your device."}
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
    if not IS_CLOUD:
        webbrowser.open(url)
    return {"action": "open_website", "url": url, "site_name": site_name, "status": "ok"}


def open_app(name: str) -> dict:
    """Open a known desktop application."""
    if IS_CLOUD:
        return {"action": "open_app", "app": name, "status": "cloud_unsupported",
                "reply": f"Opening local applications (like {name.capitalize()}) is only supported when running CIPHER locally on your device."}
    name = name.lower().strip()
    cmd = APP_MAP.get(name, {}).get(OS)
    if cmd:
        run_cmd(cmd)
        return {"action": "open_app", "app": name, "status": "ok"}
    return {"action": "open_app", "app": name, "status": "not_found"}


def get_system_info() -> dict:
    """Return real system information from this machine."""
    # ── Processor: read from registry on Windows for real CPU brand string ──
    processor = platform.processor() or platform.machine()
    if OS == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            processor = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[CIPHER] winreg CPU read failed: {e}")
    elif OS == "Darwin":
        try:
            import subprocess as _sp
            out = _sp.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
            if out:
                processor = out
        except:
            pass
    elif OS == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line.lower():
                        processor = line.split(":", 1)[1].strip()
                        break
        except:
            pass

    # ── RAM: use psutil for accurate total ──
    ram_str = "Unknown"
    if _psutil:
        try:
            mem = _psutil.virtual_memory()
            ram_gb = round(mem.total / (1024 ** 3), 1)
            ram_str = f"{ram_gb} GB"
        except Exception as e:
            print(f"[CIPHER] psutil RAM read failed: {e}")

    # ── Hostname ──
    try:
        import socket
        hostname = socket.gethostname()
    except:
        hostname = "Unknown"

    return {
        "os": f"{OS} {platform.release()}",
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": processor,
        "ram": ram_str,
        "hostname": hostname,
        "python": sys.version.split()[0],
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%A, %B %d %Y"),
    }


_last_screenshot_time = 0
_screenshot_lock = threading.Lock()

def screenshot() -> dict:
    """Take a screenshot and save to Desktop. Has a 10-second cooldown to prevent repeat triggers."""
    if IS_CLOUD:
        return {"action": "screenshot", "status": "error",
                "reply": "Taking screenshots is only supported when running CIPHER locally on your device."}
    global _last_screenshot_time
    with _screenshot_lock:
        now = time.time()
        if now - _last_screenshot_time < 10:
            remaining = round(10 - (now - _last_screenshot_time))
            return {"action": "screenshot", "status": "cooldown",
                    "reply": f"Screenshot taken just now. Please wait {remaining}s before taking another."}
        _last_screenshot_time = now
    try:
        from PIL import ImageGrab
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        fname = desktop / f"cipher_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img = ImageGrab.grab()
        img.save(fname)
        return {"action": "screenshot", "path": str(fname), "status": "ok",
                "reply": f"Screenshot saved to Desktop as {fname.name}."}
    except ImportError:
        return {"action": "screenshot", "status": "error", "detail": "Pillow not installed",
                "reply": "Screenshot failed: install Pillow (pip install pillow)."}
    except Exception as e:
        return {"action": "screenshot", "status": "error", "detail": str(e),
                "reply": f"Screenshot failed: {e}"}


def _windows_set_volume(level: int) -> bool:
    """Set Windows master volume. Tries pycaw first, then PowerShell COM fallback."""
    scalar = round(level / 100.0, 6)
    # Method 1: pycaw (preferred)
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = interface.QueryInterface(IAudioEndpointVolume)
        vol.SetMasterVolumeLevelScalar(scalar, None)
        print(f"[Volume] pycaw -> {level}%")
        return True
    except Exception as e:
        print(f"[Volume] pycaw failed ({e}), using PowerShell...")
    # Method 2: PowerShell + inline C# (no extra packages needed)
    # IAudioEndpointVolume vtable after IUnknown (0-2):
    #   3:RegisterControlChangeNotify  4:UnregisterControlChangeNotify
    #   5:GetChannelCount  6:SetMasterVolumeLevel(dB)  7:GetMasterVolumeLevel(dB)
    #   8:SetMasterVolumeLevelScalar  <- 5 gap methods needed
    cs_type = (
        'using System; using System.Runtime.InteropServices;\n'
        '[ComImport,Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDev {}\n'
        '[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n'
        'interface IMMEnum { int _x(); [PreserveSig] int GetDef(int a,int b,out IMMD d); }\n'
        '[Guid("D666063F-1587-4E43-81F1-B948E807363F"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n'
        'interface IMMD { [PreserveSig] int Act(ref Guid g,uint c,IntPtr p,[MarshalAs(UnmanagedType.IUnknown)] out object v); }\n'
        '[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n'
        'interface IAEVol { int _1();int _2();int _3();int _4();int _5(); [PreserveSig] int SetScalar(float v,Guid g); }\n'
        'public static class VC {\n'
        '    public static void Set(float v) {\n'
        '        var e=(IMMEnum)(new MMDev()); IMMD d; e.GetDef(0,1,out d);\n'
        '        Guid g=new Guid("5CDF2C82-841E-4546-9722-0CF74078229A"); object ep; d.Act(ref g,23,IntPtr.Zero,out ep);\n'
        '        ((IAEVol)ep).SetScalar(v,Guid.Empty);\n'
        '    }\n'
        '}'
    )
    ps_script = f"Add-Type -TypeDefinition @'\n{cs_type}\n'@ -ErrorAction Stop\n[VC]::Set([float]{scalar})\n"
    try:
        tmp = Path(os.environ.get('TEMP', str(Path(__file__).parent))) / '_cv.ps1'
        tmp.write_text(ps_script, encoding='utf-8')
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(tmp)],
            capture_output=True, text=True, timeout=12
        )
        try: tmp.unlink()
        except: pass
        if r.returncode == 0:
            print(f"[Volume] PowerShell -> {level}%")
            return True
        print(f"[Volume] PS error: {r.stderr[:200]}")
    except Exception as e:
        print(f"[Volume] PS exception: {e}")
    return False


def set_volume(level: int) -> dict:
    """Set system volume (0-100). Works on Windows/macOS/Linux."""
    if IS_CLOUD:
        return {"action": "set_volume", "level": level, "status": "error",
                "reply": "Volume control is only supported when running CIPHER locally on your device."}
    level = max(0, min(100, level))
    if OS == "Windows":
        ok = _windows_set_volume(level)
        reply = f"Volume set to {level}%." if ok else f"Volume command sent ({level}%) — if unchanged, run: pip install pycaw"
    elif OS == "Darwin":
        run_cmd(f"osascript -e 'set volume output volume {level}'")
        reply = f"Volume set to {level}%."
    elif OS == "Linux":
        run_cmd(f"amixer -q sset Master {level}%")
        reply = f"Volume set to {level}%."
    else:
        reply = f"Volume control not supported on {OS}."
    return {"action": "set_volume", "level": level, "status": "ok", "reply": reply}


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
        if is_offline_error(e):
            return {
                "action": "weather",
                "status": "offline",
                "reply": f"Weather service is unavailable while offline. All local desktop controls (apps, volume, notes, traps) remain active."
            }
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
    if IS_CLOUD:
        return {"action": "open_folder", "reply": "Accessing local folders is only supported when running CIPHER locally on your device."}
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
        # Use GiB (1024^3) so a 64 GiB laptop shows ~64 not 68 (GB vs GiB difference)
        _GiB = 1024 ** 3
        mem_used  = round(mem.used  / _GiB, 1)
        mem_total = round(mem.total / _GiB, 1)
        battery = _psutil.sensors_battery()
        parts = [f"CPU: {cpu}%", f"RAM: {mem_used} GiB / {mem_total} GiB ({mem.percent}%)"]
        if battery:
            plug_status = "charging" if battery.power_plugged else "on battery"
            parts.append(f"Battery: {round(battery.percent)}% ({plug_status})")
        else:
            parts.append("Battery: not detected")
        
        reply = " | ".join(parts)
        if IS_CLOUD:
            reply = f"☁️ Cloud Server Stats: {reply} (Note: CIPHER is running in cloud mode)"
        return {"action": "battery_cpu", "reply": reply}
    except Exception as e:
        return {"action": "battery_cpu", "reply": f"Could not get system stats: {e}"}


# ── Disk Space & Storage ──────────────────────────────────────────────────
def get_disk_space() -> dict:
    if not _psutil:
        return {"action": "disk_space", "reply": "psutil not installed."}
    try:
        path = "C:\\" if OS == "Windows" else "/"
        usage = _psutil.disk_usage(path)
        _GiB = 1024 ** 3
        total_gb = round(usage.total / _GiB, 1)
        used_gb  = round(usage.used  / _GiB, 1)
        free_gb  = round(usage.free  / _GiB, 1)
        percent  = usage.percent
        reply = f"💾 Storage ({path}): {free_gb} GB free of {total_gb} GB ({percent}% used)."
        return {
            "action": "disk_space",
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent": percent,
            "path": path,
            "reply": reply,
            "status": "ok"
        }
    except Exception as e:
        return {"action": "disk_space", "reply": f"Could not check disk space: {e}", "status": "error"}


# ── Timers & Countdowns ───────────────────────────────────────────────────
_ACTIVE_TIMERS = {}
_TIMER_LOCK = threading.Lock()

def set_timer(duration_seconds: int, label: str = "") -> dict:
    if duration_seconds <= 0:
        return {"action": "timer", "status": "error", "reply": "Timer duration must be positive."}
    if duration_seconds > 86400:
        return {"action": "timer", "status": "error", "reply": "Timer cannot exceed 24 hours."}
    
    end_time = time.time() + duration_seconds
    with _TIMER_LOCK:
        _ACTIVE_TIMERS["main"] = {
            "duration": duration_seconds,
            "end_time": end_time,
            "label": label or f"{duration_seconds}s",
            "started_at": time.time()
        }
    
    m, s = divmod(duration_seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h > 0:
        parts.append(f"{h} hour{'s' if h > 1 else ''}")
    if m > 0:
        parts.append(f"{m} minute{'s' if m > 1 else ''}")
    if s > 0 or not parts:
        parts.append(f"{s} second{'s' if s > 1 else ''}")
    time_desc = " ".join(parts)
    return {
        "action": "timer",
        "subaction": "set",
        "duration": duration_seconds,
        "remaining": duration_seconds,
        "reply": f"⏱️ Timer set for {time_desc}."
    }

def get_timer_status() -> dict:
    with _TIMER_LOCK:
        timer = _ACTIVE_TIMERS.get("main")
        if not timer:
            return {"action": "timer", "subaction": "status", "reply": "No active timer."}
        rem = int(timer["end_time"] - time.time())
        if rem <= 0:
            return {"action": "timer", "subaction": "status", "remaining": 0, "reply": "⏱️ Timer has finished!"}
        m, s = divmod(rem, 60)
        h, m = divmod(m, 60)
        parts = []
        if h > 0:
            parts.append(f"{h}h")
        if m > 0:
            parts.append(f"{m}m")
        parts.append(f"{s}s")
        time_str = " ".join(parts)
        return {
            "action": "timer",
            "subaction": "status",
            "remaining": rem,
            "reply": f"⏱️ Timer: {time_str} remaining."
        }

def cancel_timer() -> dict:
    with _TIMER_LOCK:
        if "main" in _ACTIVE_TIMERS:
            del _ACTIVE_TIMERS["main"]
            return {"action": "timer", "subaction": "cancel", "reply": "⏱️ Timer cancelled."}
        return {"action": "timer", "subaction": "cancel", "reply": "No active timer to cancel."}

def parse_timer_seconds(text: str):
    t = text.lower().strip()
    hours = re.search(r'(\d+)\s*(?:hour|hr)s?', t)
    mins = re.search(r'(\d+)\s*(?:minute|min)s?', t)
    secs = re.search(r'(\d+)\s*(?:second|sec)s?', t)
    total = 0
    if hours:
        total += int(hours.group(1)) * 3600
    if mins:
        total += int(mins.group(1)) * 60
    if secs:
        total += int(secs.group(1))
    if total > 0:
        return total
    short_m = re.search(r'timer\s+(?:for\s+)?(\d+)\s*m\b', t)
    if short_m:
        return int(short_m.group(1)) * 60
    short_s = re.search(r'timer\s+(?:for\s+)?(\d+)\s*s\b', t)
    if short_s:
        return int(short_s.group(1))
    return None


# ── Network IP & Diagnostics ──────────────────────────────────────────────
def get_network_diagnostics() -> dict:
    hostname = socket.gethostname()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
        
    online = check_internet_connection()
    status_str = "Connected (Online)" if online else "Disconnected (Offline Mode)"
    reply = (
        f"🌐 Network Diagnostics:\n"
        f"• Local IP: {local_ip}\n"
        f"• Hostname: {hostname}\n"
        f"• Internet: {status_str}"
    )
    return {
        "action": "network_diagnostics",
        "local_ip": local_ip,
        "hostname": hostname,
        "online": online,
        "reply": reply,
        "status": "ok"
    }


# ── Recycle Bin Cleaner ───────────────────────────────────────────────────
def empty_recycle_bin() -> dict:
    if IS_CLOUD:
        return {"action": "empty_recycle_bin", "reply": "Recycle bin cleaning is only supported on a local device."}
    if OS == "Windows":
        try:
            cmd = 'powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"'
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return {"action": "empty_recycle_bin", "status": "ok", "reply": "🗑️ Recycle Bin has been emptied."}
        except Exception as e:
            return {"action": "empty_recycle_bin", "status": "error", "reply": f"Could not empty Recycle Bin: {e}"}
    return {"action": "empty_recycle_bin", "reply": "Recycle Bin cleaner is only supported on Windows."}


# ── Desktop Folder Creator ────────────────────────────────────────────────
def create_desktop_folder(folder_name: str) -> dict:
    if IS_CLOUD:
        return {"action": "create_folder", "reply": "Desktop creation is only supported on a local device."}
    try:
        clean_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip()
        if not clean_name:
            return {"action": "create_folder", "status": "error", "reply": "Please specify a valid folder name."}
        desktop = Path.home() / "Desktop"
        target = desktop / clean_name
        target.mkdir(parents=True, exist_ok=True)
        return {"action": "create_folder", "status": "ok", "reply": f"📁 Created folder '{clean_name}' on your Desktop."}
    except Exception as e:
        return {"action": "create_folder", "status": "error", "reply": f"Could not create folder: {e}"}


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
    if IS_CLOUD:
        return {"action": "focus_mode", "reply": "Focus mode is only supported when running CIPHER locally on your device."}
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


# ── Switch to window (tab switcher) ─────────────────────────────
def switch_to_window(keyword: str) -> dict:
    if IS_CLOUD:
        return {"action": "switch_window", "reply": "Window switching is only supported when running CIPHER locally on your device."}
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


# ── Background Apps ───────────────────────────────────────────────────────────
def get_running_apps() -> dict:
    """Get a list of currently running visible windows/apps."""
    if IS_CLOUD:
        return {"action": "running_apps", "apps": [], "reply": "Retrieving background applications is only supported when running CIPHER locally on your device."}
    if OS != "Windows":
        return {"action": "running_apps", "apps": [], "reply": "This feature is only supported on Windows."}
    try:
        import ctypes
        apps = []
        def enum_handler(hwnd, _):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0 and ctypes.windll.user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                # Filter out default Windows 10/11 system windows
                ignore_titles = ["Program Manager", "Settings", "Microsoft Text Input Application", "Taskbar", "Snipping Tool"]
                if title not in ignore_titles and "cipher" not in title.lower() and "gemini" not in title.lower() and "default ime" not in title.lower() and "msctfime" not in title.lower():
                    apps.append(title)
            return True
            
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
        
        unique_apps = list(set(apps))
        
        if not unique_apps:
            return {"action": "running_apps", "apps": [], "reply": "No background applications found."}
            
        return {"action": "running_apps", "apps": unique_apps, "reply": f"Found {len(unique_apps)} background applications."}
    except Exception as e:
        print(f"[CIPHER] get_running_apps error: {e}")
        return {"action": "running_apps", "apps": [], "reply": f"Couldn't get running applications."}


# ── Top Memory / CPU Processes ────────────────────────────────────────────
def get_top_processes(n: int = 5) -> dict:
    if not _psutil:
        return {"action": "top_processes", "reply": "psutil not installed."}
    try:
        proc_map = {}
        for p in _psutil.process_iter(['name', 'memory_info']):
            try:
                name = p.info.get('name')
                if not name:
                    continue
                mem_info = p.info.get('memory_info')
                if mem_info:
                    proc_map[name] = proc_map.get(name, 0) + mem_info.rss
            except (Exception,):
                pass
        
        sorted_procs = sorted(proc_map.items(), key=lambda x: x[1], reverse=True)[:n]
        lines = []
        for i, (name, rss) in enumerate(sorted_procs, 1):
            if rss >= 1024 ** 3:
                size_str = f"{round(rss / (1024 ** 3), 1)} GB"
            else:
                size_str = f"{round(rss / (1024 ** 2))} MB"
            lines.append(f"{i}. {name} — {size_str}")
            
        reply = "🧠 Top Memory-Consuming Processes:\n" + "\n".join(lines)
        return {
            "action": "top_processes",
            "processes": [{"name": k, "rss_bytes": v} for k, v in sorted_procs],
            "reply": reply,
            "status": "ok"
        }
    except Exception as e:
        return {"action": "top_processes", "reply": f"Could not list processes: {e}", "status": "error"}

# ── Intent router ─────────────────────────────────────────────────────────────


def route_intent(text: str):
    """
    Try to match a local OS intent before calling Gemini.
    Returns a dict result if handled locally, else None.

    COMMAND SEMANTICS (strictly enforced):
      'open X'         -> prefer browser / SITE_MAP first, then APP_MAP, never universal_launch
      'launch/start/run X' -> prefer APP_MAP / universal_launch (OS app), then SITE_MAP as fallback
    """
    global chat_history
    original = text
    t = text.lower().strip()
    # Remove trailing punctuation
    t = re.sub(r'[.!?]+$', '', t).strip()

    print(f"[CIPHER] Processing: {t}")

    # ── Detect verb intent ────────────────────────────────────────────
    has_open   = bool(re.search(r'\bopen\b', t))
    has_launch = bool(re.search(r'\b(?:launch|start|run)\b', t))

    # ── 'open X' branch: browser/website first ───────────────────────
    if has_open and not has_launch:
        # Extract the target name after 'open [the] ...'
        m = re.search(r'\bopen\s+(?:the\s+)?(.+?)\s*$', t)
        if m:
            raw = m.group(1).strip()
            # 1. Known site → always open in browser
            if raw in SITE_MAP:
                return open_website(SITE_MAP[raw], raw.capitalize())
            # 2. Multi-word site check (e.g. 'prime video')
            for site_name in sorted(SITE_MAP.keys(), key=len, reverse=True):
                if raw.startswith(site_name) or raw == site_name:
                    return open_website(SITE_MAP[site_name], site_name.capitalize())
            # 3. Known desktop app → launch it
            for app_name in sorted(APP_MAP.keys(), key=len, reverse=True):
                if raw == app_name or raw.startswith(app_name):
                    result = open_app(app_name)
                    if result['status'] in ('ok', 'cloud_unsupported'):
                        return result
            # 4. Looks like a URL/domain → open in browser
            if '.' in raw:
                return open_website(raw, raw.split('.')[0].capitalize())
            # 5. Unknown short name → try as website first (.com)
            if len(raw.split()) <= 2:
                return open_website(f"https://www.{raw}.com", raw.capitalize())

    # ── 'launch/start/run X' branch: OS app first ────────────────────
    if has_launch:
        m = re.search(r'\b(?:launch|start|run)\s+(?:the\s+)?(.+?)\s*$', t)
        if m:
            raw = m.group(1).strip()
            # 1. Known desktop app → launch
            for app_name in sorted(APP_MAP.keys(), key=len, reverse=True):
                if raw == app_name or raw.startswith(app_name):
                    result = open_app(app_name)
                    if result['status'] in ('ok', 'cloud_unsupported'):
                        return result
            # 2. Not in APP_MAP → try universal OS launcher
            if '.' not in raw and len(raw.split()) <= 3:
                return universal_launch(raw)
            # 3. If it looks like a web-only thing, fall back to browser
            if raw in SITE_MAP:
                return open_website(SITE_MAP[raw], raw.capitalize())

    # ── 'open' with launch verb also present (edge case) ────────────
    if has_open and has_launch:
        m = re.search(r'\b(?:open|launch|start|run)\s+(?:the\s+)?(.+?)\s*$', t)
        if m:
            raw = m.group(1).strip()
            if raw in SITE_MAP:
                return open_website(SITE_MAP[raw], raw.capitalize())
            for app_name in sorted(APP_MAP.keys(), key=len, reverse=True):
                if raw == app_name or raw.startswith(app_name):
                    result = open_app(app_name)
                    if result['status'] in ('ok', 'cloud_unsupported'):
                        return result
            return universal_launch(raw)

    open_trigger = has_open or has_launch

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
    if any(kw in t for kw in ["system info", "system information", "what os", "my system", "about my computer", "computer info", "device info", "hardware info"]):
        info = get_system_info()
        return {
            "action": "system_info",
            "reply": (
                f"💻 System: {info['os']}\n"
                f"🖥  Host: {info.get('hostname', 'Unknown')}\n"
                f"⚙️  CPU: {info['processor']}\n"
                f"🧠 RAM: {info.get('ram', 'Unknown')}\n"
                f"🕐 Time: {info['time']}  |  📅 Date: {info['date']}"
            ),
        }

    # ── Screenshot ────────────────────────────────────────────────────────────
    if any(kw in t for kw in ["screenshot", "screen shot", "take a screenshot", "capture screen"]):
        return screenshot()

    # ── Volume ────────────────────────────────────────────────────────────────
    vol_patterns = [
        r'set\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)',
        r'volume\s+(?:to\s+|at\s+|level\s+)?(\d+)',
        r'change\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)',
        r'(\d+)\s*(?:percent|%)\s*volume',
        r'volume\s+(?:to\s+)?(\d+)\s*(?:percent|%)?',
        r'set\s+(?:it\s+)?to\s+(\d+)\s*(?:percent|%)?(?:\s+volume)?',
        r'(?:make|put)\s+(?:the\s+)?volume\s+(?:at\s+)?(\d+)',
        r'(\d+)\s+volume',
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
        if IS_CLOUD:
            return {"action": "mute", "status": "error", "reply": "Mute control is only supported when running CIPHER locally on your device."}
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
        if IS_CLOUD:
            return {"action": "unmute", "status": "error", "reply": "Volume control is only supported when running CIPHER locally on your device."}
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

    # ── Media Control (Play/Pause/Next/Prev) ──────────────────────────────────
    if any(kw in t for kw in ["pause music", "resume music", "play music", "pause song", "resume song", "play/pause", "pause playback"]):
        if IS_CLOUD:
            return {"action": "media_play_pause", "reply": "Media controls are only supported when running CIPHER locally on your device."}
        if OS == "Windows":
            import ctypes
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)  # VK_MEDIA_PLAY_PAUSE
            ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
            return {"action": "media_play_pause", "reply": "Toggling playback."}
        return {"action": "media_play_pause", "reply": "Media controls only supported on Windows."}

    if any(kw in t for kw in ["next song", "next track", "skip song", "skip track"]):
        if IS_CLOUD:
            return {"action": "media_next", "reply": "Media controls are only supported when running CIPHER locally on your device."}
        if OS == "Windows":
            import ctypes
            ctypes.windll.user32.keybd_event(0xB5, 0, 0, 0)  # VK_MEDIA_NEXT_TRACK
            ctypes.windll.user32.keybd_event(0xB5, 0, 2, 0)
            return {"action": "media_next", "reply": "Playing next track."}
        return {"action": "media_next", "reply": "Media controls only supported on Windows."}

    if any(kw in t for kw in ["previous song", "previous track", "prev song", "prev track", "go back song"]):
        if IS_CLOUD:
            return {"action": "media_prev", "reply": "Media controls are only supported when running CIPHER locally on your device."}
        if OS == "Windows":
            import ctypes
            ctypes.windll.user32.keybd_event(0xB6, 0, 0, 0)  # VK_MEDIA_PREV_TRACK
            ctypes.windll.user32.keybd_event(0xB6, 0, 2, 0)
            return {"action": "media_prev", "reply": "Playing previous track."}
        return {"action": "media_prev", "reply": "Media controls only supported on Windows."}

    # ── Date / time ───────────────────────────────────────────────────────────
    if any(kw in t for kw in ["what time", "what's the time", "current time", "time is it"]):
        return {"action": "time", "reply": f"It's {datetime.now().strftime('%H:%M:%S')}."}

    if any(kw in t for kw in ["what date", "what's today", "today's date", "what day"]):
        return {"action": "date", "reply": f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."}

    # ── Lock Screen ───────────────────────────────────────────────────────────
    if any(kw in t for kw in ["lock computer", "lock screen", "lock my computer", "lock the computer"]):
        if IS_CLOUD:
            return {"action": "lock", "reply": "Locking the computer is only supported when running CIPHER locally on your device."}
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

    # ── Disk Space & Storage ──────────────────────────────────────────
    if any(kw in t for kw in ["disk space", "storage", "hard drive space", "free space", "storage info", "disk usage", "how much storage", "how much space", "free disk"]):
        return get_disk_space()

    # ── Top Memory & CPU Processes ────────────────────────────────────
    if any(kw in t for kw in ["top processes", "top apps", "what is using my ram", "what's using my ram", "what is using my memory", "memory hogs", "heavy apps", "ram usage details", "what is slowing down my pc", "ram heavy"]):
        return get_top_processes(5)

    # ── Timers ────────────────────────────────────────────────────────
    if any(kw in t for kw in ["cancel timer", "stop timer", "clear timer", "delete timer"]):
        return cancel_timer()
    if any(kw in t for kw in ["check timer", "timer status", "timer remaining", "how much time left on timer"]):
        return get_timer_status()
    if "timer" in t:
        secs = parse_timer_seconds(t)
        if secs:
            return set_timer(secs)

    # ── Network IP / Diagnostics ──────────────────────────────────────────────
    if any(kw in t for kw in ["what is my ip", "my ip", "what's my ip", "local ip", "ip address", "network diagnostics", "network details"]):
        return get_network_diagnostics()

    # ── Empty Recycle Bin ─────────────────────────────────────────────────────
    if any(kw in t for kw in ["empty recycle bin", "clean recycle bin", "empty trash", "clear recycle bin", "clean trash"]):
        return empty_recycle_bin()

    # ── Create Desktop Folder ─────────────────────────────────────────────────
    create_folder_m = re.search(r'(?:create|make|new)\s+(?:a\s+)?folder\s+(?:named\s+|called\s+)?["\']?(.+?)["\']?(?:\s+on\s+desktop)?\s*$', t)
    if create_folder_m:
        folder_name = create_folder_m.group(1).strip()
        folder_name = re.sub(r'\s+on\s+desktop$', '', folder_name, flags=re.IGNORECASE).strip()
        if folder_name and folder_name.lower() not in ['on desktop', 'desktop']:
            return create_desktop_folder(folder_name)

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

    # ── Background Apps ───────────────────────────────────────────────────────
    if any(kw in t for kw in ["background apps", "running apps", "what applications are running", "what's running", "apps running", "running applications"]):
        return get_running_apps()

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
    # e.g. "close whatsapp", "close spotify", "close word", "close the chrome app"
    close_app_match = re.search(
        r'\b(?:close|quit|exit|kill)\b\s+(?:the\s+)?([a-z0-9\s]+?)(?:\s+(?:app|application|program|software|window|now))?\s*$', t
    )
    if close_app_match:
        target = close_app_match.group(1).strip()
        # Exclude cases that are already handled above (tabs/windows/browser)
        if not any(w in t for w in ['tab', 'window', 'page']):
            if target:  # Don't call with empty string
                return close_app(target)

    # ── Sleep / Stop Listening ────────────────────────────────────────────────
    SLEEP_KWS = [
        "cipher sleep", "go to sleep", "sleep cipher", "stop listening",
        "goodbye cipher", "bye cipher", "cipher goodbye", "take a break",
        "cipher stop", "stop cipher", "that's all", "thats all",
        "i'm done", "im done", "cipher rest", "go to rest", "sleep now",
    ]
    if any(kw in t for kw in SLEEP_KWS):
        return {
            "action": "sleep",
            "reply": "Going to sleep. Mic off. Click the mic icon to wake me up."
        }

    # ── Help / Commands ───────────────────────────────────────────────────────
    if any(t == kw for kw in ["help", "commands", "show commands", "what can you do", "list commands", "help me"]):
        return {
            "action": "help",
            "reply": (
                "Here are some commands you can ask me (all desktop controls work 100% offline!):\n"
                "• 'open <website>' (e.g. open youtube, open github)\n"
                "• 'launch <app>' (e.g. launch notepad, open calculator, open powershell)\n"
                "• 'set volume to <0-100>' or 'mute' / 'unmute'\n"
                "• 'take a screenshot' or 'lock screen'\n"
                "• 'system stats' or 'battery status'\n"
                "• 'calculate <expression>' (e.g. calculate 25 * 4, 150 / 3)\n"
                "• 'internet status' / 'check connection'\n"
                "• 'weather in <city>'\n"
                "• 'note: <text>' or 'read notes'\n"
                "• 'focus mode on' / 'focus mode off'\n"
                "• 'run trap <name>' (e.g. run trap beast)\n"
                "• 'answer this <question>' for AI answers"
            )
        }

    # ── Internet / Connection Status ──────────────────────────────────────────
    if any(kw in t for kw in ["internet status", "check internet", "am i online", "is internet working", "network status", "wifi status", "connection status"]):
        online = check_internet_connection()
        if online:
            return {"action": "network_status", "status": "online", "reply": "🌐 Internet is connected and active. Cloud AI & online voice recognition are available."}
        return {"action": "network_status", "status": "offline", "reply": "📡 You are currently offline. CIPHER Offline Desktop Engine is active — all local PC commands work without internet."}

    # ── Offline Math / Calculator ─────────────────────────────────────────────
    math_m = re.match(r'^(?:calculate|compute|solve|what is|how much is)\s+([0-9\.\s\+\-\*\/\(\)\%\^]+)$', t)
    if not math_m:
        if re.match(r'^\s*\(?\d+[\d\.\s\+\-\*\/\(\)\%]+\d\)?\s*$', t) and any(op in t for op in ['+', '-', '*', '/', '%']):
            math_m = re.match(r'^\s*(.+?)\s*$', t)
    if math_m:
        expr = math_m.group(1).strip()
        try:
            val = safe_eval_math(expr)
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            return {"action": "calculator", "reply": f"Result: {expr} = {val}"}
        except Exception:
            pass

    # ── Basic Greetings ───────────────────────────────────────────────────────
    if any(t == kw for kw in ["hello", "hi", "hey cipher", "hey", "who are you", "what is cipher"]):
        return {
            "action": "greeting",
            "reply": "Hello! I am CIPHER, your desktop AI assistant. How can I help you today? Say 'help' to see available commands."
        }

    return None  # Not handled locally -> fall through to Gemini


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/app")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "app": "CIPHER",
        "version": "2.5",
        "os": OS,
        "cloud": IS_CLOUD,
        "online": check_internet_connection(),
        "gemini_configured": bool(client)
    })


@app.route("/app")
def serve_app():
    """Serve the app interface at http://localhost:5000/app"""
    return send_from_directory(Path(__file__).parent / 'docs', 'app.html')


@app.route("/cipher.html")
def legacy_cipher_html():
    """Redirect legacy cipher.html requests to /app."""
    return redirect("/app")


@app.route("/landing")
def landing():
    """Serve the landing/docs page at http://localhost:5000/landing"""
    return send_from_directory(Path(__file__).parent / 'docs', 'index.html')


@app.route("/cipher_logo.png")
def serve_logo():
    """Serve the logo so the app interface finds it."""
    return send_from_directory(Path(__file__).parent / 'docs' / 'images', 'logo.png')


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
    if IS_CLOUD:
        return {"action": "trap_run", "opened": [], "failed": [],
                "reply": "Traps are only supported when running CIPHER locally on your device."}
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
    if IS_CLOUD:
        return {"action": "trap_close", "closed": [], "not_found": [],
                "reply": "Traps are only supported when running CIPHER locally on your device."}
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

    # ── "answer this" / "ask ai" bypass → skip local routing, force Gemini ─────
    answer_this = re.match(
        r'^(?:answer\s+this|ask\s+ai|ask\s+gemini|ai\s+ask|gemini\s+answer|ai\s+answer)\s*[:\-]?\s*(.+)',
        user_input, re.IGNORECASE
    )
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
    if not client:
        return jsonify({
            "reply": "I am not configured with a Gemini API key yet. Please add your GEMINI_API_KEY environment variable on your Railway service dashboard, then redeploy.",
            "error": "GEMINI_API_KEY is missing"
        }), 500
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
        if is_offline_error(e):
            return jsonify({
                "reply": (
                    "📡 You are currently offline (no internet connection).\n\n"
                    "CIPHER Offline Mode is active! You can still control your PC with local commands:\n"
                    "• Launch apps ('open notepad', 'launch calculator', 'open powershell')\n"
                    "• Volume & Media ('volume 60', 'mute', 'unmute', 'next track')\n"
                    "• System stats & hardware ('battery status', 'cpu usage', 'system info')\n"
                    "• Utilities ('take a screenshot', 'lock screen', 'note: <text>', 'read notes')\n"
                    "• Math & calculations ('calculate 25 * 4', 'what is 100 / 5')\n"
                    "• Clipboard ('read clipboard', 'copy <text>')\n"
                    "• Traps ('run trap beast')\n"
                    "• Date & time ('what time is it', 'what is today's date')"
                ),
                "action": "offline_mode",
                "offline": True
            }), 200
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


@app.route("/sysstats", methods=["GET"])
def sysstats():
    if not _psutil:
        return jsonify({"error": "psutil not installed"}), 500
    try:
        # Use interval=None to read CPU non-blockingly
        cpu = _psutil.cpu_percent(interval=None)
        mem = _psutil.virtual_memory()
        _GiB = 1024 ** 3
        ram_used = round(mem.used / _GiB, 1)
        ram_total = round(mem.total / _GiB, 1)
        ram_percent = mem.percent
        
        battery = _psutil.sensors_battery()
        battery_data = {
            "present": False,
            "percent": 0,
            "charging": False
        }
        if battery:
            battery_data["present"] = True
            battery_data["percent"] = round(battery.percent)
            battery_data["charging"] = battery.power_plugged

        disk_info = get_disk_space()
            
        return jsonify({
            "cpu": cpu,
            "ram_used": ram_used,
            "ram_total": ram_total,
            "ram_percent": ram_percent,
            "battery": battery_data,
            "disk": disk_info
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    if IS_CLOUD:
        print("   Mode: CLOUD (Action features disabled)")
    print("="*36)
    print()
    print(f"[CIPHER] Server starting on port {port}")
    print(f"[CIPHER] Open the app at: https://localhost:{port}/app")
    print("[CIPHER] API ready at:    https://localhost:{}/chat".format(port))
    print("[CIPHER] NOTE: Your browser may warn you about an unsafe certificate.")
    print("         Click 'Advanced' -> 'Proceed to localhost' to continue.")
    print()
    try:
        app.run(host="0.0.0.0", port=port, debug=False, ssl_context='adhoc')
    except Exception as e:
        print(f"[CIPHER] ERROR starting HTTPS server: {e}")
        print("         Please ensure you have installed: pip install pyopenssl cryptography")
        print("         Falling back to HTTP (mic permissions will NOT be saved)...")
        app.run(host="0.0.0.0", port=port, debug=False)