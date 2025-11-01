# CorreX - AI-Powered Text Correction & Voice Dictation for Windows

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![Tests](https://img.shields.io/badge/tests-52%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)

**CorreX** is a sophisticated, system-wide AI text correction and voice dictation tool for Windows that operates seamlessly across all applications. Leveraging Google's Gemini API, CorreX provides intelligent grammar correction, style transformation, and real-time speech-to-text capabilities—all triggered by customizable keyboard shortcuts.

Unlike traditional autocorrect tools, CorreX uses an internal buffer system that never interferes with your clipboard, supports per-candidate AI configuration (tone and temperature control), and includes multi-engine voice recognition with automatic noise reduction.

---

## ✨ Features

### 🎯 AI Text Correction
- **Customizable Trigger Keys** - TAB (default), F1-F12, Ctrl+Space, or any custom combination
- **Multiple AI Candidates** - Generate 1-5 correction variants simultaneously
- **Per-Candidate Configuration** - Set unique tone (Original, Professional, Formal, Informal, Detailed, Creative) and temperature (0.0-1.0) for each candidate
- **Live Navigation** - Browse corrections with Ctrl+Left/Right arrows
- **Internal Buffer System** - Tracks typed text without clipboard interference
- **Smart Text Replacement** - Preserves formatting and cursor position

### 🎤 Voice Dictation
- **Multi-Engine Recognition** - Google Speech API (primary), Whisper (fallback), Sphinx (offline)
- **Noise Reduction** - Automatic ambient noise calibration for improved accuracy
- **Visual Feedback** - Pulsing microphone overlay shows listening state
- **Toggle Control** - Single hotkey (Ctrl+Shift+D default) starts/stops dictation
- **Cross-App Support** - Works in any Windows application that accepts text input

### 🎨 Modern GUI
- **Comprehensive Settings Panel** - Configure all triggers, AI behavior, and system preferences
- **Candidate Personalization** - Visual controls for tone and temperature per candidate
- **Quick Start Guide** - Built-in documentation popup with scrollable content
- **Status Indicators** - Real-time service status and API configuration state
- **Asset Management** - Intelligent icon loading with fallback mechanisms

### ⚡ Performance & Reliability
- **Parallel AI Generation** - Uses ThreadPoolExecutor for concurrent candidate processing
- **Thread-Safe Architecture** - Proper locking and queue-based UI updates
- **Auto-Cleanup** - History auto-deletes after 1 hour, buffer management prevents memory leaks
- **Error Recovery** - Graceful handling of API failures, timeout protection, network issues
- **Resource Management** - Clean shutdown with proper thread/executor cleanup

### 🔒 Privacy & Security
- **Local Processing** - Keystroke buffer maintained entirely in RAM
- **Selective API Calls** - Only triggered text sent to Gemini (not everything you type)
- **No Telemetry** - Zero analytics, tracking, or phone-home behavior
- **Clipboard Preservation** - Original clipboard content always restored
- **Configurable Storage** - History database stored locally with user control

### 🚀 System Integration
- **System Tray Icon** - Persistent background service with menu access
- **Windows Startup** - Optional auto-launch on system boot
- **Notification System** - Tray notifications for status updates and errors
- **Global Hotkeys** - Works across all applications without focus stealing

---

## 🚀 Quick Start

### Installation

#### Option 1: Package Installation (Recommended)
```bash
# Clone or download the project
cd CorreX

# Install as editable package (for development)
pip install -e .

# OR install normally
pip install .

# Launch the app
correx
```

#### Option 2: Direct Run (Without Installation)
```bash
# 1. Install dependencies
pip install -r correX/requirements.txt

# 2. Run directly
python -m correX
```

#### Get Gemini API Key
Visit: https://makersuite.google.com/app/apikey

### First Run

1. **Set API Key** - Enter your Gemini API key in the GUI
2. **Adjust Settings** - Configure trigger key, number of versions, etc.
3. **Position Indicator** - Use Test button to preview loading indicator position
4. **Start Using** - Type in any app, press TAB to correct!

---

## 🎮 How to Use

### Basic Workflow

1. **Type text** in any application (Word, browser, notepad, etc.)
2. **Press TAB** - Triggers AI correction
3. **Loading indicator appears** - Shows API is processing
4. **First correction shown** - Text instantly replaced
5. **Navigate options** - Use Ctrl+Left/Right to see other versions
6. **Accept** - Press any key (or TAB again) to accept

### Text Correction Example

```
You type: "this sentence have bad grammer and needs fixing"

Press TAB → Loading indicator appears

Candidate 1 (Original, temp=0.30): "This sentence has bad grammar and needs fixing"
Candidate 2 (Professional, temp=0.55): "This statement contains grammatical errors requiring correction"
Candidate 3 (Formal, temp=0.60): "The sentence exhibits grammatical inaccuracies that necessitate amendment"
Candidate 4 (Informal, temp=0.65): "Hey, this sentence has some grammar issues that need fixing"
Candidate 5 (Detailed, temp=0.70): "This sentence contains two primary issues: incorrect verb conjugation ('have' should be 'has') and a spelling error ('grammer' should be 'grammar')"

Use Ctrl+Left/Right to browse, press any key to accept
```

### Voice Dictation Example

```
Press Ctrl+Shift+D → Mic overlay appears at bottom-center

You say: "This is a test of the voice dictation feature"

Text is automatically typed: "This is a test of the voice dictation feature"

Press Ctrl+Shift+D again → Mic overlay disappears, dictation stops
```

---

## ⚙️ Configuration

### GUI Settings

- **API Key** - Your Google Gemini API key
- **Model** - Gemini model to use (default: gemini-2.0-flash-exp)
- **Trigger Key** - Key to trigger correction (default: TAB)
- **Versions** - Number of correction options (1-3)
- **Loading Position** - X/Y coordinates for loading indicator
- **Startup** - Launch on Windows boot
- **Notifications** - Show correction notifications

### Configuration Files

- **Config:** `~/.autocorrect_ai/config.json` - Stores API key, triggers, model selection, candidate settings
- **History:** `~/.autocorrect_ai/history.db` - SQLite database tracking corrections (auto-cleanup after 1 hour)
- **Logs:** Console output for debugging

### Logging Configuration

CorreX includes a centralized logging system for better debugging and monitoring:

```python
# Enable debug logging with file output
from correX.logger import CorreXLogger
import logging

CorreXLogger.setup(
    level=logging.DEBUG,
    log_file=Path("correx_debug.log"),
    console=True
)
```

**Command-line options:**
```bash
# Run with verbose output
correx --verbose

# Run quietly (errors only)
correx --quiet

# Specify log file
correx --log-file correx.log
```

### Advanced Settings

**Candidate Personalization:**
- Each of the 5 candidates can have a unique tone and temperature
- **Temperature** (0.0-1.0): Controls AI creativity/randomness
  - 0.0-0.3: Conservative, minimal changes
  - 0.4-0.6: Balanced, moderate variation
  - 0.7-1.0: Creative, significant rewording
- **Tone Options:**
  - `original`: Fix only grammar/spelling, preserve voice
  - `professional`: Workplace-appropriate, confident tone
  - `formal`: Academic/official writing style
  - `informal`: Conversational, relaxed language
  - `detailed`: Moderate elaboration with structured formatting
  - `creative`: Expressive, varied rhythm and wording

---

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────┐
│                   main.py (Entry)                    │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
    ┌───▼────┐    ┌──────▼──────┐   ┌────▼────┐
    │  GUI   │    │   Service   │   │ Gemini  │
    │        │◄───┤ (Keyboard)  │──►│  API    │
    └────────┘    └──────┬──────┘   └─────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌─────▼─────┐   ┌──────▼──────┐   ┌────▼────┐
  │ Keystroke │   │    Text     │   │ Loading │
  │  Buffer   │   │   Buffer    │   │ Overlay │
  └───────────┘   └─────────────┘   └─────────┘
```

### Key Modules

- **`main.py`** - Application entry point, tray icon bootstrap, command-line argument parsing
- **`autocorrect_service.py`** - Core service with keyboard hooks, correction orchestration, trigger normalization
- **`gemini_corrector.py`** - Gemini API wrapper with tone presets, parallel generation, prompt engineering
- **`keystroke_buffer.py`** - Per-window keystroke tracking, buffer synchronization, cleanup management
- **`text_buffer.py`** - Cross-application text replacement using Win32 API and pywinauto
- **`loading_overlay.py`** - Thread-safe floating overlay with fade animation and position control
- **`mic_overlay.py`** - Voice dictation visual indicator with pulsing animation
- **`dictation_manager.py`** - Multi-engine speech recognition with noise reduction and error recovery
- **`config_manager.py`** - JSON persistence with schema validation and migration support
- **`history_manager.py`** - SQLite history tracking with auto-expiration and query methods
- **`tray_icon.py`** - System tray integration with dynamic menu and notification support
- **`asset_manager.py`** - Resource loading with caching, fallback logic, and ICO generation
- **`gui/app_gui.py`** - Comprehensive Tkinter GUI with responsive layout and modern components

---

## 🔧 Technical Details

### Thread Safety
- **Main Thread:** GUI operations (tkinter requirement)
- **Background Threads:** API calls (ThreadPoolExecutor with 2 workers)
- **Thread-Safe Callbacks:** Uses `root.after_idle()` for GUI updates
- **Proper Cleanup:** Executor waits for pending tasks on shutdown

### Buffer Management
- **Per-Window Tracking:** Separate buffers for each application window
- **Automatic Sync:** Updates on every keystroke
- **Buffer Clearing:** Clears after correction acceptance
- **Memory Management:** Auto-cleanup of old window buffers (max 10)

### Error Handling
- **30-Second Timeout:** Prevents infinite API waits
- **Duplicate Filtering:** Removes identical candidates
- **Text Validation:** Max 10,000 characters
- **Loading Indicator:** Always stops, even on errors
- **Graceful Degradation:** Returns original text on API failure

### AI Prompt Engineering

Each tone preset uses carefully crafted prompts with three components:
1. **Core Instruction** - Primary behavior directive (e.g., "Fix ONLY grammar" or "Rewrite professionally")
2. **Variation Hint** - Guidance for generating distinct candidates (ensures diversity across variants)
3. **First Hint** - Special instruction for the first candidate in each tone category

**Prompt Structure:**
```
You are a text [autocorrect/rewriting] engine.
[Core instruction tailored to tone]
[Variation hint to ensure diversity]
Preserve the original meaning, factual details, and intent.
Return ONLY the [corrected/rewritten] text, no explanations or quotes.

Input: [user's text]

[Corrected/Rewritten]:
```

This design ensures:
- Clean output (no markdown, no explanations)
- Tone-appropriate transformations
- Distinct candidates within each tone category
- Meaning preservation across all variants

---

## 📝 Requirements

### Core Dependencies
```txt
google-generativeai>=0.8.3   # Gemini API client
keyboard>=0.13.5              # Global keyboard hooks
pywin32>=306                  # Windows API access (clipboard, window management)
pywinauto>=0.6.8              # GUI automation for text replacement
pystray>=0.19.5               # System tray icon support
Pillow>=10.4.0                # Image processing for icons/overlays
```

### Optional Dependencies (Voice Dictation)
```txt
SpeechRecognition>=3.10.0     # Multi-engine speech recognition framework
PyAudio>=0.2.13               # Microphone input capture
noisereduce>=3.0.0            # Audio noise reduction (improves accuracy)
numpy>=1.24.0                 # Array processing for audio (required by noisereduce)
openai-whisper                # Offline high-accuracy recognition (optional, large download)
```

### System Requirements
- **Python:** 3.9+ (Tested on 3.10-3.13)
- **OS:** Windows 10/11 (64-bit recommended)
- **Memory:** 100MB+ RAM (500MB+ with Whisper)
- **Storage:** 50MB (10GB+ with Whisper models)
- **Internet:** Required for Google Speech API and Gemini API (optional for offline mode with Whisper/Sphinx)

---

## 🐛 Troubleshooting

### API Key Not Working
- Verify key at https://makersuite.google.com/app/apikey
- Check internet connection
- Ensure Gemini API is enabled in Google Cloud Console

### Loading Indicator Not Appearing
- Check position is on-screen (0-2000 range)
- Use Test button to preview
- Verify overlay isn't hidden behind fullscreen apps

### Corrections Not Showing
- Check buffer has text (type something first)
- Ensure API key is configured
- Look for errors in console output
- Verify trigger key isn't conflicting with app shortcuts

### Text Not Replacing
- Some apps block automated input (security feature)
- Try pressing Ctrl+A before TAB
- Check console for "Failed to replace" errors

### Service Won't Start
- Check if keyboard library has admin rights
- Look for port conflicts (unlikely)
- Verify all dependencies installed

---

## 📊 Performance

- **Startup Time:** <2 seconds
- **API Response:** 500-1500ms (depends on Gemini)
- **Memory Usage:** ~50-100MB
- **CPU Usage:** <1% idle, ~5% during correction
- **Disk Usage:** ~10MB (code + history DB)

---

## 🔒 Privacy & Security

- **Local Processing:** Keyboard buffer tracked locally in RAM
- **API Calls:** Only text you trigger is sent to Gemini
- **No Telemetry:** No tracking, analytics, or phone-home
- **Clipboard Safety:** Original clipboard restored after operations
- **History:** Stored locally in SQLite, auto-cleaned after 1 hour

---

## 🛠️ Development

### Project Structure
```
.
├── README.md                  # Comprehensive guide (you are here)
├── QUICK_START.md             # Fast-start instructions
└── correX/
  ├── __init__.py            # Package marker
  ├── __main__.py            # Allows `python -m correX`
  ├── main.py                # Entry point and tray bootstrap
  ├── autocorrect_service.py # Core background service
  ├── gemini_corrector.py    # Gemini API integration
  ├── keystroke_buffer.py    # Real-time keystroke buffer
  ├── text_buffer.py         # UI automation helpers
  ├── loading_overlay.py     # Floating loading indicator
  ├── config_manager.py      # Persistent configuration logic
  ├── history_manager.py     # SQLite history tracking
  ├── tray_icon.py           # System tray integration
  ├── CorreX_logo.png        # Application tray/logo asset
  ├── requirements.txt       # Python dependencies
  └── gui/
    ├── app_gui.py         # Feature-rich configuration GUI
    └── app_gui_simple.py  # Lightweight configuration GUI
```

### Running the Application
```bash
# Run full application (launches tray + GUI)
python -m correX

# Directly run the module entry point
python -m correX.main

# Run background-only mode (requires configured API key)
python -m correX.main --no-gui
```

### Testing
```bash
# Run all unit tests
pytest

# Run tests with coverage report
python run_tests.py

# Run specific test file
pytest tests/test_keystroke_buffer.py

# Run tests with verbose output
pytest -v -s

# View coverage report
start htmlcov/index.html    # Opens browser with coverage report
```

**Test Coverage:**
- `test_keystroke_buffer.py` - Buffer operations, overflow, per-window tracking
- `test_config_manager.py` - Config load/save, validation, defaults  
- `test_history_manager.py` - History save/retrieve, cleanup, search

See `tests/README.md` for detailed testing documentation.

---

## 📚 Documentation

### User Documentation
- **`README.md`** - This file (comprehensive user guide)
- **`QUICK_START.md`** - Quick reference guide with essential commands
- **`CHANGELOG.md`** - Version history and upgrade notes

### Developer Documentation
- **`DEVNOTES.md`** - Complete technical blueprint (3,266 lines)
  - Architecture diagrams and data flows
  - Component deep-dives with code examples
  - Threading model and state management
  - Error handling strategies
  - Testing and debugging techniques
- **`CONTRIBUTING.md`** - Developer contribution guidelines
  - Setup instructions
  - Code style standards
  - Testing procedures
  - Pull request process

### Feature Documentation
- **`correX/DICTATION_FEATURE.md`** - Voice dictation implementation details

### Testing
- **`test_install.py`** - Installation verification script
  ```bash
  python test_install.py
  ```

---

## 📄 License

MIT License - Free to use, modify, and distribute

---

## 🙏 Credits

- **Gemini API** - Google's generative AI
- **keyboard** - Global keyboard hooks
- **pywin32** - Windows API access
- **pywinauto** - GUI automation

---

## 📧 Support

For issues, questions, or contributions:
- Check console output for detailed error messages
- Review documentation files in project directory
- Verify all dependencies are installed correctly

---

**Status:** Production-ready ✅  
**Version:** 1.0.0  
**Last Updated:** November 1, 2025

---

## 🔗 Additional Documentation

- **`QUICK_START.md`** - Fast-start guide with essential commands and tips
- **`DEVNOTES.md`** - Comprehensive developer documentation with architecture details, data flows, and implementation notes
- **`correX/DICTATION_FEATURE.md`** - In-depth voice dictation feature documentation

For detailed technical information, see `DEVNOTES.md`
