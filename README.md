# AI Shortcuts — Writing Tools

> **A customized & extended fork of [WritingTools](https://github.com/theJayTea/WritingTools) by theJayTea.**  
> Maintained by **[Nam Trần](https://github.com/gemkids)** — a technology enthusiast.

**Instantly proofread, rewrite, summarize, and optimize your writing system-wide with AI — one hotkey, any app.**

---

## 🗂 Table of Contents

- [What is this?](#-what-is-this)
- [How to Use](#-how-to-use)
- [What's new in this fork](#-whats-new-in-this-fork-macos)
- [Features](#-features)
- [AI Providers](#-ai-providers-macos)
- [Installation](#-installation)
- [Privacy](#-privacy)
- [Original Project & Credits](#-original-project--credits)
- [About the Author](#-about-the-author)
- [License](#-license)

---

## ✨ What is this?

**AI Shortcuts** is a personal fork of **WritingTools** — an Apple Intelligence-inspired, system-wide AI writing assistant for **macOS, Windows & Linux**.

With one hotkey press, it lets you fix grammar, rewrite text, change tone, summarize content (webpages, YouTube transcripts, documents), and more — without ever leaving your current app.

This fork builds on top of the original idea with significant macOS enhancements: more AI providers, image & file attachments, a richer native UI, and quality-of-life improvements throughout.

> **🍎 macOS users:** This fork focuses on the native Swift/SwiftUI macOS version. Windows & Linux are inherited from the original project.

---

## 🚀 How to Use

### 1. Fix or improve selected text

1. Select any text in any app
2. Press your hotkey (default: `⌥ Space`)
3. Choose a command — **Proofread**, **Rewrite**, **Friendly**, **Professional**, **Concise**, etc.
4. The text is replaced instantly. Press `⌘Z` to undo.

<!-- VIDEO: basic usage demo -->

---

### 2. Custom instruction

1. Select text (or skip selection to use chat mode)
2. Press your hotkey
3. Type your instruction in the input box — e.g. _"translate to French"_, _"add code comments"_, _"make it a bullet list"_
4. Press **Enter** to send. Use **Shift+Enter** or **Alt+Enter** for a new line.

<!-- VIDEO: custom instruction demo -->

---

### 3. Attach images or files

1. Open the popup with your hotkey
2. Attach content in any of these ways:
   - **Paste** an image directly from your clipboard (`⌘V`)
   - Click the **paperclip icon** to pick a file
3. Type your instruction and press **Enter**

> Supported: PNG, JPG, HEIC, and other image formats; plain text files.  
> The AI will see both your instruction and the attached content.

<!-- VIDEO: attachment demo -->

---

### 4. Summarize a webpage or document

1. Select all text on the page (`⌘A`)
2. Press your hotkey
3. Choose **Summary**, **Key Points**, or **Table**
4. A response window opens with the result — you can continue chatting from there

<!-- VIDEO: summarize demo -->

---

### 5. Summarize a YouTube video

1. Open the video on YouTube
2. Click **...** → **Show transcript** below the video
3. Select all transcript text and copy
4. Paste into any text field, select it, and invoke Writing Tools
5. Choose **Summary** or **Key Points**

<!-- VIDEO: YouTube transcript demo -->

---

### 6. Chat without selecting text

1. Press your hotkey without selecting anything
2. Type your question or request in the popup
3. A chat window opens — keep the conversation going with follow-up questions

<!-- VIDEO: chat mode demo -->

---

### 7. Manage & reorder commands

1. Press your hotkey to open the popup
2. Click the **pencil icon** (top right) to enter edit mode
3. **Drag** any button to reorder it
4. Click the **edit** or **trash** icon on a button to modify or delete it
5. Click **Manage Commands** to add new ones or import/export

<!-- VIDEO: command management demo -->

---

## 🆕 What's New in This Fork (macOS)

On top of everything the original macOS port offers, this fork adds:

### 📎 Attachments in Prompts
- **Paste images directly** from clipboard into custom prompts
- **Attach image files** (PNG, JPG, HEIC, etc.) via file picker or drag-and-drop
- **Attach plain text files** — content is read and sent as context to the AI
- Attachments also supported in **follow-up questions** in the response window
- Unsupported file types show a clear error instead of failing silently

### ✏️ Smarter Input
- **Multi-line expandable input** — grows up to 5 lines, then scrolls
- **Enter** to send, **Shift+Enter** or **Alt+Enter** to insert a new line
- Input and attachments are **reset on each popup open**
- Thin overlay scrollbar for clean aesthetics

### 🧩 Command Management
- **Drag-to-reorder** command buttons directly in the popup (edit mode)
- **Import / export individual commands** as JSON files
- **Export full config** (all commands + custom instruction) as a backup
- **Import full config** to restore or share your setup
- Per-command custom AI provider support

### 🖥️ UI & UX
- Wider popup (380px) for more breathing room
- **Drag popup across multiple screens** — not locked to the originating display
- Horizontal attachment strip with **drag-to-scroll** gesture
- Response window follow-up input also supports attachments and multi-line

### 🐛 Bug Fixes
- **Fixed:** On newer macOS versions, the onboarding flow could not locate the correct path to **System Settings → Privacy & Security**, leaving users unable to grant Accessibility or Screen Recording permissions. The deep link now opens the correct pane directly.

---

## 🛠 Common Issues

### Commands not showing after selecting text

When you select text and open the popup, but only see the text input box with no command buttons — this is almost always an **Accessibility permission issue**.

AI Shortcuts needs Accessibility access to read your selected text. Without it, the app cannot detect what you've highlighted and won't display the command list.

**How to fix:**

1. Open **System Settings → Privacy & Security → Accessibility**
2. Find **AI Shortcuts** in the list — if the toggle is OFF, turn it ON
3. If AI Shortcuts is not in the list, or the issue persists after enabling:
   - Select **AI Shortcuts** and click the **`−`** button to remove it
   - Relaunch the app — it will prompt you to grant Accessibility permission again
   - Click **Open System Settings**, then enable the toggle

> **Note:** On macOS, the app must be added under its current name. If you previously had an older version listed (e.g. "WritingTools"), remove that entry and add the current version instead.

---

## 🔮 What's Coming

- **Windows & Linux parity** — Gradually bring the macOS-exclusive features (attachments, richer command management, more providers) to the Windows & Linux version
- **Multi-language & custom language support** — Let users set a preferred response language, and support custom language configurations beyond the built-in UI locales
- **Ongoing bug fixes** — Continuously improving stability and compatibility across macOS versions

---

## 🌟 Features

### For all platforms (inherited from original):
- **Proofread** — Smart grammar & spelling correction
- **Rewrite** — Improve phrasing while keeping your meaning
- **Friendly / Professional** — Adjust tone instantly
- **Concise** — Trim the fat from your writing
- **Summarize** — Clear summaries of any text, webpage, or video transcript
- **Key Points** — Extract the most important ideas
- **Table** — Convert text into a formatted table (paste directly into Word/Notion)
- **Custom Instructions** — Anything you can describe: _"translate to French"_, _"add code comments"_, _"make it title case"_
- **Chat mode** — Press the hotkey without selecting text to chat with your AI
- **Zero clipboard corruption** — Uses the Accessibility API, not the clipboard
- **Privacy-first** — No telemetry, no tracking, API keys stored locally in Keychain

### macOS exclusive:
- Local **MLX models** on Apple Silicon — fully offline, no internet required
- **Ollama** support via OpenAI-compatible endpoint
- **RTF-preserving Proofread** — keeps bold, italics, lists, and links intact
- **Command shortcuts** — assign keyboard shortcuts to any command
- **Custom command editor** — create and edit your own AI buttons
- Localized UI in **English, German, French, Spanish**
- Multiple themes including dark mode

---

## 🧠 AI Providers (macOS)

| Provider | Type | Notes |
|---|---|---|
| Google Gemini | Cloud | Free tier available; Gemini 2.0 Flash recommended |
| OpenAI | Cloud | GPT-4o and compatible models |
| Anthropic | Cloud | Claude 3.5 Sonnet, Claude 3 Opus, etc. |
| Mistral AI | Cloud | Mistral Large, Small, and more |
| OpenRouter | Cloud | Access 100+ models via one API key |
| Ollama | Local | Any model via OpenAI-compatible endpoint |
| MLX (Apple Silicon) | Local | On-device inference, zero latency, zero internet |

> **Mix & match:** Use cloud models for power tasks, local models for private or offline work.

---

## ✅ Installation

### 🍎 macOS

**Requirements:** macOS 14 (Sonoma) or later.

1. Go to the [Releases](https://github.com/gemkids/WritingTools/releases) page and download the latest macOS `.dmg` file.
2. Open the `.dmg`, drag `writing-tools.app` into your **Applications** folder.
3. Launch the app — it will guide you through permissions and initial setup.

**Permissions required (prompted on first launch):**
- **Accessibility** — to read and replace selected text system-wide
- **Screen Recording** — for apps that restrict text access via Accessibility API

Manage these under **System Settings → Privacy & Security**.

> **Hotkey conflict?** If your shortcut clashes with Spotlight or Input Source switching, set a custom hotkey in Settings and adjust **System Settings → Keyboard → Keyboard Shortcuts**.

---

### 🪟 Windows & 🐧 Linux

Refer to the [original WritingTools project](https://github.com/theJayTea/WritingTools) for Windows & Linux installation. The `Windows_and_Linux/` folder in this repo contains an updated version with additional AI providers.

**Quick start:**
```bash
cd Windows_and_Linux
pip install -r requirements.txt
python main.py
```

---

## 🔒 Privacy

- **No telemetry, no logging, no ads.** The app collects nothing.
- API keys are stored in the **macOS Keychain** (not plain UserDefaults).
- Text is only sent to your chosen AI provider when you explicitly trigger an action.
- Use **local MLX or Ollama** to keep everything fully on-device.
- Refer to your AI provider's privacy policy when using cloud models.

---

## 📖 Original Project & Credits

This fork is built on top of **[WritingTools](https://github.com/theJayTea/WritingTools)**, created by **[Jesai](https://github.com/theJayTea)** — a high school student from Bangalore who built one of the most innovative open-source AI utilities of 2024.

WritingTools was featured in 🔥 [**28+ global publications**](https://github.com/theJayTea/WritingTools/blob/main/Media%20Coverage.md) including [Beebom](https://beebom.com/high-schooler-app-brings-apple-inteligence-writing-tools-windows/), [XDA Developers](https://www.xda-developers.com/windows-pc-can-now-deliver-instant-free-writing-help-across-all-apps/), [How-To Geek](https://www.howtogeek.com/if-you-like-apple-intelligences-writing-tool-try-this-open-source-app-as-its-windows-counterpart/), and [Windows Central](https://www.windowscentral.com/software-apps/can-apple-catch-up-apple-intelligence-just-shipped-yet-free-apple-writing-tools-on-github-for-windows-and-linux-make-a-better-alternative). It was among the [**top 10 most trending AI programs on GitHub**](https://devface.ai/ranking/top_ai_developers/2024-10) in October 2024.

### Original macOS Port
The native Swift/SwiftUI macOS version was built from scratch by **[Arya Mirsepasi](https://github.com/Aryamirsepasi)** — an incredible engineering effort that this fork builds upon.

### Other notable contributors to the original project
- **[momokrono](https://github.com/momokrono)** — Linux support, pynput, Ollama, localization
- **[Cameron Redmore](https://github.com/CameronRedmore)** — OpenAI-compatible API, streamed responses, chat mode
- **[Joaov41](https://github.com/Joaov41)** — Image processing in Gemini on macOS
- **[gdmka](https://github.com/gdmka)** — Per-command custom provider, response window text size memory
- **[drankush](https://github.com/drankush)** — Custom Base URL fix for OpenAI provider

Full contributor list: [theJayTea/WritingTools](https://github.com/theJayTea/WritingTools#-contributors)

---

## 👨‍💻 About the Author

**Nam Trần** — a web developer and technology enthusiast based in Vietnam.

I'm primarily a web developer, so macOS and Swift are not my home turf. I built this in my spare time because I wanted a more powerful AI writing assistant that fits the way I work — and decided to share it openly in case it helps others too.

This fork is completely free — no subscription, no maintenance fee, no catch. Every feature here was built on personal time and shared openly in the spirit of the original project.

**Found a bug or have an idea?**  
Feel free to [open an issue on GitHub](https://github.com/gemkids275/WritingToolsV2/issues). I check issues regularly and will fix anything that's important or genuinely useful. If you have a feature idea, share it — I'll consider building it if it's feasible.

If any of this makes your workflow a little better, leaving a ⭐ on GitHub is the best way to say thanks. It costs nothing and means a lot.

- GitHub: [github.com/gemkids275](https://github.com/gemkids275)

**⚠️ Copyright / Legal concerns**  
If you have any concerns regarding copyright, intellectual property, or any other serious matter related to this project — please email me at **gemkids275@gmail.com**. I will review the issue promptly and take it down immediately if it affects the original authors or violates any rights.

---

## 📄 License

Distributed under the **GNU General Public License v3.0** — the same license as the original WritingTools project.

See [LICENSE](LICENSE) for details.
