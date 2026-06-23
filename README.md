# OMI — Personal AI Assistant

> An always-on AI assistant that runs silently in the background, watching your screen, listening via microphone, and helping you stay focused — powered by Google Gemini.

**Supports Windows & Linux.**

---

## Features

| Feature | Description |
|---|---|
| 🖥️ **Screen Vision** | Analyses your screen every few seconds and gives you proactive suggestions |
| 📷 **Camera** | Periodic webcam capture to monitor posture, focus, and habits |
| 🎙️ **Microphone** | Real-time transcription of speech, stored in a local database |
| 🧠 **Long-term Memory** | Persistent user profile that survives restarts |
| 🤖 **OS Agent** | Can list/read/write files, manage processes, control clipboard, run commands |
| 💬 **Contextual Chat** | Answers your questions with full awareness of your screen and session history |
| ⚡ **Hardware Detection** | Automatically detects if camera/microphone are available and adapts accordingly |
| 🌙 **Auto Theme** | Follows system light/dark mode in real time (Windows) |

---

## Installation

### 🪟 Windows — Installer (.exe)

Download and run **`OMI_Setup.exe`** from the [Releases](https://github.com/Tommy579/omi/releases) page.

The installer will:
1. Ask for your Gemini API key
2. Install all Python dependencies into a virtual environment
3. Configure OMI to start automatically on login
4. Optionally launch OMI immediately

> You can get a **free** Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

### 🐧 Linux — Automated Script

A single script handles everything automatically:

```bash
# Clone the repository
git clone https://github.com/Tommy579/omi
cd omi

# Run the installer (pass your API key directly or let the script ask)
bash install_linux.sh AIzaYOUR_API_KEY
```

The script will automatically:
- Install missing system packages (`libportaudio2`, `python3-venv`, etc.) via `apt`
- Create a Python virtual environment (`.venv`)
- Install all Python dependencies
- Optionally install Whisper for microphone transcription
- Set up autostart via `~/.config/autostart/OmiAssistant.desktop` (GNOME/KDE)
- Optionally launch OMI immediately in the background

---

### 🛠️ Manual Installation (both platforms)

```bash
# 1. Clone the repository
git clone https://github.com/Tommy579/omi
cd omi

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# OR
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
echo "GEMINI_API_KEY=AIzaYOUR_KEY_HERE" > .env

# 5. Launch
python main.py
```

---

## Usage

| Action | Result |
|---|---|
| Click the OMI tray icon | Open the panel |
| `↺` in the panel | Force a screen analysis now |
| `⏸` in the panel | Pause automatic analysis |
| `🎙️` in the panel | Show microphone transcript history |
| `—` in the panel | Minimize to watermark (last message visible bottom-right) |
| `×` in the panel | Close the panel |
| Chat box at the bottom | Send a message to OMI with full screen context |

---

## Configuration (`config.py`)

| Parameter | Description | Default |
|---|---|---|
| `GEMINI_MODEL` | Gemini model to use | `gemini-3.1-flash-lite` |
| `ENABLE_CAMERA` | Enable webcam capture | `True` |
| `CAMERA_CAPTURE_INTERVAL` | Seconds between camera captures | `30` |
| `ENABLE_MICROPHONE` | Enable microphone transcription (requires Whisper) | `True` |
| `AUDIO_SEGMENT_DURATION` | Duration of each audio segment (seconds) | `10` |
| `SCREEN_CAPTURE_INTERVAL` | Seconds between screen analyses | `10` |
| `ALLOW_AUTONOMOUS_UI_INTERACTION` | Allow OMI to click/type without being asked | `False` |
| `MAX_MEMORY_ITEMS` | Max items in short-term memory | `20` |
| `SYSTEM_PROMPT` | AI personality and behaviour | see file |

> All settings can also be overridden via environment variables in `.env`.

---

## Hardware Detection

OMI automatically detects whether a **camera** and **microphone** are physically available on startup:

- If **no camera** is found → camera capture is skipped and the Gemini API is notified not to make posture/appearance comments.
- If **no microphone** is found → audio transcription thread is not started and Gemini is informed.

This means OMI works correctly on headless servers, VMs, or any machine without these peripherals.

---

## Project Structure

```
omi/
├── main.py                # Entry point
├── config.py              # ⚙️ Configuration
├── install.py             # Interactive CLI installer
├── install_linux.sh       # 🐧 Automated Linux installer
├── build_release.py       # 🏗️ Builds Windows .exe release
├── requirements.txt       # Python dependencies
├── core/
│   ├── assistant.py       # Brain: vision, mic, Gemini calls, hardware detection
│   ├── tools.py           # OS tools accessible by Gemini
│   ├── database.py        # SQLite for audio history
│   └── profile.py         # Long-term user memory
├── ui/
│   └── tray.py            # System tray icon + popup panel
└── tests/
    ├── test_tools.py       # Unit tests for OS tools
    └── test_assistant.py   # Unit tests for hardware detection
```

---

## Tools Available to Gemini

Gemini can call these tools autonomously based on context:

| Category | Tools |
|---|---|
| **Files** | `list_directory`, `read_file`, `write_file`, `search_files` |
| **OS** | `execute_command`, `get_active_window_info`, `get_ui_tree`, `get_system_stats` |
| **Processes** | `list_processes`, `get_process_details`, `kill_process` |
| **UI Interaction** | `mouse_click`, `type_text`, `press_key`, `background_interact` *(restricted by default)* |
| **Network** | `get_network_connections` |
| **System** | `get_clipboard`, `set_clipboard`, `get_machine_info`, `get_windows_event_logs` |
| **Apps** | `control_itunes`, `open_url`, `search_web`, `send_notification` |
| **Memory** | `get_user_profile`, `update_user_profile`, `query_transcript_history` |

---

## Key Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini API (new SDK) |
| `mss` | Screen capture |
| `Pillow` | Image processing |
| `opencv-python` | Webcam capture |
| `pystray` | System tray icon |
| `sounddevice` + `numpy` | Audio capture |
| `openai-whisper` | Local speech transcription *(optional)* |
| `psutil` | Process monitoring |
| `pywinauto` | Window interaction *(Windows only)* |
| `pyodbc` | Windows Search index *(Windows only)* |
| `pyperclip` | Clipboard access |
| `pyautogui` | Mouse/keyboard control |
| `pywin32` | Windows event logs *(Windows only)* |
| `pyaudiowpatch` | WASAPI loopback audio *(Windows only)* |
| `python-dotenv` | `.env` file loading |

---

## Building the Windows Installer

To rebuild the `.exe` files from source:

```bash
python build_release.py
```

This produces two files in `dist/`:
- **`OmiAssistant.exe`** — the main application
- **`OMI_Setup.exe`** — the installer to distribute

Requires PyInstaller (`pip install pyinstaller`).

---

## Running Tests

```bash
python -m unittest discover -s tests
```

---

## Security

- **Never commit your API key to Git** — use `.env` (already in `.gitignore`)
- `execute_command` and `write_file` give Gemini full system access — use with awareness
- `ALLOW_AUTONOMOUS_UI_INTERACTION` is `False` by default — Gemini won't click or type unless you explicitly ask
