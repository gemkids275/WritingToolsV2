# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Writing Tools is a dual-platform, system-wide AI writing assistant inspired by Apple Intelligence. It has two independent implementations:

- **`macOS/`** — Native Swift/SwiftUI port (macOS 14+), built as a menu bar app
- **`Windows_and_Linux/`** — Python/PySide6 cross-platform version

Both share the same core concept: intercept a global hotkey, capture selected text, send it to an AI provider, and replace the original text with the AI response — without corrupting the clipboard.

---

## macOS (Swift)

### Build & Run

```bash
# Open in Xcode
open macOS/WritingTools.xcodeproj

# CLI build
xcodebuild build -scheme WritingTools -project macOS/WritingTools.xcodeproj

# Run tests
xcodebuild test -scheme WritingTools -project macOS/WritingTools.xcodeproj
```

### Architecture

Entry point: `App/AppDelegate.swift` + `App/AppState.swift`

| Layer | Location | Responsibility |
|---|---|---|
| App state | `App/AppState.swift` | Global singleton managing active provider, settings, command list |
| Command execution | `App/CommandExecutionEngine.swift` | Orchestrates AI call, text replacement via Accessibility API |
| AI Providers | `Models/Providers/` | One file per provider (OpenAI, Gemini, Anthropic, Mistral, OpenRouter, Ollama, LocalModel) |
| Provider protocol | `Models/Providers/AIProvider.swift` | Shared protocol all providers conform to |
| Settings/Secrets | `App/AppSettings.swift` + `App/KeychainManager.swift` | API keys stored in Keychain; preferences in UserDefaults |
| Views | `Views/` | SwiftUI views for popup, chat, settings, command editor |
| Services | `Services/` | Clipboard, window management, update checker |

**Key design pattern:** All providers conform to `AIProvider` protocol. Adding a new provider = new file in `Models/Providers/`, conform to `AIProvider`, register in `AppState`.

**Local LLM:** `LocalModelProvider.swift` runs MLX models directly on Apple Silicon (no network). Ollama is accessed via the OpenAI-compatible endpoint through `OllamaProvider`.

**Text replacement:** Uses macOS Accessibility API (not clipboard) to read/write text — this is how it works system-wide without clipboard corruption.

---

## Windows & Linux (Python)

### Setup & Run

```bash
cd Windows_and_Linux

# Install dependencies
pip install -r requirements.txt

# Run
python main.py

# Build standalone executable
python pyinstaller-build-script.py
```

All Python commands must use the project's virtual environment.

### Architecture

Entry point: `main.py` → instantiates `WritingToolApp` from `WritingToolApp.py`

| File | Responsibility |
|---|---|
| `main.py` | QApplication setup, instantiates `WritingToolApp` |
| `WritingToolApp.py` | Core app class; hotkey listener via `pynput`, text selection/replacement |
| `aiprovider.py` | Base provider class + all provider implementations (Gemini, OpenAI-compatible, Ollama) |
| `ui/` | PySide6 UI modules (popup window, chat window, settings dialog, response output) |
| `options.json` | Default command definitions (name, system prompt, icon) |
| `locales/` | `gettext` translation files |

**Adding a provider:** Subclass the base provider in `aiprovider.py`, implement the abstract methods, register in the provider selection logic in `WritingToolApp.py`.

**Text replacement:** Uses `pyperclip` + simulated keyboard shortcuts (Ctrl+C / Ctrl+V via `pynput`) to read and replace selected text.

---

## Shared Concepts

### Commands / Buttons

Built-in commands: Proofread, Rewrite, Friendly, Professional, Concise, Summary, Key Points, Table, Custom.

- **Windows/Linux:** Defined in `options.json`; users can add custom buttons
- **macOS:** Editable via the command editor UI; stored in UserDefaults

### AI Provider Support (both platforms)

| Provider | Windows/Linux | macOS |
|---|---|---|
| Google Gemini | ✓ | ✓ |
| OpenAI & compatible (Ollama, llama.cpp, KoboldCPP, etc.) | ✓ | ✓ |
| Anthropic | — | ✓ |
| Mistral | — | ✓ |
| OpenRouter | — | ✓ |
| MLX (local, Apple Silicon) | — | ✓ |

### Localization

- **Windows/Linux:** `gettext` with `.po`/`.mo` files in `locales/`
- **macOS:** `.xcstrings` files; supports EN, DE, FR, ES
