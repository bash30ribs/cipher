# CIPHER — Desktop AI Assistant v2.5

> Voice-powered AI assistant with OS control, built on Gemini + Flask.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/hrishav2208/CIPHER.github.io)
[![Live Demo](https://img.shields.io/badge/Live-Demo-4cc9f0?style=for-the-badge)](https://hrishav2208.github.io/CIPHER.github.io/)

**🚀 ADVANCED VERSION — NOW LIVE & CLOUD-READY**

---

## ✨ Features

### 🎤 **Voice Command Execution**
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
```
Open `cipher.html` in Chrome/Edge, click the mic, and say **"Hey Cipher, show my system stats!"**

---

## 🎤 Command Reference

| Category | Commands |
|----------|----------|
| **Launch** | "open youtube", "launch whatsapp", "open downloads folder" |
| **Control** | "set volume to 80", "lock screen", "take a screenshot" |
| **Stats** | "battery status", "cpu usage", "performance" |
| **Environment** | "weather in Paris", "current temperature" |
| **Productivity** | "note: meeting at 3pm", "show my notes", "read clipboard" |
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

## 🛠️ Requirements
- Python 3.10+
- Chrome/Edge (for Speech API)
- Windows (Primary support), macOS/Linux (Partial)

---

## 📄 License
MIT — Go wild! 🚀