# ╔══════════════════════════════════════════╗
# ║       CIPHER — Desktop AI Makefile       ║
# ╚══════════════════════════════════════════╝

.PHONY: all setup run open clean help

PYTHON   := python3
PIP      := pip3
ENV_FILE := .env
BROWSER_OPEN := $(shell \
	if command -v xdg-open >/dev/null 2>&1; then echo xdg-open; \
	elif command -v open >/dev/null 2>&1; then echo open; \
	else echo start; fi)

# ── Default target ───────────────────────────────────────────────────────────
all: help

# ── Setup: create .env and install deps ─────────────────────────────────────
setup:
	@echo "[ CIPHER ] Setting up..."
	@if [ ! -f $(ENV_FILE) ]; then \
		cp .env.example $(ENV_FILE); \
		echo "  Created .env — add your GEMINI_API_KEY!"; \
	else \
		echo "  .env already exists, skipping."; \
	fi
	@echo "[ CIPHER ] Installing Python dependencies..."
	$(PIP) install -r requirements.txt
	@echo "[ CIPHER ] Setup complete."

# ── Run backend only ─────────────────────────────────────────────────────────
run:
	@echo "[ CIPHER ] Starting server on http://localhost:5000"
	$(PYTHON) server.py

# ── Open frontend in browser ─────────────────────────────────────────────────
open:
	@echo "[ CIPHER ] Opening frontend..."
	$(BROWSER_OPEN) http://localhost:5000/app

# ── Start server + open UI ────────────────────────────────────────────────────
start:
	@echo "[ CIPHER ] Launching CIPHER..."
	@$(PYTHON) server.py &
	@sleep 1.5
	@$(BROWSER_OPEN) http://localhost:5000/app
	@echo "[ CIPHER ] Running at http://localhost:5000/app — Press Ctrl+C to stop."

# ── Clean Python cache ────────────────────────────────────────────────────────
clean:
	@echo "[ CIPHER ] Cleaning cache..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -name "*.pyc" -delete 2>/dev/null; true
	@echo "  Done."

# ── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  CIPHER — Desktop AI Assistant"
	@echo "  ──────────────────────────────────────────"
	@echo "  make setup    — Install deps & create .env"
	@echo "  make run      — Start Flask server"
	@echo "  make open     — Open cipher.html in browser"
	@echo "  make start    — Server + open UI together"
	@echo "  make clean    — Remove Python cache"
	@echo "  make help     — Show this message"
	@echo ""