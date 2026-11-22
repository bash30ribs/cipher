# CIPHER — Desktop AI Assistant v2.5

> Voice-powered AI assistant with OS control, built on Gemini + Flask.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/hrishav2208/CIPHER.github.io)
[![Live Demo](https://img.shields.io/badge/Live-Demo-4cc9f0?style=for-the-badge)](https://hrishav2208.github.io/CIPHER.github.io/)

**🚀 ADVANCED VERSION — NOW LIVE & CLOUD-READY**

---

## ✨ Features

### 🎤 **Voice Command Execution**
- ✅ **100% Offline Mode**: All OS controls, app launchers, volume, system stats, notes, traps, and math work without network.
- ✅ **Live Telemetry & Animations**: Ambient floating glow orbs, dynamic network status badge, and mic radar pulses.
- ✅ **Websites & Apps**: Open any URL or local application with natural language.
- ✅ **Trap System**: Multi-launch (or close) batches of apps and sites in one go.
- ✅ **System Stats**: Live reports on Battery, CPU, and RAM usage.
- ✅ **Weather**: Real-time conditions and forecasts for any city.
- ✅ **Clipboard**: Voice-controlled copy/paste management.
- ✅ **Quick Notes**: Instant timestamped notes saved to a local file.
- ✅ **Focus Mode**: One-click distraction blocking (closes social media/apps).
- ✅ **Window Switching**: Jump between open windows using your voice (Windows only).
- ✅ **Answer This**: Direct AI spoken responses using Gemini.
- ✅ **Wake Word**: Hands-free mode with "Hey Cipher".

### 😏 **Personality**
- ✅ **Sarcastic Replies**: Hilarious feedback when the server is down or has bugs.
- ✅ **Custom Branding**: Branded with the official CIPHER logo and design language.

---

## 🚀 Quickstart

### 1. Setup (first time only)
```bash
# Clone and enter folder
# Install dependencies
pip install -r requirements.txt
```

### 2. Add your API key
Edit `.env`:
```
GEMINI_API_KEY=your_key_here
```
Get a free key → [Google AI Studio](https://aistudio.google.com/app/apikey)

### 3. Run
```bash
python server.py
# or using make
make start
```
Open `http://localhost:5000/app` (or `docs/app.html`) in Chrome/Edge, click the mic, and say **"Hey Cipher, show my system stats!"**

### 4. Run Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
# or using make
make test
```

---

## 🎤 Command Reference

| Category | Commands |
|----------|----------|
| **Help** | "help", "what can you do", "commands" |
| **Math & Decisions** | "calculate 25 * 4", "flip a coin", "roll a d20", "pick a number between 1 and 100" |
| **Network & IP** | "check internet", "internet status", "what is my ip", "local ip" |
| **Storage & RAM** | "disk space", "storage info", "what is using my ram", "top apps" |
| **System Uptime** | "system uptime", "how long has my pc been on", "boot time" |
| **Timers** | "set a timer for 10 minutes", "check timer", "cancel timer" |
| **Audio & Volume** | "what is the volume", "set volume to 80", "mute", "unmute" |
| **System Maintenance** | "empty recycle bin", "create folder ProjectX on desktop" |
| **Productivity** | "note: meeting at 3pm", "show notes", "clear notes", "read clipboard", "clear clipboard" |
| **Launch** | "open youtube", "launch whatsapp", "open downloads folder" |
| **Control** | "lock screen", "take a screenshot" |
| **Stats** | "battery status", "cpu usage", "performance" |
| **Focus** | "focus mode on", "disable distractions" |
| **Navigation** | "switch to Spotify tab", "go to Chrome window" |
| **AI** | "answer this how many days to a year?", "ai what is gravity?" |

---

## 🪤 Trap System
Create "Traps" in the UI to automate your morning or work routine.
- **Run**: "trap work"
- **Close**: "close trap work"

---

## 🎙 Wake Word
Say **"Hey Cipher"** then wait a split second for the command.
- *"Hey Cipher, open my documents."*

---

## 📡 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | `GET` | Health check & service metadata |
| `/app` | `GET` | Main UI interface |
| `/landing` | `GET` | Landing & documentation page |
| `/chat` | `POST` | Execute natural language or local commands |
| `/sysinfo` | `GET` | Host hardware & OS specifications |
| `/sysstats` | `GET` | Live CPU, RAM, and Battery telemetry |
| `/traps` | `GET` / `POST` | Retrieve or create automated Trap routines |
| `/traps/<name>/run` | `POST` | Trigger Trap execution |
| `/traps/<name>/close` | `POST` | Close apps/sites in a Trap |
| `/reset` | `POST` | Clear conversational context |

---

## 🛠️ Requirements & Cross-Platform Support
- Python 3.10+
- Chrome / Edge (for Web Speech Recognition & Audio Synthesis)
- **Universal OS Compatibility**:
  - **Windows**: PyCaw master audio scalar, PowerShell / Wscript COM, Win32 EnumWindows, taskkill, and registry CPU querying.
  - **macOS (Darwin)**: Native AppleScript via `osascript` (System Events, Music/Spotify, volume query/control, Finder trash emptying, Activity Monitor).
  - **Linux**: Native `wmctrl`, `xdotool`, `amixer`/`pactl`, `playerctl`, `gio trash`, and `/proc/cpuinfo`.

---

## 📄 License
MIT — Go wild! 🚀