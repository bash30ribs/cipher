# 🚀 CIPHER Quick Setup Guide

## What's Fixed
✅ **Websites now open** when you say "open YouTube"  
✅ **Apps now launch** when you say "open calculator"  
✅ **Searches work** properly  
✅ **Better voice command matching**  

---

## Installation (3 Steps)

### 1️⃣ Download All Files
Make sure these 5 files are in one folder:
- `cipher.html`
- `server.py`
- `requirements.txt`
- `.env.example`
- `README.md` (this file)

### 2️⃣ Setup Environment
Open terminal/command prompt in the CIPHER folder:

```bash
# Copy the environment template
cp .env.example .env

# Install Python packages
pip install -r requirements.txt
```

**Windows users:** If `pycaw` fails:
```bash
pip install pycaw comtypes pywin32
```

### 3️⃣ Add API Key
1. Get free Gemini API key: https://aistudio.google.com/app/apikey
2. Open `.env` file in notepad
3. Replace `your_gemini_api_key_here` with your actual key
4. Save the file

---

## Running CIPHER

```bash
python server.py
```

Then open `cipher.html` in Chrome or Edge browser.

---

## Test It Works

Try saying these commands (in order):

1. **"open calculator"** → Should launch calculator app
2. **"open YouTube"** → Should open youtube.com in browser
3. **"what time is it"** → Should tell you the current time
4. **"system info"** → Should show your system details
5. **"take a screenshot"** → Should save image to Desktop

If all 5 work, you're ready to go! 🎉

---

## Voice Commands

### Open Websites
- "open Google"
- "open YouTube"
- "open GitHub"
- "open Facebook"
- "open example.com" (any URL)

### Open Apps
- "open calculator"
- "open notepad"
- "open Spotify"
- "open VS Code"
- "open Chrome"

### Search
- "search for Python tutorials"
- "play lofi on YouTube"
- "look up machine learning"

### System Control
- "take a screenshot"
- "system info"
- "what time is it"
- "set volume to 60"
- "mute"

### Ask Anything Else
- "What is Python?"
- "Tell me a joke"
- "Help me write an email"

---

## Troubleshooting

**Mic not working?**
- Use Chrome or Edge browser
- Allow microphone permission when prompted
- Click the mic button to start listening

**Commands not executing?**
- Check server is running (`python server.py`)
- Look at server console for logs
- Make sure you see: `[CIPHER] Processing: open youtube`
- Should also see: `[CIPHER] Local action: open_website`

**Server won't start?**
- Install all packages: `pip install -r requirements.txt`
- Make sure `.env` file exists with your API key
- Check port 5000 is available

---

## What's Different from Before

**BEFORE (Broken):**
```
You: "open YouTube"
↓
Pattern doesn't match ❌
↓
Falls through to AI (just talks about it)
```

**NOW (Fixed):**
```
You: "open YouTube"
↓
Pattern matches ✅
↓
Actually opens youtube.com in browser!
```

---

## Need Help?

Check the full **README.md** for:
- Complete command list
- Detailed troubleshooting
- Technical details
- Supported apps & websites

---

**You're all set! Start talking to CIPHER! 🎯**