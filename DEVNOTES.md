# CorreX Developer Notes

**Version:** 1.0.0  
**Last Updated:** November 1, 2025  
**Purpose:** Complete technical documentation for understanding, maintaining, and rebuilding CorreX from scratch

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Core Components Deep Dive](#core-components-deep-dive)
   - main.py - Application Entry Point
   - autocorrect_service.py - Core Background Service
   - gemini_corrector.py - AI Integration Layer
   - keystroke_buffer.py - Per-Window Text Tracking
   - text_buffer.py - Cross-App Text Replacement
   - dictation_manager.py - Voice Recognition System
   - config_manager.py - Configuration Persistence
   - history_manager.py - SQLite History Tracking
5. [GUI Implementation](#gui-implementation)
6. [System Integration](#system-integration)
7. [Threading Model](#threading-model)
8. [Data Flow & State Management](#data-flow--state-management)
9. [Error Handling & Recovery](#error-handling--recovery)
10. [Testing & Debugging](#testing--debugging)
11. [Build & Deployment](#build--deployment)
12. [Known Issues & Limitations](#known-issues--limitations)
13. [Logging System](#logging-system)
14. [Testing Infrastructure](#testing-infrastructure)
15. [Configuration Validation](#configuration-validation)
16. [Modern Python Packaging](#modern-python-packaging)
17. [Open Source Infrastructure](#open-source-infrastructure)
18. [Conclusion](#conclusion)

---

## Project Overview

### What is CorreX?

CorreX is a **system-wide AI-powered text correction and voice dictation tool** for Windows. It operates as a background service that monitors keyboard input, detects correction triggers, sends text to Google's Gemini API for processing, and replaces the original text with corrections—all without interfering with the user's clipboard or workflow.

### Key Innovations

1. **Internal Buffer System**: Tracks typed text per-window without clipboard manipulation
2. **Per-Candidate AI Configuration**: Each correction variant can have unique tone and temperature
3. **Multi-Engine Voice Recognition**: Fallback chain (Google → Whisper → Sphinx) ensures reliability
4. **Thread-Safe Architecture**: Proper synchronization between keyboard hooks, GUI, and API calls
5. **Zero-Interference Design**: Works across all Windows applications without focus stealing

### Design Philosophy

- **Non-Intrusive**: Service runs in background, minimal UI presence (system tray only)
- **User Control**: All behavior configurable (triggers, AI parameters, history retention)
- **Privacy First**: Only triggered text sent to API, local processing when possible
- **Fail-Safe**: Graceful degradation on errors (returns original text, never loses data)
- **Cross-App Compatible**: Uses Win32 APIs for universal Windows application support

---

## Technology Stack

### Programming Language
- **Python 3.9+** (Tested on 3.10, 3.11, 3.12, 3.13)
  - Chosen for: Rapid development, rich library ecosystem, excellent AI/ML support
  - Trade-offs: Slower than compiled languages, but acceptable for I/O-bound workload

### Core Libraries

#### AI & API
- **google-generativeai** (0.8.3+)
  - Official Google Gemini API client
  - Handles authentication, request formatting, streaming responses
  - Used in: `gemini_corrector.py`

#### System Integration
- **keyboard** (0.13.5+)
  - Global keyboard event hooks (works across all applications)
  - Captures key presses without requiring focus
  - Used in: `autocorrect_service.py`
  - **Important**: Requires elevated privileges on some systems

- **pywin32** (306+)
  - Windows API bindings (Win32 API access)
  - Used for: Clipboard manipulation, window handle detection, process information
  - Modules used: `win32clipboard`, `win32con`, `win32gui`, `win32process`
  - Used in: `text_buffer.py`, `keystroke_buffer.py`

- **pywinauto** (0.6.8+)
  - GUI automation library for Windows applications
  - Used for: Sending keystrokes, simulating user input
  - Used in: `text_buffer.py` (fallback text replacement method)

#### Voice Recognition
- **SpeechRecognition** (3.10.0+)
  - Unified interface for multiple speech engines
  - Supports: Google Speech API, Whisper, Sphinx, others
  - Used in: `dictation_manager.py`

- **PyAudio** (0.2.13+)
  - Low-level audio capture from microphone
  - Cross-platform audio I/O library
  - Used in: `dictation_manager.py` (via SpeechRecognition)
  - **Note**: Windows installation may require precompiled wheels

- **noisereduce** (3.0.0+) + **numpy** (1.24.0+)
  - Optional audio noise reduction
  - Improves speech recognition accuracy in noisy environments
  - Used in: `dictation_manager.py`

#### GUI & UI
- **tkinter** (stdlib)
  - Python's standard GUI framework (Tk/Tcl wrapper)
  - Used for: Main configuration GUI, popup windows, overlays
  - **Important**: Single-threaded, all UI updates must occur on main thread
  - Used in: `gui/app_gui.py`, `loading_overlay.py`, `mic_overlay.py`

- **pystray** (0.19.5+)
  - System tray icon library
  - Cross-platform, but CorreX uses Windows-specific features
  - Used in: `tray_icon.py`

- **Pillow (PIL)** (10.4.0+)
  - Image processing library
  - Used for: Icon resizing, format conversion, overlay rendering
  - Used in: `asset_manager.py`, `tray_icon.py`, `loading_overlay.py`

#### Data Persistence
- **sqlite3** (stdlib)
  - Lightweight embedded database
  - Used for: Correction history tracking
  - Database file: `~/.autocorrect_ai/history.db`
  - Used in: `history_manager.py`

- **json** (stdlib)
  - Configuration file format
  - Config file: `~/.autocorrect_ai/config.json`
  - Used in: `config_manager.py`

### Development Tools
- **concurrent.futures** (stdlib): Thread pool management for parallel API calls
- **threading** (stdlib): Thread synchronization, locks, events
- **queue** (stdlib): Thread-safe message passing between UI and background threads
- **pathlib** (stdlib): Modern path manipulation
- **dataclasses** (stdlib, Python 3.7+): Structured data containers

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Layer                               │
│  (Types in any Windows app, presses trigger key)                │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Keyboard Hook Layer                           │
│  keyboard.on_press() → AutoCorrectService._on_key_press()       │
│  Detects: Correction trigger, dictation toggle, navigation      │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
┌─────────────▼────────────┐  ┌────────────▼──────────────┐
│   Text Correction Path   │  │   Voice Dictation Path    │
│                          │  │                           │
│ 1. KeystrokeBuffer       │  │ 1. DictationManager       │
│    → Get typed text      │  │    → Listen via mic       │
│                          │  │                           │
│ 2. GeminiCorrector       │  │ 2. SpeechRecognition      │
│    → Send to API         │  │    → Transcribe speech    │
│    → Generate candidates │  │                           │
│                          │  │ 3. keyboard.write()       │
│ 3. TextBuffer            │  │    → Type recognized text │
│    → Replace original    │  │                           │
│                          │  │ 4. KeystrokeBuffer        │
│ 4. User navigation       │  │    → Add to buffer        │
│    → Ctrl+Left/Right     │  │                           │
└──────────────────────────┘  └───────────────────────────┘
              │                             │
              └──────────────┬──────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Persistence Layer                             │
│  ConfigManager → config.json                                     │
│  HistoryManager → history.db                                     │
└──────────────────────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────┐
│                      UI Layer                                    │
│  GUI (app_gui.py) → Configuration, testing, status display      │
│  TrayIcon → Menu, notifications, service control                │
│  Overlays → Loading spinner, mic indicator                      │
└──────────────────────────────────────────────────────────────────┘
```

### Component Interaction Matrix

| Component | Depends On | Used By | Communication Method |
|-----------|------------|---------|---------------------|
| main.py | All | None (entry point) | Function calls |
| AutoCorrectService | keyboard, GeminiCorrector, KeystrokeBuffer, TextBuffer, DictationManager | main.py, GUI | Callbacks, threading |
| GeminiCorrector | google-generativeai | AutoCorrectService | Synchronous API calls |
| KeystrokeBuffer | pywin32 | AutoCorrectService | Direct method calls |
| TextBuffer | pywin32, pywinauto, keyboard | AutoCorrectService | Direct method calls |
| DictationManager | SpeechRecognition, PyAudio | AutoCorrectService | Callbacks, threading |
| ConfigManager | json (stdlib) | main.py, AutoCorrectService, GUI | Direct method calls |
| HistoryManager | sqlite3 (stdlib) | AutoCorrectService | Direct method calls |
| GUI | tkinter, all services | main.py | Queue-based commands |
| TrayIcon | pystray | main.py | Callbacks |
| LoadingOverlay | tkinter | AutoCorrectService | Thread-safe methods |
| MicOverlay | tkinter | DictationManager | Thread-safe methods |
| AssetManager | PIL, pathlib | GUI, TrayIcon, Overlays | Direct method calls |

---


## Core Components Deep Dive

### 1. main.py - Application Entry Point

**Location**: `correX/main.py`  
**Purpose**: Bootstrap application, initialize services, manage lifecycle  
**Lines of Code**: ~200

**Key Responsibilities**:
- Parse command-line arguments (`--no-gui`, `--verbose`)
- Load configuration from `~/.autocorrect_ai/config.json`
- Initialize GeminiCorrector with API key (or dummy key for GUI config)
- Create AutoCorrectService with all dependencies
- Launch system tray icon in daemon thread
- Optionally launch GUI on main thread
- Handle graceful shutdown (service stop, config save, thread cleanup)

**Entry Point Flow**:
```python
def main():
    # 1. Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-gui', action='store_true')
    args = parser.parse_args()
    
    # 2. Load config
    config = ConfigManager()
    api_key = config.get("api_key") or "dummy-key-replace-in-gui"
    
    # 3. Initialize corrector (allow_dummy=True for GUI launch)
    corrector = GeminiCorrector(api_key=api_key, allow_dummy=True)
    
    # 4. Load candidate settings
    candidate_settings = config.get("candidate_settings")
    if not candidate_settings:
        candidate_settings = GeminiCorrector.default_candidate_settings()
    
    # 5. Create service
    service = AutoCorrectService(
        corrector=corrector,
        trigger_key=config.get("trigger_key", "tab"),
        dictation_trigger_key=config.get("dictation_trigger_key", "ctrl+shift+d"),
        candidate_settings=candidate_settings,
        version_count=config.get("version_count", 3),
    )
    
    # 6. Start service
    service.start()
    
    # 7. Launch tray in daemon thread
    tray = TrayIcon(on_show_gui=lambda: launch_gui(...))
    threading.Thread(target=tray.start, daemon=True).start()
    
    # 8. Launch GUI if not suppressed
    if not args.no_gui:
        launch_app(service=service, corrector=corrector, config=config)
```

**Shutdown Sequence**:
1. User triggers exit (tray menu or GUI close)
2. `on_exit()` callback invoked
3. Service stops: `service.stop()` removes keyboard hooks
4. History closes: `history_manager.close()` commits DB
5. Config saves: `config.save()` writes JSON
6. Threads join with timeout
7. Process exits

**Critical Design Decisions**:
- Tray thread is daemon (terminates with main process automatically)
- GUI must run on main thread (tkinter single-threaded requirement)
- Service starts before GUI (ensures core functionality even if GUI crashes)
- `allow_dummy=True` permits GUI launch for API key configuration

---

### 2. autocorrect_service.py - Core Background Service

**Location**: `correX/autocorrect_service.py`  
**Purpose**: Central orchestrator for keyboard monitoring, text correction, dictation  
**Lines of Code**: ~600

**Key Responsibilities**:
- Register/unregister global keyboard hooks
- Maintain per-window keystroke buffers
- Detect correction/dictation/navigation triggers
- Coordinate API calls with GeminiCorrector
- Manage correction candidate navigation (Ctrl+Left/Right)
- Control loading/mic overlays
- Track correction history in SQLite

**Critical State Variables**:
```python
self._running: bool                     # Service active flag
self._processing: bool                  # Currently processing correction (prevents double-trigger)
self._current_candidates: List[str]     # Last generated corrections (for navigation)
self._candidate_index: int              # Currently displayed candidate (0-based)
self._lock: threading.RLock             # Protects all shared state
self._trigger_key: str                  # Normalized trigger (e.g., "tab", "ctrl+space")
self._dictation_trigger_key: str        # Dictation toggle trigger
self._candidate_settings: List[Dict]    # Per-candidate tone/temperature config
self._version_count: int                # Number of candidates to generate (1-5)
```

**Key Methods**:

**1. start() - Register Keyboard Hooks**
```python
def start(self):
    if self._running:
        return
    self._running = True
    keyboard.on_press(self._on_key_press)
    keyboard.on_release(self._on_key_release)
    print("[INFO] AutoCorrectService started")
```

**2. _on_key_press(event) - Main Keyboard Event Handler**
```python
def _on_key_press(self, event: keyboard.KeyboardEvent):
    if not self._running:
        return
    
    # Normalize event to trigger string
    trigger = self._format_event_to_trigger(event)
    
    # Check for correction trigger
    if trigger == self._trigger_key:
        self._handle_correction_trigger()
        return
    
    # Check for dictation toggle
    if trigger == self._dictation_trigger_key:
        self.toggle_dictation()
        return
    
    # Check for navigation (Ctrl+Left/Right)
    if self._current_candidates:
        if event.name == 'left' and self._is_ctrl_pressed():
            self._navigate_candidate(-1)  # Previous
            return
        if event.name == 'right' and self._is_ctrl_pressed():
            self._navigate_candidate(1)   # Next
            return
    
    # Normal key: add to buffer
    self._keystroke_buffer.add_keystroke(event.name)
    
    # Clear candidates on any other key press
    if self._current_candidates:
        self._current_candidates = []
```

**3. _handle_correction_trigger() - Core Correction Logic**
```python
def _handle_correction_trigger(self):
    # Prevent double-trigger
    with self._lock:
        if self._processing:
            return
        self._processing = True
    
    try:
        # Get text from buffer
        text = self._keystroke_buffer.get_text()
        if not text or len(text) < 2:
            return
        
        # Show loading overlay
        if self._loading_overlay:
            self._loading_overlay.show()
        
        # Call API (blocks on keyboard hook thread - acceptable)
        candidates = self._corrector.cleanup_paragraph(
            text,
            num_versions=self._version_count,
            candidate_settings=self._candidate_settings
        )
        
        # Hide overlay
        if self._loading_overlay:
            self._loading_overlay.hide()
        
        # Replace text with first candidate
        if candidates and candidates[0]:
            success = self._text_buffer.replace_text(text, candidates[0])
            if success:
                self._current_candidates = candidates
                self._candidate_index = 0
                self._keystroke_buffer.set_text(candidates[0])
                
                # Save to history
                if self._history_manager:
                    self._history_manager.add_correction(text, candidates[0])
    
    finally:
        with self._lock:
            self._processing = False
```

**4. _navigate_candidate(direction) - Cycle Through Corrections**
```python
def _navigate_candidate(self, direction: int):
    if not self._current_candidates:
        return
    
    # Calculate new index (wrap around)
    new_index = (self._candidate_index + direction) % len(self._current_candidates)
    
    # Get current and new text
    old_text = self._current_candidates[self._candidate_index]
    new_text = self._current_candidates[new_index]
    
    # Replace text
    success = self._text_buffer.replace_text(old_text, new_text)
    if success:
        self._candidate_index = new_index
        self._keystroke_buffer.set_text(new_text)
```

**Thread Safety Design**:
- Keyboard hooks run on separate thread (managed by `keyboard` library)
- All state access protected by `self._lock` (RLock allows re-entrance)
- GUI updates queued via `_UI_COMMANDS` queue (never direct tkinter calls)
- Loading overlay uses `root.after()` for thread-safe scheduling

**Trigger Normalization Algorithm**:
```python
@staticmethod
def normalize_trigger_key(key: Optional[str]) -> Optional[str]:
    \"\"\"Convert 'Ctrl-A', 'ctrl+a', 'CTRL+A'  'ctrl+a'\"\"\"
    if not key:
        return None
    
    # Special cases
    if key.lower() == "tab":
        return "tab"
    
    # Parse components
    parts = key.lower().replace("-", "+").split("+")
    modifiers = []
    main_key = None
    
    for part in parts:
        part = part.strip()
        if part in ("ctrl", "control"):
            modifiers.append("ctrl")
        elif part == "shift":
            modifiers.append("shift")
        elif part in ("alt", "meta"):
            modifiers.append("alt")
        else:
            main_key = part
    
    # Canonical order: ctrl, shift, alt, then main key
    ordered = []
    for mod in ["ctrl", "shift", "alt"]:
        if mod in modifiers:
            ordered.append(mod)
    if main_key:
        ordered.append(main_key)
    
    return "+".join(ordered) if ordered else None
```

**Event-to-Trigger Conversion**:
Uses bitmask detection for modifier keys to avoid false positives (e.g., NumLock):
```python
CTRL_MASK = 0x0004
SHIFT_MASK = 0x0001
ALT_MASK = 0x0008   # Only 0x0008, not 0x20000 (NumLock)

def _format_event_to_trigger(self, event):
    state = getattr(event, 'state', 0) or 0
    
    modifiers = []
    if state & CTRL_MASK:
        modifiers.append('ctrl')
    if state & SHIFT_MASK:
        modifiers.append('shift')
    if state & ALT_MASK:
        modifiers.append('alt')
    
    ordered_mods = ['ctrl', 'shift', 'alt']
    result = [m for m in ordered_mods if m in modifiers]
    result.append(event.name.lower())
    
    return '+'.join(result)
```

---

### 3. gemini_corrector.py - AI Integration Layer

**Location**: `correX/gemini_corrector.py`  
**Purpose**: Wrapper for Google Gemini API with tone presets and parallel generation  
**Lines of Code**: ~350

**Key Responsibilities**:
- Initialize Gemini API client with authentication
- Define tone presets (Original, Professional, Formal, Informal, Detailed, Creative)
- Build tone-aware prompts for each candidate
- Generate multiple corrections in parallel using ThreadPoolExecutor
- Normalize and validate candidate settings
- Handle API errors and timeout

**Tone Presets Dictionary**:
```python
TONE_PRESETS = {
    "original": {
        "label": "Original (Minimal change)",
        "rewrite": False,
        "instruction": "Fix ONLY grammar, spelling, and punctuation errors...",
    },
    "professional": {
        "label": "Professional",
        "rewrite": True,
        "instruction": "Rewrite the passage so it sounds professional...",
    },
    "formal": {...},
    "informal": {...},
    "detailed": {
        "label": "Detailed",
        "rewrite": True,
        "instruction": "Refine and enhance content with moderate elaboration...",
    },
    "creative": {...},
}
```

**Core Method - cleanup_paragraph()**:
```python
def cleanup_paragraph(
    self,
    text: str,
    num_versions: int = 1,
    candidate_settings: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    \"\"\"Generate multiple AI corrections with different tones/temperatures.\"\"\"
    
    # Validate and normalize settings
    normalized_settings = self.normalize_candidate_settings(candidate_settings)
    candidate_slice = normalized_settings[:num_versions]
    
    # Build tone lookup (for logging/debugging)
    tone_lookup = {i: cfg["tone"] for i, cfg in enumerate(candidate_slice)}
    
    # Parallel generation using ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=min(num_versions, 3)) as executor:
        futures = {}
        for i, config in enumerate(candidate_slice):
            future = executor.submit(
                self._generate_single,
                text,
                config["temperature"],
                config["tone"],
                i
            )
            futures[future] = i
        
        # Collect results as they complete
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result()
                results.append((futures[future], result))
            except Exception as e:
                print(f"[ERROR] Candidate generation failed: {e}")
                results.append((futures[future], text))  # Fallback to original
    
    # Sort by original order
    results.sort(key=lambda x: x[0])
    candidates = [r[1] for r in results]
    
    # Remove duplicates (preserve order)
    unique_candidates = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)
    
    return unique_candidates if unique_candidates else [text]
```

**Prompt Engineering - _build_prompt()**:
```python
@classmethod
def _build_prompt(cls, text: str, tone: str, variant_index: int) -> str:
    \"\"\"Create tone-aware prompt ensuring clean output.\"\"\"
    preset = cls.TONE_PRESETS.get(tone, cls.TONE_PRESETS["original"])
    
    # Non-rewrite tones (original): minimal change
    if not preset.get("rewrite", False):
        guidance = "\\n".join([
            "You are a text autocorrect engine.",
            preset.get("instruction", "Fix ONLY grammar/spelling/punctuation."),
            preset.get("variation_hint", "Preserve the writer's voice."),
            "Return ONLY the corrected text, no explanations or quotes.",
        ])
        return f"{guidance}\\n\\nInput: {text}\\n\\nCorrected:"
    
    # Rewrite tones: use variation/first hints
    variation_hint = preset.get("variation_hint", "")
    first_hint = preset.get("first_hint", "")
    extra_line = first_hint if variant_index == 0 else variation_hint
    
    guidance_lines = [
        "You are a text rewriting engine.",
        preset.get("instruction", "Rewrite clearly while preserving meaning."),
    ]
    
    if extra_line:
        guidance_lines.append(extra_line)
    
    guidance_lines.extend([
        "Preserve the original meaning, factual details, and intent.",
        "Return ONLY the rewritten text, no explanations or quotes.",
    ])
    
    guidance = "\\n".join(guidance_lines)
    return f"{guidance}\\n\\nInput: {text}\\n\\nRewritten:"
```

**Why Parallel Generation?**:
- Sequential API calls would be slow (5 candidates  1-2s each = 5-10s total)
- Parallel execution reduces latency to ~2-3s (limited by slowest call)
- ThreadPoolExecutor manages worker threads automatically
- `max_workers` capped at 3 to avoid rate limiting

**Temperature Control**:
- Range: 0.0 (deterministic) to 1.0 (highly creative)
- Default settings:
  - Original: 0.30 (minimal variation)
  - Professional: 0.55 (moderate)
  - Formal: 0.60 (structured variation)
  - Informal: 0.65 (conversational diversity)
  - Detailed: 0.70 (balanced elaboration)
  - Creative: 0.80+ (expressive)

**Error Recovery**:
- Timeout: 30 seconds per batch (not per candidate)
- Network failure: Returns original text
- API error: Logs error, returns original text
- Empty response: Returns original text
- Duplicate filtering: Removes identical candidates post-generation

---

### 4. keystroke_buffer.py - Per-Window Text Tracking

**Location**: `correX/keystroke_buffer.py`  
**Purpose**: Track typed text separately for each application window without clipboard interference  
**Lines of Code**: ~250

**Why It Exists**:
Traditional autocorrect tools use clipboard to capture text, but this:
- Overwrites user's clipboard (data loss)
- Visible to user (clipboard managers show activity)
- Slow (clipboard operations are I/O bound)
- Unreliable (some apps block clipboard access)

CorreX uses an **internal buffer per window** that reconstructs typed text from keystrokes.

**Key Data Structures**:
```python
self._buffers: Dict[int, Deque[str]]   # window_handle  deque of keystrokes
self._max_buffer_size: int = 5000      # Max keystrokes per window
self._max_windows: int = 10            # Max tracked windows (LRU eviction)
self._window_order: Deque[int]         # LRU queue for window handles
```

**Core Logic - add_keystroke()**:
```python
def add_keystroke(self, key: str):
    \"\"\"Add keystroke to current window's buffer.\"\"\"
    window_handle = self._get_foreground_window()
    if not window_handle:
        return
    
    # Get or create buffer for this window
    if window_handle not in self._buffers:
        self._buffers[window_handle] = deque(maxlen=self._max_buffer_size)
        self._window_order.append(window_handle)
        
        # Evict oldest window if limit exceeded
        if len(self._buffers) > self._max_windows:
            oldest_window = self._window_order.popleft()
            self._buffers.pop(oldest_window, None)
    
    # Update LRU
    if window_handle in self._window_order:
        self._window_order.remove(window_handle)
    self._window_order.append(window_handle)
    
    # Convert keystroke to text
    text_char = self._keystroke_to_text(key)
    if text_char:
        self._buffers[window_handle].append(text_char)
```

**Keystroke-to-Text Conversion**:
```python
def _keystroke_to_text(self, key: str) -> Optional[str]:
    \"\"\"Convert keyboard event name to character.\"\"\"
    # Special keys
    if key == 'space':
        return ' '
    if key == 'enter':
        return '\\n'
    if key == 'tab':
        return '\\t'
    if key == 'backspace':
        # Remove last character from buffer
        window_handle = self._get_foreground_window()
        if window_handle in self._buffers and self._buffers[window_handle]:
            self._buffers[window_handle].pop()
        return None
    
    # Printable characters (length == 1)
    if len(key) == 1 and key.isprintable():
        return key
    
    # Ignore modifier keys, function keys, etc.
    return None
```

**Getting Text**:
```python
def get_text(self, limit: int = 10000) -> str:
    \"\"\"Retrieve text from current window's buffer.\"\"\"
    window_handle = self._get_foreground_window()
    if not window_handle or window_handle not in self._buffers:
        return ""
    
    buffer = self._buffers[window_handle]
    text = "".join(buffer)[-limit:]  # Last N characters
    return text.strip()
```

**Buffer Management**:
- **Per-Window Isolation**: Each window (app) has separate buffer
- **LRU Eviction**: When >10 windows tracked, oldest unused buffer is dropped
- **Size Limit**: Max 5000 keystrokes per window (prevents memory bloat)
- **Window Detection**: Uses `win32gui.GetForegroundWindow()` to get active window handle

**Limitations**:
- Doesn't track mouse clicks or selections (assumes linear typing)
- No clipboard paste detection (only keyboard input)
- Can't detect Ctrl+A, Ctrl+X operations (would require deeper hook)

---

### 5. text_buffer.py - Cross-App Text Replacement

**Location**: `correX/text_buffer.py`  
**Purpose**: Replace text in any Windows application using Win32 API and pywinauto  
**Lines of Code**: ~200

**The Challenge**:
Replacing text in arbitrary applications is hard because:
- Each app has different input methods (Win32 edit controls, custom text fields, web content)
- Security restrictions prevent some injection methods
- Clipboard must be preserved (user expectation)
- Race conditions between operations (select, copy, paste)

**Replacement Strategy (Multi-Method Fallback)**:

**Method 1: Clipboard + Selection (Primary)**
```python
def replace_text(self, old_text: str, new_text: str) -> bool:
    try:
        # 1. Save original clipboard
        original_clipboard = self._get_clipboard()
        
        # 2. Select all existing text (Ctrl+A)
        keyboard.press_and_release('ctrl+a')
        time.sleep(0.05)  # Wait for selection
        
        # 3. Copy to verify content matches
        keyboard.press_and_release('ctrl+c')
        time.sleep(0.05)
        current_text = self._get_clipboard()
        
        if current_text and old_text in current_text:
            # Text matches, replace it
            self._set_clipboard(new_text)
            time.sleep(0.05)
            keyboard.press_and_release('ctrl+v')
            time.sleep(0.05)
            
            # Restore original clipboard
            if original_clipboard:
                self._set_clipboard(original_clipboard)
            
            return True
        
        # Text doesn't match, restore clipboard and fail
        if original_clipboard:
            self._set_clipboard(original_clipboard)
        return False
    
    except Exception as e:
        print(f"[ERROR] Text replacement failed: {e}")
        return False
```

**Method 2: pywinauto Fallback (Secondary)**
```python
def _replace_via_pywinauto(self, old_text: str, new_text: str) -> bool:
    try:
        window = Application().connect(active_only=True)
        control = window.window()
        
        # Get current text
        current_text = control.window_text()
        
        if old_text in current_text:
            # Replace text
            updated_text = current_text.replace(old_text, new_text)
            control.set_text(updated_text)
            return True
        
        return False
    except Exception:
        return False
```

**Clipboard Operations (Win32 API)**:
```python
def _get_clipboard(self) -> Optional[str]:
    \"\"\"Read text from Windows clipboard.\"\"\"
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return data
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except:
            pass
    return None

def _set_clipboard(self, text: str):
    \"\"\"Write text to Windows clipboard.\"\"\"
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
    except Exception as e:
        print(f"[ERROR] Failed to set clipboard: {e}")
```

**Why Two Methods?**:
- **Clipboard method**: Works in 95% of apps (browser, Word, Notepad, chat apps)
- **pywinauto fallback**: Works for Win32 controls when clipboard fails
- **Neither works**: Some apps (admin-restricted, sandboxed) may block both

**Timing Considerations**:
- 50ms delays between operations (clipboard needs time to update)
- Operations are **synchronous** (blocks calling thread)
- Acceptable because called from keyboard hook thread (not GUI)

---

### 6. dictation_manager.py - Voice Recognition System

**Location**: `correX/dictation_manager.py`  
**Purpose**: Multi-engine speech-to-text with noise reduction and error recovery  
**Lines of Code**: ~300

**Recognition Engine Fallback Chain**:
1. **Google Speech API** (primary) - Cloud-based, highest accuracy, requires internet
2. **Whisper** (fallback) - OpenAI offline model, good accuracy, CPU-intensive
3. **Sphinx** (fallback) - CMU offline, lower accuracy, lightweight

**Core Architecture**:
```python
class DictationManager:
    def __init__(self, mic_overlay=None):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.mic_overlay = mic_overlay
        self.is_listening_flag = False
        self.listen_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        
        # Audio settings
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
```

**Start Listening Flow**:
```python
def start_listening(self, callback: Callable[[str], None]):
    with self.lock:
        if self.is_listening_flag:
            return
        self.is_listening_flag = True
        self.stop_event.clear()
    
    # Show mic overlay
    if self.mic_overlay:
        self.mic_overlay.show()
    
    # Start background thread
    self.listen_thread = threading.Thread(
        target=self._listen_loop,
        args=(callback,),
        daemon=True
    )
    self.listen_thread.start()
```

**Listen Loop (Background Thread)**:
```python
def _listen_loop(self, callback):
    with self.microphone as source:
        # Calibrate for ambient noise (0.5 seconds)
        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        while not self.stop_event.is_set():
            try:
                # Listen for speech (blocks until detected)
                audio = self.recognizer.listen(source, timeout=30)
                
                # Apply noise reduction if available
                if HAS_NOISEREDUCE:
                    audio = self._apply_noise_reduction(audio)
                
                # Try recognition engines in order
                text = self._recognize_speech(audio)
                
                if text:
                    callback(text)  # Invoke callback with recognized text
            
            except sr.WaitTimeoutError:
                continue  # No speech detected, keep listening
            except Exception as e:
                print(f"[ERROR] Dictation error: {e}")
                break
    
    # Hide overlay when done
    if self.mic_overlay:
        self.mic_overlay.hide()
```

**Speech Recognition with Fallbacks**:
```python
def _recognize_speech(self, audio) -> Optional[str]:
    # Try Google Speech API
    try:
        text = self.recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        pass  # Speech unintelligible
    except sr.RequestError:
        pass  # Network/API error
    
    # Try Whisper (if installed)
    if HAS_WHISPER:
        try:
            text = self.recognizer.recognize_whisper(audio)
            return text
        except Exception:
            pass
    
    # Try Sphinx (offline fallback)
    try:
        text = self.recognizer.recognize_sphinx(audio)
        return text
    except Exception:
        pass
    
    return None  # All engines failed
```

**Noise Reduction**:
```python
def _apply_noise_reduction(self, audio):
    \"\"\"Use noisereduce library to clean audio.\"\"\"
    try:
        import numpy as np
        import noisereduce as nr
        
        # Convert audio to numpy array
        audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
        sample_rate = audio.sample_rate
        
        # Apply stationary noise reduction
        reduced = nr.reduce_noise(
            y=audio_data,
            sr=sample_rate,
            stationary=True,
            prop_decrease=0.8
        )
        
        # Convert back to AudioData
        return sr.AudioData(reduced.tobytes(), sample_rate, audio.sample_width)
    except Exception:
        return audio  # Return original on failure
```

**Integration with AutoCorrectService**:
```python
# In autocorrect_service.py
def _on_dictation_text(self, text: str):
    \"\"\"Callback when speech recognized.\"\"\"
    # Temporarily suspend keyboard events (prevent interference)
    self._suspend_events = True
    
    try:
        # Type the recognized text
        keyboard.write(text)
        
        # Add to keystroke buffer (for potential correction)
        for char in text:
            self._keystroke_buffer.add_keystroke(char)
    
    finally:
        self._suspend_events = False
```

**Why Multi-Engine?**:
- **Google**: Best accuracy, but requires internet and has rate limits
- **Whisper**: Offline, high accuracy, but downloads large model (~1GB)
- **Sphinx**: Offline, lightweight, but lower accuracy
- Fallback chain ensures dictation works even offline or with network issues

---

### 7. config_manager.py - Configuration Persistence

**Location**: `correX/config_manager.py`  
**Purpose**: Load/save user settings to JSON with schema validation  
**Lines of Code**: ~250

**Configuration Schema**:
```python
DEFAULT_CONFIG = {
    "api_key": "",
    "model_name": "gemini-2.0-flash-exp",
    "trigger_key": "tab",
    "dictation_trigger_key": "ctrl+shift+d",
    "clear_trigger_key": None,  # Optional
    "version_count": 3,
    "candidate_settings": [
        {"temperature": 0.30, "tone": "original"},
        {"temperature": 0.55, "tone": "professional"},
        {"temperature": 0.60, "tone": "formal"},
        {"temperature": 0.65, "tone": "informal"},
        {"temperature": 0.70, "tone": "detailed"},
    ],
    "loading_position_x": 100,
    "loading_position_y": 100,
    "enable_notifications": True,
    "enable_history": True,
}
```

**File Location**:
- **Windows**: `%USERPROFILE%/.autocorrect_ai/config.json`
- **Example**: `C:/Users/YourName/.autocorrect_ai/config.json`

**Load Configuration**:
```python
def _load_config(self) -> dict:
    if not self.config_path.exists():
        return self._get_default_config()
    
    try:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        
        # Merge with defaults (in case new keys added)
        config = self._get_default_config()
        config.update(loaded)
        
        # Normalize candidate settings
        config["candidate_settings"] = self._normalize_candidate_settings(
            config.get("candidate_settings")
        )
        
        return config
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return self._get_default_config()
```

**Save Configuration**:
```python
def save(self):
    \"\"\"Write config to disk.\"\"\"
    try:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2)
        
        print(f"[INFO] Config saved to {self.config_path}")
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
```

**Candidate Settings Normalization**:
```python
def _normalize_candidate_settings(self, settings):
    \"\"\"Ensure candidate settings are valid.\"\"\"
    try:
        from .gemini_corrector import GeminiCorrector
        return GeminiCorrector.normalize_candidate_settings(settings)
    except:
        # Fallback if import fails
        return DEFAULT_CONFIG["candidate_settings"]
```

**Thread Safety**:
- Config is loaded once at startup (no concurrent reads)
- Writes are triggered by GUI (main thread only)
- No explicit locking needed (single-threaded writes)

---

### 8. history_manager.py - SQLite History Tracking

**Location**: `correX/history_manager.py`  
**Purpose**: Store correction history with automatic expiration  
**Lines of Code**: ~200

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON corrections(timestamp);
```

**Database Location**:
- **Windows**: `%USERPROFILE%/.autocorrect_ai/history.db`
- **Engine**: SQLite3 (embedded, no server needed)

**Add Correction**:
```python
def add_correction(self, original: str, corrected: str, model: str = None):
    \"\"\"Store a correction in the database.\"\"\"
    try:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO corrections (original_text, corrected_text, model_name) VALUES (?, ?, ?)",
                (original, corrected, model or "unknown")
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to save history: {e}")
```

**Auto-Cleanup (1 Hour Expiration)**:
```python
def cleanup_old_entries(self, hours: int = 1):
    \"\"\"Delete corrections older than N hours.\"\"\"
    try:
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM corrections WHERE timestamp < datetime('now', ? || ' hours')",
                (f"-{hours}",)
            )
            conn.commit()
            deleted = conn.total_changes
            if deleted > 0:
                print(f"[INFO] Cleaned up {deleted} old corrections")
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {e}")
```

**Get Recent History**:
```python
def get_recent(self, limit: int = 100):
    \"\"\"Retrieve recent corrections.\"\"\"
    try:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT original_text, corrected_text, timestamp FROM corrections ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"[ERROR] Failed to fetch history: {e}")
        return []
```

**Connection Management**:
- Uses context manager (`with` statement) for auto-commit/rollback
- Connection closed after each operation (SQLite is file-based, no persistent connection needed)
- Thread-safe by default (SQLite serializes writes)

**Privacy Considerations**:
- History stored locally (never sent to server)
- Auto-deletion after 1 hour (configurable)
- User can disable history tracking in config
- Database file can be manually deleted

---

## GUI Implementation

### 9. gui/app_gui.py - Configuration Interface

**Location**: `correX/gui/app_gui.py`  
**Purpose**: Comprehensive Tkinter GUI for configuring all CorreX settings  
**Lines of Code**: ~1,860

**GUI Architecture**:

The GUI is built using Tkinter with a modern card-based layout, scrollable canvas, and responsive design. It uses a queue-based command system for thread-safe updates.

**Key Components**:

**1. Thread-Safe UI Update Queue**:
```python
_UI_COMMANDS: queue.Queue[Callable[[], None]] = queue.Queue(maxsize=128)
_UI_READY = threading.Event()

def _process_ui_queue(window: tk.Tk):
    \"\"\"Process queued UI commands (runs on main thread).\"\"\"
    try:
        while True:
            command = _UI_COMMANDS.get_nowait()
            command()
    except queue.Empty:
        pass
    finally:
        window.after(50, lambda: _process_ui_queue(window))
```

**Why This Pattern?**:
- Tkinter is single-threaded (all UI updates must happen on main thread)
- Background threads (keyboard hooks, API calls) need to update GUI
- Solution: Background threads queue lambda functions, main thread executes them
- Example: `_UI_COMMANDS.put(lambda: status_label.config(text="Active"))`

**2. Window Setup and Icon Management**:
```python
def launch_app(...):
    # Create window
    window = tk.Tk()
    window.title("CorreX Control Center")
    
    # Responsive window sizing (70% screen width, 80% height)
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    window_width = max(980, min(int(screen_width * 0.7), 1400))
    window_height = max(720, min(int(screen_height * 0.8), 1000))
    window.minsize(900, 720)
    window.geometry(f"{window_width}x{window_height}")
    
    # Set taskbar icon (Windows-specific)
    if os.name == "nt":
        # Try asset manager icon
        if icon_path:
            window.iconbitmap(str(icon_path))
            base_root.iconbitmap(str(icon_path))
        
        # Fallback: Direct path to CorreX_logo.ico
        if not icon_set_successfully:
            direct_icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "CorreX_logo.ico"
            if direct_icon_path.exists():
                window.iconbitmap(str(direct_icon_path))
                base_root.iconbitmap(str(direct_icon_path))
```

**Why Two Icon Attempts?**:
- Asset manager may fail to find icon (path issues)
- Direct fallback ensures icon always loads
- Both `window` and `base_root` set for taskbar/tray consistency

**3. Scrollable Canvas Layout**:
```python
# Main canvas with vertical scrollbar
main_canvas = tk.Canvas(window, bg=COLORS['bg_secondary'])
scrollbar = ttk.Scrollbar(window, orient="vertical", command=main_canvas.yview)
scrollable_frame = tk.Frame(main_canvas, bg=COLORS['bg_secondary'])

# Create window inside canvas
canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
main_canvas.configure(yscrollcommand=scrollbar.set)

# Sync canvas width with window resize (throttled to prevent flicker)
resize_job = {'id': None}

def _schedule_canvas_width_sync():
    if resize_job['id'] is not None:
        window.after_cancel(resize_job['id'])
    resize_job['id'] = window.after(90, _sync_canvas_width)

def _sync_canvas_width():
    new_width = max(main_canvas.winfo_width(), 400)
    main_canvas.itemconfig(canvas_window, width=new_width)

scrollable_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
window.bind("<Configure>", lambda e: _schedule_canvas_width_sync())
```

**Why Throttled Resize?**:
- Window resize events fire rapidly (dozens per second)
- Updating canvas width each time causes flicker
- 90ms throttle: Only update after resize pause
- `resize_job` dict: Stores timer ID for cancellation

**4. Candidate Personalization Panel**:

This is the most complex GUI component, allowing per-candidate tone and temperature configuration.

```python
# Container for 5 candidate rows
candidate_rows = []

for i in range(MAX_CANDIDATES):
    row_frame = tk.Frame(candidate_panel, bg=COLORS['bg_secondary'])
    row_frame.pack(fill='x', padx=10, pady=8)
    
    # Top row: candidate name + temperature slider + value label
    top_row = tk.Frame(row_frame, bg=COLORS['bg_secondary'])
    top_row.pack(fill='x')
    
    name_label = tk.Label(top_row, text=f"Candidate {i+1}", ...)
    name_label.pack(side='left')
    
    temp_value_var = tk.StringVar(value="0.50")
    temp_value_label = tk.Label(top_row, textvariable=temp_value_var, ...)
    temp_value_label.pack(side='right', padx=(0, 10))
    
    # Temperature slider (0.0 to 1.0, step 0.05)
    temp_scale = ttk.Scale(
        top_row,
        from_=0.0,
        to=1.0,
        orient='horizontal',
        command=lambda val, idx=i: _on_temp_change(idx, val)
    )
    temp_scale.pack(side='right', fill='x', expand=True, padx=(10, 10))
    
    # Tone dropdown
    tone_row = tk.Frame(row_frame, bg=COLORS['bg_secondary'])
    tone_row.pack(fill='x', pady=(4, 0))
    
    tone_label = tk.Label(tone_row, text="Tone:", ...)
    tone_label.pack(side='left')
    
    tone_var = tk.StringVar()
    tone_combo = ttk.Combobox(
        tone_row,
        textvariable=tone_var,
        values=[opt["label"] for opt in TONE_OPTIONS],
        state='readonly',
        width=25
    )
    tone_combo.pack(side='left', padx=(10, 0))
    tone_combo.bind('<<ComboboxSelected>>', lambda e, idx=i: _on_tone_change(idx))
    
    # Tone description (dynamic)
    tone_desc_var = tk.StringVar(value="")
    tone_desc_label = tk.Label(row_frame, textvariable=tone_desc_var, ...)
    tone_desc_label.pack(fill='x', pady=(4, 0))
    
    # Store references for later access
    candidate_rows.append({
        'frame': row_frame,
        'temp_scale': temp_scale,
        'temp_value_var': temp_value_var,
        'tone_combo': tone_combo,
        'tone_var': tone_var,
        'tone_desc_var': tone_desc_var,
    })
```

**Dynamic Visibility Control**:
```python
def _update_candidate_visibility():
    \"\"\"Show/hide candidate rows based on version count.\"\"\"
    version_count = int(version_var.get())
    for i, row_data in enumerate(candidate_rows):
        if i < version_count:
            row_data['frame'].pack(fill='x', padx=10, pady=8)
        else:
            row_data['frame'].pack_forget()
```

**5. Trigger Capture System**:

Interactive popup for setting custom keyboard shortcuts:

```python
def _capture_trigger(target_var: tk.StringVar, prompt_title: str):
    \"\"\"Show modal popup to capture keyboard shortcut.\"\"\"
    capture = tk.Toplevel(window)
    capture.title(prompt_title)
    capture.configure(bg=COLORS['bg_secondary'])
    capture.attributes('-topmost', True)
    capture.resizable(False, False)
    capture.transient(window)
    capture.grab_set()  # Modal
    
    message_var = tk.StringVar(value="Press the desired key combination. Press Esc to cancel.")
    label = tk.Label(capture, textvariable=message_var, ...)
    label.pack(fill='both', expand=True, padx=20, pady=20)
    
    # Center on parent window
    capture.geometry(f"360x140+{x}+{y}")
    
    captured_trigger = None
    
    def on_key_press(event):
        nonlocal captured_trigger
        
        if event.name == 'esc':
            capture.destroy()
            return
        
        # Convert event to normalized trigger string
        trigger = _format_event_to_trigger(event)
        if trigger:
            captured_trigger = trigger
            message_var.set(f"Captured: {trigger}\\n\\nPress Enter to confirm, Esc to cancel")
    
    def on_enter(event):
        if captured_trigger:
            target_var.set(captured_trigger)
        capture.destroy()
    
    keyboard.on_press(on_key_press)
    capture.bind('<Return>', on_enter)
    capture.bind('<Escape>', lambda e: capture.destroy())
    
    capture.wait_window()  # Block until window closed
    keyboard.unhook_all()  # Remove temporary hook
```

**Event-to-Trigger Formatting**:
```python
def _format_event_to_trigger(event):
    \"\"\"Convert keyboard event to normalized trigger string.\"\"\"
    CTRL_MASK = 0x0004
    SHIFT_MASK = 0x0001
    ALT_MASK = 0x0008  # Only 0x0008, not 0x20000 (NumLock)
    
    keysym = event.name.lower()
    state = getattr(event, 'state', 0) or 0
    
    modifiers = []
    if state & CTRL_MASK:
        modifiers.append('ctrl')
    if state & SHIFT_MASK:
        modifiers.append('shift')
    if state & ALT_MASK:
        modifiers.append('alt')
    
    # Order: ctrl, shift, alt, then key
    ordered = []
    for mod in ['ctrl', 'shift', 'alt']:
        if mod in modifiers:
            ordered.append(mod)
    ordered.append(keysym)
    
    return '+'.join(ordered)
```

**Critical Bug Fix**:
- Windows event state includes NumLock bit (0x20000)
- NumLock was being detected as Alt modifier
- Solution: Only check 0x0008 for Alt, not 0x20000

**6. Quick Start Guide Popup**:

Instead of opening markdown file in external app, show in-app popup:

```python
def open_quick_start():
    \"\"\"Open Quick Start guide in popup window.\"\"\"
    popup = tk.Toplevel(window)
    popup.title("CorreX Quick Start Guide")
    popup.geometry("800x600")
    popup.transient(window)
    popup.grab_set()  # Modal
    
    # Scrollable text widget
    text_scroll = tk.Scrollbar(popup)
    text_scroll.pack(side='right', fill='y')
    
    text_widget = tk.Text(
        popup,
        wrap='word',
        font=('Segoe UI', 10),
        yscrollcommand=text_scroll.set
    )
    text_widget.pack(side='left', fill='both', expand=True, padx=20, pady=20)
    text_scroll.config(command=text_widget.yview)
    
    # Read and display QUICK_START.md
    try:
        with open(quick_start_path, 'r', encoding='utf-8') as f:
            content = f.read()
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')  # Read-only
    except Exception as e:
        text_widget.insert('1.0', f"Error reading guide: {e}")
    
    # Close button
    close_btn = ModernButton(popup, text="Close", command=popup.destroy)
    close_btn.pack(pady=(0, 20))
```

**7. Save & Apply Logic**:
```python
def save_settings():
    \"\"\"Save all GUI settings to config and apply to service.\"\"\"
    try:
        # Get values from GUI
        api_key = api_key_entry.get().strip()
        model_name = model_combo.get()
        trigger_key = trigger_var.get()
        dictation_key = dictation_var.get()
        version_count = int(version_var.get())
        
        # Build candidate settings from GUI
        candidate_settings = []
        for i in range(MAX_CANDIDATES):
            temp = candidate_rows[i]['temp_scale'].get()
            tone_label = candidate_rows[i]['tone_var'].get()
            tone_key = TONE_LABEL_TO_KEY.get(tone_label, 'original')
            
            candidate_settings.append({
                'temperature': round(float(temp), 2),
                'tone': tone_key
            })
        
        # Save to config
        config.set('api_key', api_key)
        config.set('model_name', model_name)
        config.set('trigger_key', trigger_key)
        config.set('dictation_trigger_key', dictation_key)
        config.set('version_count', version_count)
        config.set('candidate_settings', candidate_settings)
        config.save()
        
        # Apply to running service
        service.set_trigger_key(trigger_key)
        service.set_dictation_trigger_key(dictation_key)
        service.set_version_count(version_count)
        service.set_candidate_settings(candidate_settings)
        
        # Reinitialize corrector if API key changed
        if api_key and api_key != "dummy-key-replace-in-gui":
            new_corrector = GeminiCorrector(api_key=api_key, model_name=model_name)
            service._corrector = new_corrector
        
        messagebox.showinfo("Success", "Settings saved and applied!")
    
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save settings: {e}")
```

**GUI Best Practices Implemented**:
- **Responsive Layout**: Grid weights, fill='x', expand=True
- **No Fixed Widths**: Removed all `wraplength=` parameters
- **Throttled Events**: Resize handler with 90ms delay
- **Thread Safety**: Queue-based UI updates from background threads
- **Modal Dialogs**: `grab_set()` for trigger capture, `transient()` for parent relationship
- **Proper Cleanup**: `unhook_all()` after trigger capture, `destroy()` on close

---


## System Integration

### 10. tray_icon.py - System Tray Interface

**Location**: `correX/tray_icon.py`  
**Purpose**: Lightweight system tray icon with menu for quick access  
**Lines of Code**: ~150

**Key Features**:
- Always-visible tray icon (even when GUI closed)
- Right-click menu: Show GUI, Quit
- Icon loading with fallback (asset manager  direct path)
- Runs on daemon thread (auto-terminates when main app exits)

**Implementation**:
```python
from pystray import Icon, Menu, MenuItem
from PIL import Image

def setup_tray_icon(show_gui_callback, asset_manager):
    \"\"\"Create and run system tray icon.\"\"\"
    
    # Load icon image
    icon_path = asset_manager.get_icon_path()
    if icon_path and icon_path.exists():
        icon_image = Image.open(icon_path)
    else:
        # Fallback: Create simple colored square
        icon_image = Image.new('RGB', (64, 64), color=(73, 109, 137))
    
    # Define menu
    menu = Menu(
        MenuItem('Show CorreX', lambda: show_gui_callback()),
        MenuItem('Quit', lambda: icon.stop())
    )
    
    # Create icon
    icon = Icon("CorreX", icon_image, "CorreX - AI Text Correction", menu)
    
    # Run on daemon thread (auto-exits with main thread)
    icon.run()
```

**Thread Safety Notes**:
- Tray icon runs on separate daemon thread
- `show_gui_callback` must be thread-safe (uses `_UI_COMMANDS` queue)
- `icon.stop()` triggers clean shutdown

**Why Daemon Thread?**:
- Main thread runs Tkinter event loop (blocking)
- Daemon thread allows concurrent tray icon operation
- Daemon auto-terminates when main thread exits (no explicit cleanup needed)

---

### 11. loading_overlay.py - Transparent Loading Indicator

**Location**: `correX/loading_overlay.py`  
**Purpose**: Full-screen transparent overlay shown during AI processing  
**Lines of Code**: ~120

**Why Needed?**:
- AI correction takes 1-3 seconds
- User needs visual feedback (not frozen)
- Prevents user from typing during processing (would corrupt buffer)

**Implementation**:
```python
import tkinter as tk

class LoadingOverlay:
    def __init__(self):
        self.window = None
    
    def show(self):
        \"\"\"Display transparent overlay with spinner.\"\"\"
        if self.window:
            return  # Already showing
        
        # Create borderless, always-on-top window
        self.window = tk.Tk()
        self.window.title("Processing...")
        self.window.attributes('-alpha', 0.5)  # 50% transparency
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)  # Remove title bar
        self.window.configure(bg='black')
        
        # Full screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        self.window.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Spinner label
        label = tk.Label(
            self.window,
            text="Processing...",
            font=('Segoe UI', 16),
            fg='white',
            bg='black'
        )
        label.place(relx=0.5, rely=0.5, anchor='center')
        
        self.window.update()  # Force render
    
    def hide(self):
        \"\"\"Remove overlay.\"\"\"
        if self.window:
            self.window.destroy()
            self.window = None
```

**Design Trade-offs**:
- **Transparency**: 0.5 alpha allows user to see what's happening beneath
- **Topmost**: Ensures overlay stays above all windows
- **Overrideredirect**: Removes title bar for cleaner look (but also removes minimize/close buttons)
- **Full Screen**: Covers entire screen to prevent input during processing

**Thread Safety**:
- `show()` and `hide()` called from keyboard hook thread
- Tkinter calls must happen on main thread
- Solution: Queue overlay commands via `_UI_COMMANDS.put(lambda: overlay.show())`

---

### 12. mic_overlay.py - Voice Dictation Indicator

**Location**: `correX/mic_overlay.py`  
**Purpose**: Visual indicator showing microphone is listening  
**Lines of Code**: ~180

**Why Separate from Loading Overlay?**:
- Different visual style (red circle, pulsing animation)
- Shows live audio level (volume meter)
- User needs to know when to speak

**Implementation**:
```python
import tkinter as tk
from tkinter import Canvas
import math

class MicOverlay:
    def __init__(self):
        self.window = None
        self.pulse_phase = 0
    
    def show(self):
        \"\"\"Display pulsing red microphone indicator.\"\"\"
        if self.window:
            return
        
        self.window = tk.Tk()
        self.window.title("Listening...")
        self.window.attributes('-alpha', 0.8)
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)
        self.window.configure(bg='black')
        
        # Small corner window (not full screen like loading overlay)
        self.window.geometry("200x200+50+50")
        
        # Canvas for drawing pulsing circle
        self.canvas = Canvas(self.window, bg='black', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        
        # Start pulse animation
        self._animate_pulse()
        
        self.window.update()
    
    def _animate_pulse(self):
        \"\"\"Animate pulsing red circle.\"\"\"
        if not self.window:
            return
        
        self.canvas.delete('all')  # Clear previous frame
        
        # Calculate pulse size
        self.pulse_phase += 0.1
        scale = 0.8 + 0.2 * math.sin(self.pulse_phase)
        radius = 40 * scale
        
        # Draw red circle
        cx, cy = 100, 100
        self.canvas.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill='red', outline='white', width=2
        )
        
        # Text
        self.canvas.create_text(
            cx, cy + 70,
            text="Listening...",
            fill='white',
            font=('Segoe UI', 12)
        )
        
        # Schedule next frame (30 FPS)
        self.window.after(33, self._animate_pulse)
    
    def hide(self):
        \"\"\"Remove overlay.\"\"\"
        if self.window:
            self.window.destroy()
            self.window = None
```

**Animation Details**:
- **Pulse**: Sine wave modulates circle radius (0.8x to 1.0x base size)
- **Frame Rate**: 33ms = ~30 FPS (smooth animation without high CPU usage)
- **Colors**: Red (active), white outline (contrast), black background

**Position**:
- Corner placement (50, 50) instead of full screen
- User can still see most of screen while dictating

---

### 13. asset_manager.py - Resource Loading

**Location**: `correX/asset_manager.py`  
**Purpose**: Centralized asset loading with caching and fallbacks  
**Lines of Code**: ~100

**Why Needed?**:
- Icon paths differ between dev (source tree) and production (PyInstaller bundle)
- Avoid hardcoded paths scattered across codebase
- Cache loaded assets (don't reload icon 10 times)

**Implementation**:
```python
from pathlib import Path
from typing import Optional

class AssetManager:
    def __init__(self):
        self._cache = {}
        self._base_path = self._find_asset_base()
    
    def _find_asset_base(self) -> Path:
        \"\"\"Locate assets directory (dev or PyInstaller bundle).\"\"\"
        # Try 1: Source tree (development)
        source_path = Path(__file__).resolve().parent / 'assets'
        if source_path.exists():
            return source_path
        
        # Try 2: PyInstaller _MEIPASS (temporary extraction dir)
        import sys
        if hasattr(sys, '_MEIPASS'):
            bundle_path = Path(sys._MEIPASS) / 'assets'
            if bundle_path.exists():
                return bundle_path
        
        # Try 3: Current working directory
        cwd_path = Path.cwd() / 'assets'
        if cwd_path.exists():
            return cwd_path
        
        # Fallback: Return source path even if doesn't exist
        return source_path
    
    def get_icon_path(self, icon_name: str = "CorreX_logo.ico") -> Optional[Path]:
        \"\"\"Get path to icon file with caching.\"\"\"
        cache_key = f"icon:{icon_name}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        icon_path = self._base_path / 'icons' / icon_name
        
        if icon_path.exists():
            self._cache[cache_key] = icon_path
            return icon_path
        
        # Not found
        self._cache[cache_key] = None
        return None
```

**PyInstaller Handling**:
- **sys._MEIPASS**: Temporary directory where PyInstaller extracts bundled files
- **Fallback Chain**: Source tree  _MEIPASS  CWD  None
- **Caching**: Avoid repeated filesystem checks

**Usage**:
```python
asset_manager = AssetManager()
icon_path = asset_manager.get_icon_path()  # Returns Path or None
if icon_path:
    window.iconbitmap(str(icon_path))
```

---


## Threading Model

CorreX uses a multi-threaded architecture to handle concurrent operations without blocking the user interface.

### Thread Types

**1. Main Thread (Tkinter Event Loop)**:
- **What Runs Here**: All GUI operations (app_gui.py)
- **Created By**: `tk.Tk()` and `window.mainloop()`
- **Lifetime**: Entire application lifetime
- **Critical Rule**: ONLY this thread can modify Tkinter widgets
- **Communication**: Processes `_UI_COMMANDS` queue every 50ms

**2. Daemon Thread (System Tray)**:
- **What Runs Here**: `pystray.Icon.run()` (tray_icon.py)
- **Created By**: `icon.run()` starts background thread automatically
- **Lifetime**: Same as main thread (auto-exits when main thread stops)
- **Purpose**: Allow tray icon to respond to clicks while GUI is blocked
- **Why Daemon**: No explicit cleanup needed (Python auto-terminates daemons on exit)

**3. Keyboard Hook Thread**:
- **What Runs Here**: Global keyboard event handler (`keyboard.hook()`)
- **Created By**: `keyboard` library spawns internal thread
- **Lifetime**: From `keyboard.hook()` to `keyboard.unhook_all()`
- **Critical Timing**: Events fire immediately (< 1ms latency)
- **Responsibilities**:
  - Detect trigger keys (Ctrl+Shift+A)
  - Track typed characters for buffer
  - Handle candidate navigation (Tab, Shift+Tab)
  - Launch dictation (Ctrl+Shift+D)

**4. API Worker Threads (ThreadPoolExecutor)**:
- **What Runs Here**: Parallel AI candidate generation (gemini_corrector.py)
- **Created By**: `ThreadPoolExecutor(max_workers=5)`
- **Lifetime**: Per correction request (threads reused from pool)
- **Purpose**: Generate 5 candidates in parallel (1-3 seconds each)
- **Thread Safety**: Each thread has isolated API connection (no shared state)

**5. Dictation Listen Thread**:
- **What Runs Here**: `_listen_loop()` in dictation_manager.py
- **Created By**: `threading.Thread(target=_listen_loop, daemon=True).start()`
- **Lifetime**: From `start_listening()` to `stop_listening()`
- **Purpose**: Block on microphone input without freezing GUI
- **Blocking Operations**: `recognizer.listen()` waits for audio (5-30 seconds)

---

### Synchronization Patterns

**Pattern 1: RLock for State Protection**

Used in `autocorrect_service.py` to protect correction state:

```python
class AutoCorrectService:
    def __init__(self):
        self._state_lock = threading.RLock()  # Reentrant lock
        self._current_candidates = []
        self._current_idx = 0
    
    def _handle_correction_trigger(self, ...):
        with self._state_lock:
            # Read/write correction state safely
            self._current_candidates = candidates
            self._current_idx = 0
    
    def _navigate_candidate(self, direction: int):
        with self._state_lock:
            # Modify index safely
            self._current_idx = (self._current_idx + direction) % len(self._current_candidates)
```

**Why RLock (Reentrant)?**:
- Same thread can acquire lock multiple times
- Needed because `_handle_correction_trigger` may call other locked methods
- Prevents deadlock in recursive scenarios

**Pattern 2: UI Command Queue**

Thread-safe pattern for updating GUI from background threads:

```python
# In app_gui.py
_UI_COMMANDS: queue.Queue[Callable[[], None]] = queue.Queue(maxsize=128)

def _process_ui_queue(window: tk.Tk):
    \"\"\"Runs on main thread, executes queued commands.\"\"\"
    try:
        while True:
            command = _UI_COMMANDS.get_nowait()
            command()  # Execute on main thread
    except queue.Empty:
        pass
    finally:
        window.after(50, lambda: _process_ui_queue(window))  # Repeat

# From keyboard hook thread:
def on_trigger_pressed():
    # Can't update GUI directly (wrong thread)
    _UI_COMMANDS.put(lambda: status_label.config(text="Processing..."))
```

**Why This Works**:
- `queue.Queue` is thread-safe (built-in locking)
- Lambda captures widget reference and operation
- Main thread executes lambda (correct thread for Tkinter)

**Pattern 3: Event Flags for Lifecycle**

Used for signaling between threads:

```python
class DictationManager:
    def __init__(self):
        self._stop_event = threading.Event()  # Initially unset
        self._listen_thread = None
    
    def start_listening(self):
        self._stop_event.clear()  # Reset flag
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
    
    def stop_listening(self):
        self._stop_event.set()  # Signal thread to stop
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)  # Wait for graceful exit
    
    def _listen_loop(self):
        while not self._stop_event.is_set():
            # Listen for audio...
            if self._stop_event.is_set():
                break
```

**Why Event over Boolean?**:
- `threading.Event` is thread-safe (no need for separate lock)
- `is_set()` check is atomic
- `join()` waits for thread to actually finish (vs just setting flag)

**Pattern 4: ThreadPoolExecutor for Parallelism**

Used in `gemini_corrector.py` for concurrent API calls:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def cleanup_paragraph(self, text: str, count: int = 5) -> List[Dict]:
    \"\"\"Generate N candidates in parallel.\"\"\"
    futures = []
    
    with ThreadPoolExecutor(max_workers=min(count, 5)) as executor:
        for i in range(count):
            future = executor.submit(self._generate_single_candidate, text, i)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)
                results.append(result)
            except Exception as e:
                results.append({'text': f'[Error: {e}]', 'temperature': 0.5, 'tone': 'original'})
    
    return results
```

**Why ThreadPoolExecutor?**:
- Automatically manages thread lifecycle (no manual thread creation)
- Limits concurrent threads (5 max prevents API rate limit)
- `as_completed()` returns results as soon as available (not in order)
- Timeout per future (don't hang indefinitely if one API call stalls)

---

### Race Condition Prevention

**Issue 1: Overlapping Corrections**

**Problem**: User presses trigger twice rapidly (while first correction is processing)

**Solution**:
```python
# In autocorrect_service.py
def _handle_correction_trigger(self, ...):
    if self._is_correcting:
        return  # Ignore trigger if already processing
    
    self._is_correcting = True
    try:
        # Generate candidates...
        # Replace text...
    finally:
        self._is_correcting = False
```

**Issue 2: Buffer Modification During Replacement**

**Problem**: User types more characters while text replacement is in progress

**Solution**: Loading overlay blocks all input during correction
```python
# Show overlay (prevents typing)
overlay.show()

try:
    # Replace text (1-2 seconds)
    text_buffer.replace_selected_text(candidate_text)
finally:
    # Hide overlay (allow typing again)
    overlay.hide()
```

**Issue 3: Dictation Start While Correction Active**

**Problem**: Both features modify text buffer simultaneously

**Solution**: Check flags before starting either operation
```python
def toggle_dictation(self):
    if self._is_correcting:
        return  # Don't start dictation during correction
    
    if self._is_dictating:
        self.stop_dictation()
    else:
        if not self._is_correcting:  # Double-check
            self.start_dictation()
```

---

### Thread Communication Diagram

```

                         Main Thread (Tkinter)                       
  - Runs GUI event loop                                              
  - Processes _UI_COMMANDS queue every 50ms                          
  - Only thread allowed to modify widgets                            

                         
                          Queues lambda commands
                         

                    Keyboard Hook Thread                             
  - Detects trigger keys (Ctrl+Shift+A, Tab, etc.)                  
  - Acquires _state_lock before modifying correction state          
  - Queues GUI updates via _UI_COMMANDS.put(lambda: ...)            

                         
                          Spawns on trigger
                         

              API Worker Threads (ThreadPoolExecutor)                
  - 5 threads max                                                    
  - Each generates one candidate                                     
  - No shared state (isolated API connections)                      
  - Returns results to keyboard hook thread                          



                  Dictation Listen Thread (Daemon)                   
  - Blocks on microphone input (5-30 seconds)                       
  - Checks _stop_event.is_set() each loop iteration                 
  - Queues transcribed text via text_buffer                          



                  Tray Icon Thread (Daemon)                          
  - Runs pystray event loop                                          
  - On menu click, queues show_gui() via _UI_COMMANDS               
  - Auto-terminates when main thread exits                           

```

---


## Data Flow & State Management

### Correction Flow (End-to-End)

```
1. User Types Text
   
   > keystroke_buffer.add_keystroke(key, window_id)
        - Appends character to window-specific deque
        - Maintains 5000 keystroke limit per window
        - Tracks current window handle for isolation

2. User Presses Trigger (Ctrl+Shift+A)
   
   > keyboard hook detects event
        
        > autocorrect_service._on_key_press(event)
             
             > Is trigger match? YES
                  
                  > _handle_correction_trigger()
                       
                       > Acquire _state_lock
                       
                       > Set _is_correcting = True
                       
                       > Show loading overlay (via UI queue)
                       
                       > Extract text from buffer
                            
                            > keystroke_buffer.get_recent_text(window_id, max_chars=500)
                                 - Returns last 500 chars from current window
                                 - Converts keystrokes to text (handles backspace)

3. AI Correction (Parallel)
   
   > corrector.cleanup_paragraph(text, count=5)
        
        > ThreadPoolExecutor spawns 5 worker threads
             
             > Thread 1: Generate candidate with settings[0] (temperature=0.30, tone=original)
             > Thread 2: Generate candidate with settings[1] (temperature=0.55, tone=professional)
             > Thread 3: Generate candidate with settings[2] (temperature=0.60, tone=formal)
             > Thread 4: Generate candidate with settings[3] (temperature=0.65, tone=informal)
             > Thread 5: Generate candidate with settings[4] (temperature=0.70, tone=detailed)
                  
                  > Each thread:
                       - Builds tone-aware prompt
                       - Calls Gemini API (1-3 seconds)
                       - Returns {'text': ..., 'temperature': ..., 'tone': ...}
        
        > as_completed() collects results as they arrive
             - Returns list of 5 candidates (unordered)

4. Text Replacement
   
   > Select original text
        
        > text_buffer.select_last_n_chars(len(original_text))
             
             > Method 1: Win32 clipboard + Ctrl+A simulation
                 - Copy original to temp variable
                 - Clear clipboard
                 - Simulate Ctrl+Shift+Left (select N chars)
                 - Verify selection length matches
             
             > Method 2 (fallback): pywinauto
                  - Find active window element
                  - Set selection range programmatically
   
   > Replace with first candidate
        
        > text_buffer.replace_selected_text(candidates[0]['text'])
             
             > Method 1: Clipboard paste
                 - Save current clipboard
                 - Set clipboard to new text
                 - Simulate Ctrl+V
                 - Restore original clipboard
                 - Wait 50ms for paste to complete
             
             > Method 2 (fallback): pywinauto
                  - Insert text directly via accessibility API

5. Store State for Navigation
   
   > With _state_lock:
        - self._current_candidates = candidates
        - self._current_idx = 0
        - self._original_text = original_text

6. Hide Loading Overlay (via UI queue)

7. User Navigates Candidates (Optional)
   
   > User presses Tab or Shift+Tab
        
        > _navigate_candidate(direction=+1 or -1)
             
             > Acquire _state_lock
             
             > Calculate new index: (current_idx + direction) % len(candidates)
             
             > Select current text: text_buffer.select_last_n_chars(len(current_candidate))
             
             > Replace with next candidate: text_buffer.replace_selected_text(next_candidate)

8. Log to History (Async)
   
   > history_manager.add_correction(
            original=original_text,
            corrected=candidates[0]['text'],
            tone=candidates[0]['tone'],
            temperature=candidates[0]['temperature']
        )
        - Insert into SQLite (timestamp, window_id, original, corrected, tone, temperature)
        - Auto-cleanup: DELETE WHERE timestamp < (now - 1 hour)
```

---

### Dictation Flow (End-to-End)

```
1. User Presses Dictation Trigger (Ctrl+Shift+D)
   
   > autocorrect_service.toggle_dictation()
        
        > If _is_correcting: return (don't interrupt correction)
        
        > If not _is_dictating:
             
             > Start Dictation
                  
                  > Set _is_dictating = True
                  
                  > Show mic overlay (via UI queue)
                  
                  > dictation_manager.start_listening()
                       
                       > Spawn daemon thread: _listen_loop()

2. Listen Loop (Daemon Thread)
   
   > while not _stop_event.is_set():
        
        > recognizer.listen(source, timeout=5, phrase_time_limit=10)
            - Blocks until speech detected or timeout
            - Records audio for max 10 seconds
        
        > audio captured?
             
             > _recognize_speech(audio_data)
                  
                  > Try Engine 1: Google Speech Recognition
                      - recognizer.recognize_google(audio)
                      - Free, accurate, requires internet
                      - Returns text or raises UnknownValueError
                  
                  > Try Engine 2 (fallback): Whisper
                      - recognizer.recognize_whisper(audio)
                      - Offline, slower, requires model download
                  
                  > Try Engine 3 (final fallback): Sphinx
                       - recognizer.recognize_sphinx(audio)
                       - Offline, less accurate, always available

3. Noise Reduction (Before Recognition)
   
   > audio_np = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
        
        > reduced_audio = noisereduce.reduce_noise(
                 y=audio_np,
                 sr=audio.sample_rate,
                 stationary=True  # Assume constant background noise
             )
        
        > Convert back to AudioData object
             - Improves recognition accuracy in noisy environments

4. Insert Transcribed Text
   
   > On successful recognition:
        
        > text_buffer.insert_text_at_cursor(transcribed_text)
             
             > Method 1: Clipboard paste
                 - Save current clipboard
                 - Set clipboard to transcribed text
                 - Simulate Ctrl+V
                 - Restore original clipboard
             
             > Method 2 (fallback): pywinauto
                  - Get cursor position
                  - Insert text at position

5. Stop Dictation (User Presses Trigger Again)
   
   > autocorrect_service.toggle_dictation()
        
        > If _is_dictating:
             
             > dictation_manager.stop_listening()
                  
                  > _stop_event.set()  # Signal listen loop to exit
                  
                  > _listen_thread.join(timeout=2.0)  # Wait for thread
                  
                  > Hide mic overlay (via UI queue)
```

---

### State Variables

**AutoCorrectService State**:
```python
class AutoCorrectService:
    # Correction state (protected by _state_lock)
    self._current_candidates: List[Dict] = []
    self._current_idx: int = 0
    self._original_text: str = ""
    
    # Operation flags (atomic checks)
    self._is_correcting: bool = False
    self._is_dictating: bool = False
    
    # Configuration (thread-safe updates via setters)
    self._trigger_key: str = "ctrl+shift+a"
    self._dictation_trigger_key: str = "ctrl+shift+d"
    self._version_count: int = 5
    self._candidate_settings: List[Dict] = [...]
    
    # Component references
    self._corrector: GeminiCorrector
    self._keystroke_buffer: KeystrokeBuffer
    self._text_buffer: TextBuffer
    self._dictation_manager: DictationManager
    self._history_manager: HistoryManager
    self._loading_overlay: LoadingOverlay
    self._mic_overlay: MicOverlay
```

**KeystrokeBuffer State**:
```python
class KeystrokeBuffer:
    # Per-window keystroke history
    self._buffers: Dict[int, Deque[str]] = {}
    # window_id -> deque(['h', 'e', 'l', 'l', 'o', ' ', 'w', 'o', 'r', 'l', 'd'])
    
    # LRU tracking for eviction
    self._last_access: Dict[int, float] = {}
    # window_id -> timestamp
    
    # Configuration
    self.MAX_BUFFER_SIZE: int = 5000  # keystrokes per window
    self.MAX_WINDOWS: int = 20  # total windows tracked
```

**ConfigManager State**:
```python
class ConfigManager:
    # In-memory cache
    self._config: Dict[str, Any] = {
        'api_key': 'your-api-key',
        'model_name': 'gemini-1.5-flash',
        'trigger_key': 'ctrl+shift+a',
        'dictation_trigger_key': 'ctrl+shift+d',
        'version_count': 5,
        'candidate_settings': [
            {'temperature': 0.30, 'tone': 'original'},
            {'temperature': 0.55, 'tone': 'professional'},
            # ... 3 more
        ]
    }
    
    # File path
    self._config_path: Path = Path.home() / '.autocorrect_ai' / 'config.json'
```

**HistoryManager State**:
```python
class HistoryManager:
    # SQLite connection (thread-safe with check_same_thread=False)
    self._conn: sqlite3.Connection
    
    # Database path
    self._db_path: Path = Path.home() / '.autocorrect_ai' / 'history.db'
    
    # Schema:
    # CREATE TABLE corrections (
    #     id INTEGER PRIMARY KEY AUTOINCREMENT,
    #     timestamp TEXT NOT NULL,
    #     window_id INTEGER,
    #     original TEXT NOT NULL,
    #     corrected TEXT NOT NULL,
    #     tone TEXT,
    #     temperature REAL
    # )
```

---

### State Transitions

**Correction State Machine**:
```
[Idle]
  
  > Trigger Pressed
       
       > [Correcting] (_is_correcting = True, overlay shown)
            
            > Success: Candidates generated
                > [Navigating] (candidates stored, overlay hidden)
                     
                     > Tab/Shift+Tab: Cycle through candidates
                         > Stay in [Navigating]
                     
                     > Any other key: Clear state
                          > [Idle] (_is_correcting = False, candidates cleared)
            
            > Error: API failure
                 > [Idle] (overlay hidden, error logged)
```

**Dictation State Machine**:
```
[Idle]
  
  > Dictation Trigger Pressed
       
       > [Listening] (_is_dictating = True, mic overlay shown)
            
            > Speech Detected
                > [Recognizing] (audio sent to API)
                     
                     > Success: Text inserted
                         > [Listening] (continue listening)
                     
                     > Error: No speech recognized
                          > [Listening] (try again)
            
            > Dictation Trigger Pressed Again
                 > [Idle] (_is_dictating = False, mic overlay hidden)
```

---


## Error Handling & Recovery

### API Failure Handling

**Problem**: Gemini API may fail (network issues, rate limits, invalid key)

**Strategy**: Graceful degradation with user feedback

```python
# In gemini_corrector.py
def _generate_single_candidate(self, text: str, idx: int) -> Dict:
    try:
        # Get settings for this candidate
        settings = self._candidate_settings[idx]
        
        # Build prompt
        prompt = self._build_prompt(text, settings['tone'])
        
        # Call API with timeout
        response = self.model.generate_content(
            prompt,
            generation_config={
                'temperature': settings['temperature'],
                'max_output_tokens': 2048
            }
        )
        
        # Extract text
        corrected_text = response.text.strip()
        
        return {
            'text': corrected_text,
            'temperature': settings['temperature'],
            'tone': settings['tone']
        }
    
    except Exception as e:
        # Log error
        print(f"API error for candidate {idx}: {e}")
        
        # Return fallback candidate
        return {
            'text': f'[Error generating candidate {idx+1}: {str(e)[:50]}]',
            'temperature': settings.get('temperature', 0.5),
            'tone': settings.get('tone', 'original')
        }
```

**Result**: User sees error message in candidate list, can still use other candidates

---

### Clipboard Operation Failures

**Problem**: Clipboard may be locked by another app (e.g., clipboard manager)

**Strategy**: Retry with exponential backoff, then fallback to pywinauto

```python
# In text_buffer.py
def replace_selected_text(self, new_text: str) -> bool:
    # Try clipboard method (fast, reliable)
    for attempt in range(3):
        try:
            # Save current clipboard
            original_clipboard = pyperclip.paste()
            
            # Set new text
            pyperclip.copy(new_text)
            
            # Paste
            keyboard.send('ctrl+v')
            
            # Wait for paste
            time.sleep(0.05)
            
            # Restore clipboard
            pyperclip.copy(original_clipboard)
            
            return True
        
        except Exception as e:
            if attempt < 2:
                # Retry with exponential backoff
                time.sleep(0.1 * (2 ** attempt))  # 0.1s, 0.2s
            else:
                print(f"Clipboard method failed: {e}")
    
    # Fallback: pywinauto method (slower, but works when clipboard locked)
    try:
        window = pywinauto.Desktop(backend='uia').windows()[0]
        edit_control = window.child_window(control_type='Edit')
        edit_control.set_text(new_text)
        return True
    
    except Exception as e:
        print(f"Pywinauto method failed: {e}")
        return False
```

**Fallback Chain**:
1. Clipboard (3 attempts with backoff)
2. Pywinauto UI automation
3. Fail gracefully (log error, notify user)

---

### Voice Recognition Failures

**Problem**: Speech recognition may fail (no speech, ambient noise, network issues)

**Strategy**: Multi-engine fallback chain with error recovery

```python
# In dictation_manager.py
def _recognize_speech(self, audio: sr.AudioData) -> Optional[str]:
    # Engine 1: Google (requires internet)
    try:
        text = self.recognizer.recognize_google(audio)
        print(f"Google recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Google could not understand audio")
    except sr.RequestError as e:
        print(f"Google API error: {e}")
    
    # Engine 2: Whisper (offline, slower)
    try:
        text = self.recognizer.recognize_whisper(audio)
        print(f"Whisper recognized: {text}")
        return text
    except Exception as e:
        print(f"Whisper error: {e}")
    
    # Engine 3: Sphinx (offline, less accurate)
    try:
        text = self.recognizer.recognize_sphinx(audio)
        print(f"Sphinx recognized: {text}")
        return text
    except Exception as e:
        print(f"Sphinx error: {e}")
    
    # All engines failed
    return None
```

**User Feedback**:
- Success: Text inserted immediately
- Failure: Mic overlay remains visible, user can speak again
- All engines fail: Continue listening (user tries again)

---

### Configuration File Corruption

**Problem**: config.json may be manually edited incorrectly or corrupted

**Strategy**: Validate on load, regenerate if invalid

```python
# In config_manager.py
def load(self) -> Dict[str, Any]:
    try:
        if not self._config_path.exists():
            # First run: Create default config
            self._config = DEFAULT_CONFIG.copy()
            self.save()
            return self._config
        
        with open(self._config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        
        # Validate schema
        if not self._is_valid_config(loaded_config):
            print("Config validation failed, regenerating...")
            self._config = DEFAULT_CONFIG.copy()
            self.save()
            return self._config
        
        self._config = loaded_config
        return self._config
    
    except Exception as e:
        print(f"Config load error: {e}, using defaults")
        self._config = DEFAULT_CONFIG.copy()
        return self._config

def _is_valid_config(self, config: Dict) -> bool:
    \"\"\"Validate config schema.\"\"\"
    required_keys = ['api_key', 'model_name', 'trigger_key', 'version_count']
    
    # Check all required keys present
    if not all(key in config for key in required_keys):
        return False
    
    # Validate types
    if not isinstance(config['version_count'], int):
        return False
    if not isinstance(config['trigger_key'], str):
        return False
    
    # Validate ranges
    if not (1 <= config['version_count'] <= 5):
        return False
    
    return True
```

**Result**: App never crashes due to bad config, always falls back to working defaults

---

### Database Corruption

**Problem**: history.db may be corrupted or locked

**Strategy**: Recreate database if operations fail

```python
# In history_manager.py
def __init__(self):
    try:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False  # Allow multi-threaded access
        )
        self._ensure_schema()
    except Exception as e:
        print(f"Database init error: {e}")
        # Try recreating database
        try:
            if self._db_path.exists():
                self._db_path.unlink()  # Delete corrupted file
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._ensure_schema()
        except Exception as e2:
            print(f"Database recreation failed: {e2}")
            # Fallback: In-memory database (lost on exit)
            self._conn = sqlite3.connect(':memory:', check_same_thread=False)
            self._ensure_schema()

def add_correction(self, original: str, corrected: str, tone: str, temperature: float):
    try:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO corrections (timestamp, window_id, original, corrected, tone, temperature) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), self._get_window_id(), original, corrected, tone, temperature)
        )
        self._conn.commit()
    except Exception as e:
        print(f"Failed to log correction: {e}")
        # Don't crash app if logging fails (non-critical feature)
```

**Fallback Levels**:
1. Normal database on disk
2. Recreated database (if corrupted)
3. In-memory database (if disk access fails)
4. No logging (if all database operations fail)

---

### Window Handle Errors

**Problem**: Window may close while correction is in progress

**Strategy**: Validate window before operations, skip if invalid

```python
# In keystroke_buffer.py
def get_recent_text(self, window_id: int, max_chars: int = 500) -> str:
    try:
        if window_id not in self._buffers:
            return ""  # No buffer for this window
        
        # Check if window still exists
        if not self._is_valid_window(window_id):
            # Window closed, clean up buffer
            del self._buffers[window_id]
            if window_id in self._last_access:
                del self._last_access[window_id]
            return ""
        
        # Get recent keystrokes
        buffer = self._buffers[window_id]
        recent = list(buffer)[-max_chars:]
        return ''.join(recent)
    
    except Exception as e:
        print(f"Error getting text for window {window_id}: {e}")
        return ""

def _is_valid_window(self, window_id: int) -> bool:
    \"\"\"Check if window handle is still valid.\"\"\"
    try:
        import win32gui
        return win32gui.IsWindow(window_id)
    except:
        return False
```

**Result**: No crashes when window closes during operation

---

### Keyboard Hook Failures

**Problem**: Keyboard hook may fail to install (permissions, conflicts)

**Strategy**: Retry with delay, show error if persistent

```python
# In main.py
def main():
    try:
        # Initialize service
        service = AutoCorrectService(...)
        
        # Start keyboard hook with retry
        for attempt in range(3):
            try:
                service.start()
                print("Keyboard hook installed successfully")
                break
            except Exception as e:
                if attempt < 2:
                    print(f"Hook install failed (attempt {attempt+1}), retrying...")
                    time.sleep(1)
                else:
                    print(f"Failed to install keyboard hook after 3 attempts: {e}")
                    messagebox.showerror(
                        "CorreX Error",
                        "Failed to start keyboard monitoring. Please run as administrator or check for conflicting software."
                    )
                    return
        
        # Start GUI
        launch_app(service, config, ...)
    
    except Exception as e:
        print(f"Fatal error: {e}")
        messagebox.showerror("CorreX Error", f"Application failed to start: {e}")
```

---

### User Feedback for Errors

**Visible Errors (require immediate attention)**:
- API key invalid: Show error in GUI status label + messagebox
- Keyboard hook failed: Messagebox on startup
- Config save failed: Messagebox in GUI

**Silent Errors (non-critical, logged only)**:
- History logging failed: Print to console
- Single candidate generation failed: Show error in candidate slot
- Window handle invalid: Skip operation silently

**Error Display Pattern**:
```python
# In app_gui.py
def save_settings():
    try:
        # Save operations...
        messagebox.showinfo("Success", "Settings saved!")
    except Exception as e:
        # Critical error: Show to user
        messagebox.showerror("Error", f"Failed to save: {e}")
        print(f"Save error details: {traceback.format_exc()}")  # Full trace to console
```

---


## Testing & Debugging

### Manual Testing Checklist

**Initial Setup**:
- [ ] Fresh install: Delete `~/.autocorrect_ai` directory
- [ ] First run creates default config.json
- [ ] GUI opens with default settings
- [ ] API key field shows placeholder
- [ ] Tray icon appears in system tray

**Configuration**:
- [ ] Enter valid API key, click Save
- [ ] Change trigger key via capture popup
- [ ] Adjust version count (1-5), verify candidate rows show/hide
- [ ] Modify temperature sliders, values update correctly
- [ ] Change tone dropdowns, descriptions update
- [ ] Close and reopen GUI, settings persist

**Text Correction**:
- [ ] Type text in Notepad
- [ ] Press trigger key (Ctrl+Shift+A by default)
- [ ] Loading overlay appears (semi-transparent black screen)
- [ ] Text replaced with first candidate after 1-3 seconds
- [ ] Press Tab, text cycles to next candidate
- [ ] Press Shift+Tab, cycles backwards
- [ ] Press any other key, exits navigation mode
- [ ] Test with different apps: VS Code, Word, Chrome, Discord

**Voice Dictation**:
- [ ] Press dictation trigger (Ctrl+Shift+D)
- [ ] Mic overlay appears (red pulsing circle in corner)
- [ ] Speak into microphone
- [ ] Text appears at cursor position
- [ ] Press dictation trigger again to stop
- [ ] Mic overlay disappears
- [ ] Test in different apps

**Edge Cases**:
- [ ] Trigger with no text typed (should do nothing)
- [ ] Trigger with cursor in middle of paragraph
- [ ] Trigger while another app is active (should work)
- [ ] Close active window during correction (should handle gracefully)
- [ ] Invalid API key (should show error in candidate slot)
- [ ] Network disconnect during correction (should timeout and show error)
- [ ] Clipboard locked by another app (should fallback to pywinauto)

---

### Debugging Techniques

**1. Console Output**

Run from terminal to see real-time logs:
```bash
cd correX
python main.py
```

**Key Log Messages**:
- `Keyboard hook installed successfully` - Hook started
- `Trigger detected: ctrl+shift+a` - Trigger key pressed
- `Generating N candidates...` - API call started
- `Google recognized: [text]` - Voice recognition success
- `API error for candidate N: [error]` - API failure
- `Clipboard method failed: [error]` - Clipboard locked

**2. Config Inspection**

Check current configuration:
```bash
cat ~/.autocorrect_ai/config.json
```

Validate JSON syntax:
```bash
python -m json.tool ~/.autocorrect_ai/config.json
```

**3. Database Inspection**

Query correction history:
```bash
sqlite3 ~/.autocorrect_ai/history.db
SELECT * FROM corrections ORDER BY timestamp DESC LIMIT 10;
.quit
```

**4. Thread Debugging**

Add thread names for easier tracking:
```python
# In autocorrect_service.py
def start(self):
    import threading
    threading.current_thread().name = "KeyboardHook"
    # ... rest of code
```

Enable thread debugging:
```python
import sys
import threading

def thread_dump():
    for thread in threading.enumerate():
        print(f"Thread {thread.name}: {thread.is_alive()}")

# Call periodically or on error
```

**5. API Call Tracing**

Log API requests and responses:
```python
# In gemini_corrector.py
def _generate_single_candidate(self, text: str, idx: int) -> Dict:
    print(f"[API] Candidate {idx}: temp={settings['temperature']}, tone={settings['tone']}")
    print(f"[API] Prompt: {prompt[:100]}...")
    
    response = self.model.generate_content(...)
    
    print(f"[API] Response length: {len(response.text)} chars")
    print(f"[API] Response preview: {response.text[:100]}...")
```

---

## Build & Deployment

### Development Setup

**1. Clone Repository**:
```bash
git clone <repository-url>
cd CorreX
```

**2. Install Dependencies**:
```bash
cd correX
pip install -r requirements.txt
```

**3. Run from Source**:
```bash
python main.py
```

---

### Creating Windows Executable

**1. Install PyInstaller**:
```bash
pip install pyinstaller
```

**2. Build with PyInstaller**:
```bash
cd correX
pyinstaller --onefile --windowed --icon=assets/icons/CorreX_logo.ico --add-data "assets;assets" --add-data "QUICK_START.md;." --name CorreX main.py
```

**Build Options Explained**:
- `--onefile`: Package into single .exe (easier distribution)
- `--windowed`: No console window (GUI only)
- `--icon=...`: Set executable icon
- `--add-data "assets;assets"`: Include assets folder in bundle
- `--add-data "QUICK_START.md;."`: Include documentation
- `--name CorreX`: Output filename

**3. Output**:
- Executable: `dist/CorreX.exe`
- Spec file: `CorreX.spec` (for rebuilding)

**4. Test Executable**:
```bash
cd dist
./CorreX.exe
```

---

### Creating Installer (Optional)

**Using Inno Setup**:

1. Download and install Inno Setup
2. Create `installer.iss` script:

```iss
[Setup]
AppName=CorreX
AppVersion=1.0
DefaultDirName={pf}\CorreX
DefaultGroupName=CorreX
OutputBaseFilename=CorreX_Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\CorreX.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CorreX"; Filename: "{app}\CorreX.exe"
Name: "{group}\Uninstall CorreX"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\CorreX.exe"; Description: "Launch CorreX"; Flags: postinstall nowait skipifsilent
```

3. Compile with Inno Setup Compiler
4. Output: `Output/CorreX_Setup.exe`

---

### Distribution

**Package Contents**:
- `CorreX.exe` - Main executable
- `README.md` - User guide
- `QUICK_START.md` - Quick reference (embedded in exe)
- `LICENSE` - Software license (if applicable)

**Minimum Requirements**:
- **OS**: Windows 10 or later (64-bit)
- **RAM**: 2 GB minimum, 4 GB recommended
- **Disk**: 100 MB free space
- **Network**: Internet connection for Google Gemini API and voice recognition
- **Audio**: Microphone for voice dictation (optional)

**Installation Steps**:
1. Download `CorreX.exe` or run installer
2. First launch: Enter Google Gemini API key in GUI
3. (Optional) Customize keyboard shortcuts
4. Start using!

---

## Known Issues & Limitations

### Application Compatibility

**Fully Compatible**:
- Notepad, Notepad++
- Microsoft Word, Excel
- VS Code, Sublime Text
- Chrome, Firefox, Edge (text fields)
- Discord, Slack (chat boxes)
- File Explorer (rename fields)

**Partially Compatible**:
- Some Electron apps (clipboard method may fail, use pywinauto fallback)
- Protected fields (e.g., password inputs - intentionally blocked by Windows)
- Games with anti-cheat (keyboard hooks may be blocked)

**Incompatible**:
- Command Prompt / PowerShell (special terminal handling)
- Virtual machines (keyboard hooks don't cross VM boundary)
- Remote desktop clients (input redirection issues)

---

### Performance Considerations

**API Latency**:
- Gemini API calls: 1-3 seconds per candidate
- Parallel generation: 5 candidates in ~1-3 seconds (not 5-15 seconds)
- Network-dependent: Slower on poor connections

**Memory Usage**:
- Base: ~50 MB (Python interpreter + libraries)
- Per window buffer: ~5 KB (5000 keystrokes)
- Peak: ~200 MB during parallel API calls

**CPU Usage**:
- Idle: < 1% (keyboard hook is very efficient)
- During correction: 10-30% (API calls + text replacement)
- Voice dictation: 5-15% (audio processing)

---

### Security & Privacy

**Local Data Storage**:
- Config: `~/.autocorrect_ai/config.json` (includes API key in plaintext)
- History: `~/.autocorrect_ai/history.db` (original + corrected text)
- No data sent to third parties except Google Gemini API

**API Key Security**:
- Stored in plaintext config file (not encrypted)
- **Recommendation**: Use API key with usage limits/quotas
- **Warning**: Anyone with filesystem access can read API key

**Keystroke Logging**:
- Keystrokes stored in memory only (not written to disk)
- Per-window isolation (one app can't see another's buffer)
- Cleared when window closes or max buffer size reached

**Privacy Considerations**:
- All typed text sent to Google Gemini API for correction
- Correction history stored locally for 1 hour (auto-deleted)
- Voice audio sent to Google/Whisper/Sphinx for transcription
- No telemetry or analytics collected by CorreX

---

### Known Bugs

**1. NumLock Alt Key Confusion** (FIXED):
- **Issue**: NumLock state (0x20000) was detected as Alt modifier
- **Impact**: Triggers captured incorrectly when NumLock on
- **Fix**: Only check 0x0008 bit for Alt, ignore NumLock bit

**2. Clipboard Restore Timing**:
- **Issue**: Very fast clipboard operations may restore before paste completes
- **Impact**: Original text may be pasted instead of correction
- **Workaround**: 50ms delay between paste and restore (works in 99% of cases)
- **Future**: Detect paste completion before restoring

**3. Window Focus During Correction**:
- **Issue**: If user switches windows during correction, text may be pasted in wrong app
- **Impact**: Rare, requires precise timing
- **Workaround**: Loading overlay prevents most accidental window switches
- **Future**: Lock window focus during correction

---

### Future Enhancements

**Potential Features**:
- Offline AI mode (local model instead of API)
- Customizable prompt templates per tone
- Context-aware correction (detect code vs prose)
- Multi-language support
- History search and replay
- Encrypted config file
- Auto-update mechanism
- Plugin system for custom correctors

---

## Logging System

**File**: `correX/logger.py` (180 lines)  
**Purpose**: Centralized logging infrastructure replacing scattered print statements  
**Dependencies**: `logging`, `pathlib`

### Overview

The logging system provides a professional, configurable logging infrastructure for the entire application. It replaces 100+ scattered `print()` statements with a centralized, thread-safe logging mechanism.

### Architecture

```python
CorreXLogger (Singleton Pattern)
    │
    ├─ setup() → Configure global logging
    ├─ get_logger(name) → Get module-specific logger
    └─ set_level(level) → Change logging level dynamically

Module Loggers
    │
    ├─ logger.info()    → Informational messages
    ├─ logger.warning() → Warning messages
    ├─ logger.error()   → Error messages with optional traceback
    └─ logger.debug()   → Debug information
```

### Key Features

**1. Centralized Configuration**
```python
from correX.logger import CorreXLogger
import logging

CorreXLogger.setup(
    level=logging.DEBUG,
    log_file=Path("correx.log"),
    console=True,
    max_bytes=10*1024*1024,  # 10MB
    backup_count=3
)
```

**2. Module-Specific Loggers**
```python
from correX.logger import get_logger

logger = get_logger(__name__)
logger.info("Service started")
logger.error("API call failed", exc_info=True)
```

**3. Rotating File Handler**
- Automatic log rotation at 10MB
- Keeps 3 backup files
- UTF-8 encoding
- Thread-safe

**4. Command-Line Integration**
```bash
correx --verbose           # DEBUG level
correx --quiet             # ERROR level only
correx --log-file app.log  # Write to file
```

### Implementation Details

**Class Structure**:
```python
class CorreXLogger:
    _loggers = {}                 # Cache of module loggers
    _default_level = logging.INFO
    _log_file = None
    _initialized = False
    
    @classmethod
    def setup(cls, level, log_file, console, max_bytes, backup_count):
        # Configure root logger
        # Add console handler
        # Add rotating file handler
        
    @classmethod
    def get_logger(cls, name):
        # Return cached or create new logger
        
    @classmethod
    def set_level(cls, level):
        # Update all loggers dynamically
```

**Log Format**:
```
2025-11-01 10:30:45 - CorreX.autocorrect_service - INFO - Service started
2025-11-01 10:30:46 - CorreX.gemini_corrector - ERROR - API call failed
```

**Legacy Compatibility Functions**:
```python
# For quick migration from print statements
log_info("Message", module="main")
log_warning("Warning", module="service")
log_error("Error", module="api", exc_info=True)
log_debug("Debug info", module="buffer")
```

### Usage Patterns

**Basic Usage**:
```python
from correX.logger import get_logger

logger = get_logger(__name__)

# Different log levels
logger.debug(f"Buffer contents: {text[:50]}")
logger.info("Correction triggered")
logger.warning("API rate limit approaching")
logger.error("Failed to replace text", exc_info=True)
```

**Error Logging with Context**:
```python
try:
    result = api_call()
except Exception as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    # Stack trace automatically included
```

**Dynamic Level Changes**:
```python
# Enable debug mode at runtime
CorreXLogger.set_level(logging.DEBUG)

# Return to normal
CorreXLogger.set_level(logging.INFO)
```

### Integration Points

**main.py**:
```python
# Parse command-line arguments
log_level = logging.ERROR if args.quiet else \
            (logging.DEBUG if args.verbose else logging.INFO)
log_file = Path(args.log_file) if args.log_file else None

# Setup logging
CorreXLogger.setup(
    level=log_level,
    log_file=log_file,
    console=not args.quiet
)
```

**Migration from print statements**:
```python
# Before
print("[INFO] Service started")
print(f"[ERROR] Failed to load config: {e}")
print("[DEBUG] Buffer contents: ...")

# After
logger.info("Service started")
logger.error(f"Failed to load config: {e}")
logger.debug(f"Buffer contents: ...")
```

### Benefits

1. **Structured Logging**: Consistent format with timestamps
2. **Log Levels**: Filter messages by severity
3. **File Rotation**: Automatic log file management
4. **Thread Safety**: Safe for concurrent logging
5. **Performance**: Minimal overhead compared to print()
6. **Debugging**: Stack traces with `exc_info=True`
7. **Production Ready**: Can disable debug logs in production

### Design Decisions

**Why Singleton Pattern?**
- Ensures consistent configuration across modules
- Prevents duplicate handler setup
- Allows global level changes

**Why Module-Specific Loggers?**
- Easy to filter logs by component
- Clear message origin
- Independent level control possible

**Why Rotating File Handler?**
- Prevents unlimited disk usage
- Keeps recent history
- No manual cleanup needed

---

## Testing Infrastructure

**Location**: `tests/` directory  
**Framework**: pytest  
**Coverage**: 52 unit tests across 3 modules  
**Configuration**: `pytest.ini`, `pyproject.toml`

### Test Structure

```
tests/
├── __init__.py                    # Test package marker
├── README.md                      # Testing documentation
├── test_keystroke_buffer.py       # 15 test cases
├── test_config_manager.py         # 20 test cases
└── test_history_manager.py        # 17 test cases
```

### Test Modules

#### test_keystroke_buffer.py (15 tests)

**Purpose**: Verify keystroke buffer functionality

**Test Coverage**:
- Basic keystroke tracking
- Per-window isolation
- Backspace handling
- Buffer overflow (LRU eviction)
- Clear operations
- Special characters (unicode, emojis)
- Edge cases (empty buffer, non-existent window)

**Example Tests**:
```python
def test_buffer_overflow(self):
    """Test that buffer respects max_chars limit."""
    small_buffer = KeystrokeBuffer(max_chars=10)
    for i in range(20):
        small_buffer.add_keystroke(12345, 'a')
    
    text = small_buffer.get_text(12345)
    self.assertEqual(len(text), 10)

def test_per_window_isolation(self):
    """Test that different windows have separate buffers."""
    buffer.add_keystroke(12345, 'a')
    buffer.add_keystroke(67890, 'x')
    
    self.assertEqual(buffer.get_text(12345), 'a')
    self.assertEqual(buffer.get_text(67890), 'x')
```

#### test_config_manager.py (20 tests)

**Purpose**: Verify configuration persistence and validation

**Test Coverage**:
- Config load/save operations
- Default value handling
- API key management
- Trigger key configuration
- Candidate settings
- Startup/notification settings
- Invalid JSON handling
- Config validation
- Reset to defaults

**Example Tests**:
```python
def test_save_and_load_config(self):
    """Test saving and loading configuration."""
    config.set_api_key("test_key_12345")
    config.save_config()
    
    new_config = ConfigManager()
    new_config.config_file = self.config_file
    new_config.load_config()
    
    self.assertEqual(new_config.get_api_key(), "test_key_12345")

def test_num_versions_validation(self):
    """Test that num_versions is clamped to valid range."""
    config.set_num_versions(0)
    self.assertGreaterEqual(config.get_num_versions(), 1)
    
    config.set_num_versions(10)
    self.assertLessEqual(config.get_num_versions(), 5)
```

#### test_history_manager.py (17 tests)

**Purpose**: Verify history tracking and cleanup

**Test Coverage**:
- Save/retrieve corrections
- History limits
- Old entry cleanup
- Statistics calculation
- Search functionality
- Delete operations
- Special characters (unicode, SQL injection)
- Long text handling
- Concurrent access

**Example Tests**:
```python
def test_cleanup_old_entries(self):
    """Test automatic cleanup of old entries."""
    # Insert old entry (2 hours ago)
    old_timestamp = (datetime.now() - timedelta(hours=2)).isoformat()
    cursor.execute(
        "INSERT INTO history (...) VALUES (..., ?)",
        (old_timestamp,)
    )
    
    # Add recent entry
    history.save_correction("new", "corrected", "original")
    
    # Cleanup (1 hour threshold)
    history.cleanup_old_entries(hours=1)
    
    # Only recent entry should remain
    result = history.get_recent_history(limit=10)
    self.assertEqual(len(result), 1)
```

### Running Tests

**Basic Execution**:
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_keystroke_buffer.py

# Run specific test
pytest tests/test_config_manager.py::TestConfigManager::test_save_and_load
```

**Coverage Reports**:
```bash
# Run with coverage
pytest --cov=correX --cov-report=html

# View HTML report
start htmlcov/index.html

# Terminal report
pytest --cov=correX --cov-report=term-missing
```

**Test Markers**:
```bash
# Run only unit tests
pytest -m unit

# Exclude slow tests
pytest -m "not slow"

# Run integration tests
pytest -m integration
```

**Using Test Runner**:
```bash
# Convenient wrapper script
python run_tests.py

# With custom args
python run_tests.py -v -s --pdb
```

### Test Configuration

**pytest.ini**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

addopts =
    -v
    --strict-markers
    --cov=correX
    --cov-report=term-missing
    --cov-report=html

markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
```

**pyproject.toml**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--cov=correX"]

[tool.coverage.run]
source = ["correX"]
omit = ["*/tests/*"]
```

### Test Design Patterns

**Fixture Setup/Teardown**:
```python
class TestConfigManager(unittest.TestCase):
    def setUp(self):
        """Create temporary config file."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.json"
        self.config = ConfigManager()
    
    def tearDown(self):
        """Cleanup temporary files."""
        if self.config_file.exists():
            self.config_file.unlink()
```

**Isolation**:
- Each test uses temporary directories
- No shared state between tests
- Automatic cleanup after each test

**Mocking** (when needed):
```python
from unittest.mock import patch, MagicMock

with patch('correX.config_manager.Path.home') as mock_home:
    mock_home.return_value = Path(self.temp_dir)
    config = ConfigManager()
```

### Coverage Goals

**Target Coverage**:
- **Core Logic**: 80%+ (keystroke_buffer, config_manager)
- **Infrastructure**: 70%+ (history_manager)
- **GUI**: Not tested (requires Windows environment)
- **Overall**: 75%+

**Current Coverage**:
```
Name                    Stmts   Miss  Cover
-------------------------------------------
keystroke_buffer.py       150     15    90%
config_manager.py         180     20    89%
history_manager.py        120     18    85%
-------------------------------------------
TOTAL                     450     53    88%
```

### CI/CD Integration

Tests are designed for CI/CD:
- No GUI dependencies
- Fast execution (<5 seconds)
- Isolated fixtures
- Exit codes (0 = pass, 1 = fail)

**GitHub Actions Example**:
```yaml
- name: Run tests
  run: |
    pytest --cov=correX --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

---

## Configuration Validation

**Implementation**: `correX/config_manager.py` (+60 lines)  
**Purpose**: Schema-based validation for configuration values  
**Added**: v1.0.0

### Validation Schema

```python
CONFIG_SCHEMA = {
    "api_key": (str, lambda x: True, "Must be a string"),
    "model_name": (str, lambda x: len(x) > 0, "Must be non-empty"),
    "trigger_key": (str, lambda x: len(x) > 0, "Must be non-empty"),
    "versions_per_correction": (int, lambda x: 1 <= x <= 5, "Must be 1-5"),
    "paragraph_enabled": (bool, lambda x: True, "Must be boolean"),
    "start_on_boot": (bool, lambda x: True, "Must be boolean"),
    # ... more fields
}
```

**Schema Format**: `(expected_type, validator_function, error_message)`

### Validation Functions

**validate_config_value()**:
```python
def validate_config_value(key: str, value: Any) -> Tuple[bool, str]:
    """Validate a single configuration value."""
    if key not in CONFIG_SCHEMA:
        return True, ""  # Unknown keys allowed (forward compatibility)
    
    expected_type, validator, error_msg = CONFIG_SCHEMA[key]
    
    # Type check
    if not isinstance(value, expected_type):
        return False, f"{key}: {error_msg} (got {type(value).__name__})"
    
    # Value validation
    if not validator(value):
        return False, f"{key}: {error_msg} (value: {value})"
    
    return True, ""
```

**validate_config()**:
```python
def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate entire configuration dictionary."""
    errors = []
    
    for key, value in config.items():
        is_valid, error_msg = validate_config_value(key, value)
        if not is_valid:
            errors.append(error_msg)
    
    return len(errors) == 0, errors
```

### Integration with ConfigManager

**Save Method** (enhanced):
```python
def save(self) -> bool:
    """Save configuration with validation."""
    # Validate before saving
    is_valid, errors = validate_config(self.config)
    if not is_valid:
        logger.warning(f"Config validation errors: {'; '.join(errors)}")
        logger.warning("Saving anyway, but some values may be invalid")
    
    # Proceed with save
    with open(self.config_file, 'w') as f:
        json.dump(self.config, f, indent=2)
```

### Validation Rules

**Type Validation**:
- `api_key`: Must be string
- `trigger_key`: Must be string
- `versions_per_correction`: Must be int
- `temperature`: Must be float
- `start_on_boot`: Must be bool

**Range Validation**:
- `versions_per_correction`: 1 ≤ value ≤ 5
- `temperature`: 0.0 ≤ value ≤ 2.0
- `max_buffer_chars`: value > 0

**String Validation**:
- Non-empty strings for trigger keys
- Non-empty model names

### Error Handling

**Invalid Type**:
```python
# Config: {"versions_per_correction": "3"}  # String instead of int
# Error: "versions_per_correction: Must be between 1 and 5 (got str)"
```

**Invalid Range**:
```python
# Config: {"versions_per_correction": 10}  # Out of range
# Error: "versions_per_correction: Must be between 1 and 5 (value: 10)"
```

**Multiple Errors**:
```python
errors = [
    "versions_per_correction: Must be between 1 and 5 (value: 10)",
    "temperature: Must be between 0.0 and 2.0 (value: 3.5)",
]
# All errors reported together
```

### Benefits

1. **Early Error Detection**: Catch invalid values before they cause runtime errors
2. **User Feedback**: Clear error messages for debugging
3. **Data Integrity**: Ensures config file remains valid
4. **Forward Compatibility**: Unknown keys are allowed (for future versions)
5. **Type Safety**: Prevents type mismatches

### Usage Example

```python
from correX.config_manager import validate_config

config = {
    "api_key": "sk-test",
    "versions_per_correction": 3,
    "temperature": 0.7,
}

is_valid, errors = validate_config(config)
if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
```

---

## Modern Python Packaging

**Files**: `setup.py`, `pyproject.toml`, `MANIFEST.in`  
**Purpose**: Professional package distribution  
**Compliance**: PEP 518, PEP 517, PEP 621

### Package Structure

```
CorreX/
├── setup.py              # Setuptools configuration (backward compat)
├── pyproject.toml        # Modern packaging (PEP 518/517)
├── MANIFEST.in           # Package data inclusion rules
├── LICENSE               # MIT License
├── README.md             # Package description
├── CHANGELOG.md          # Version history
└── correX/               # Package source
    ├── __init__.py       # Version metadata
    ├── requirements.txt  # Dependencies
    └── ...
```

### setup.py

**Purpose**: Setuptools-based packaging (backward compatible)

```python
setup(
    name="correX",
    version="1.0.0",
    author="CorreX Project",
    description="AI-Powered Text Correction & Voice Dictation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vikas7516/CorreX",
    packages=find_packages(),
    classifiers=[...],
    python_requires=">=3.8",
    install_requires=[...],
    entry_points={
        "console_scripts": [
            "correx=correX.main:main",
        ],
    },
)
```

**Key Features**:
- Automatic package discovery
- Entry point creation (`correx` command)
- Dependency management
- PyPI classifiers for discoverability

### pyproject.toml

**Purpose**: Modern Python packaging (PEP 518)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "correX"
version = "1.0.0"
description = "AI-Powered Text Correction & Voice Dictation"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "google-generativeai>=0.3.0",
    "keyboard>=0.13.5",
    # ... more dependencies
]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "black>=23.0.0", ...]
test = ["pytest>=7.0.0", "pytest-cov>=4.0.0", ...]

[project.scripts]
correx = "correX.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--cov=correX"]

[tool.black]
line-length = 120
target-version = ["py38", "py39", "py310"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
ignore_missing_imports = true
```

**Benefits**:
- Single source of truth for project metadata
- Tool configuration (pytest, black, mypy) in one place
- Modern standard (PEP 517/518/621)
- Better dependency resolution

### MANIFEST.in

**Purpose**: Specify non-code files to include in distribution

```
# Documentation
include README.md
include LICENSE
include CHANGELOG.md
include DEVNOTES.md

# Requirements
include correX/requirements.txt

# Assets
recursive-include assets *
recursive-include correX/assets *

# Exclude unnecessary files
global-exclude __pycache__
global-exclude *.pyc
prune .git
prune tests
```

### Installation Methods

**Development Mode** (editable install):
```bash
pip install -e .          # Basic
pip install -e ".[dev]"   # With dev tools
pip install -e ".[test]"  # With test deps
```

**Normal Installation**:
```bash
pip install .
```

**From PyPI** (future):
```bash
pip install correx
```

**Entry Point**:
```bash
# After installation, run from anywhere:
correx
correx --verbose --log-file app.log
```

### Building Distributions

**Source Distribution**:
```bash
python -m build --sdist
# Creates: dist/correX-1.0.0.tar.gz
```

**Wheel Distribution**:
```bash
python -m build --wheel
# Creates: dist/correX-1.0.0-py3-none-any.whl
```

**Both**:
```bash
python -m build
# Creates both sdist and wheel
```

### Publishing to PyPI

**Test PyPI** (for testing):
```bash
python -m twine upload --repository testpypi dist/*
```

**Production PyPI**:
```bash
python -m twine upload dist/*
```

### Version Management

**Single Source**: `correX/__init__.py`
```python
__version__ = "1.0.0"
```

**Access from code**:
```python
import correX
print(correX.__version__)  # "1.0.0"
```

**Access from setup**:
```python
# setup.py reads from __init__.py
# No duplication needed
```

### Optional Dependencies

**Development Tools**:
```bash
pip install -e ".[dev]"
# Installs: pytest, black, flake8, mypy
```

**Test-Only**:
```bash
pip install -e ".[test]"
# Installs: pytest, pytest-cov, pytest-mock
```

**Usage in CI/CD**:
```yaml
- name: Install test dependencies
  run: pip install -e ".[test]"
```

### Package Metadata

**Classifiers** (for PyPI):
```python
classifiers=[
    "Development Status :: 4 - Beta",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]
```

**Project URLs**:
```toml
[project.urls]
Homepage = "https://github.com/vikas7516/CorreX"
Documentation = "https://github.com/vikas7516/CorreX/blob/main/DEVNOTES.md"
Repository = "https://github.com/vikas7516/CorreX"
"Bug Reports" = "https://github.com/vikas7516/CorreX/issues"
Changelog = "https://github.com/.../CHANGELOG.md"
```

### Benefits of Modern Packaging

1. **Professional**: Industry-standard packaging
2. **Discoverable**: PyPI classifiers and keywords
3. **Installable**: `pip install` support
4. **Entry Points**: `correx` command available system-wide
5. **Dependencies**: Automatic dependency resolution
6. **Development**: Easy setup for contributors
7. **CI/CD**: Standardized testing and building
8. **Distribution**: Multiple installation methods

---

## Open Source Infrastructure

CorreX includes professional open-source infrastructure with GitHub templates, policies, and automation to enable collaboration.

### Overview

**Purpose**: Provide a complete open-source ecosystem that enables community contributions while maintaining project quality and security.

**Components Added**:
1. README badges for visibility
2. EditorConfig for consistent code style
3. GitHub issue templates for bug reports and feature requests
4. Pull request template with quality checklists
5. Code of Conduct (Contributor Covenant v2.1)
6. Security Policy with vulnerability reporting
7. CI/CD workflow for automated testing
8. Roadmap for project direction transparency

### README Badges

**File**: `README.md` (lines 3-8)

**Implementation**:
```markdown
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![Tests](https://img.shields.io/badge/tests-52%20passing-success.svg)
![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)
```

**Purpose**: Provide at-a-glance project status for visitors.

**Badges Included**:
- **Version**: Current release (1.0.0)
- **License**: MIT for open collaboration
- **Python**: Minimum version requirement (3.8+)
- **Platform**: Windows-specific
- **Tests**: Number of passing tests (52)
- **Coverage**: Test coverage percentage (88%)

**Future Enhancement**: Replace static badges with dynamic shields.io badges that auto-update from GitHub Actions and Codecov.

### EditorConfig

**File**: `.editorconfig`

**Purpose**: Ensure consistent coding style across different editors and contributors.

**Configuration**:
```ini
# All files
[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

# Python files
[*.py]
indent_style = space
indent_size = 4
max_line_length = 100

# Markdown files
[*.md]
trim_trailing_whitespace = false
max_line_length = off
```

**Supported Editors**: VS Code, PyCharm, Sublime Text, Atom, Vim, and 40+ others.

**Benefits**:
- Prevents indentation wars (spaces vs tabs)
- Ensures consistent line endings across platforms
- Automatically enforced by most modern editors
- Reduces diff noise from whitespace changes

### GitHub Issue Templates

**Location**: `.github/ISSUE_TEMPLATE/`

#### Bug Report Template

**File**: `bug_report.md`

**Sections**:
1. **Bug Description**: Clear problem statement
2. **Steps to Reproduce**: Numbered reproduction steps
3. **Expected vs Actual Behavior**: What should happen vs what does
4. **Environment**: CorreX version, Windows version, Python version, application
5. **Configuration**: Relevant config.json excerpts (sanitized)
6. **Logs**: Relevant log excerpts from correx.log
7. **Screenshots**: Visual aids if applicable
8. **Possible Solution**: Optional troubleshooting suggestions

**Key Features**:
- Pre-filled YAML front matter for labels
- Placeholder title `[BUG]`
- Prompts for environment details
- Reminds users to sanitize API keys

#### Feature Request Template

**File**: `feature_request.md`

**Sections**:
1. **Feature Description**: What to build
2. **Problem it Solves**: User pain point or use case
3. **Proposed Solution**: How it should work
4. **Alternative Solutions**: Other approaches considered
5. **Use Case Examples**: Concrete scenarios
6. **Implementation Suggestions**: Technical approach (optional)
7. **Priority**: Critical/High/Medium/Low
8. **Willing to Contribute**: Gauges community involvement

**Key Features**:
- Checkbox for affected components (keyboard, AI, GUI, etc.)
- Priority selection
- Contribution willingness indicator
- Encourages detailed use cases

**Benefits**:
- Reduces incomplete or vague issues
- Provides maintainers with actionable information
- Standardizes issue format for easier triage
- Educates users on what information is needed

### Pull Request Template

**File**: `.github/PULL_REQUEST_TEMPLATE.md`

**Major Sections**:

1. **Description & Type**: What changed and why
2. **Related Issue**: Links to resolved issues
3. **Changes Made**: Bulleted list of modifications
4. **Testing Performed**: Manual and automated testing
5. **Code Quality Checklist**: Black, Flake8, Mypy, docstrings
6. **Testing Checklist**: Unit tests, coverage, edge cases
7. **Documentation Checklist**: README, DEVNOTES, CHANGELOG updates
8. **Performance Impact**: Performance implications
9. **Breaking Changes**: Migration guide if needed
10. **Reviewer Notes**: What to focus on

**Quality Gates**:
```markdown
## Code Quality Checklist
- [ ] Code follows PEP 8
- [ ] Code formatted with Black
- [ ] Linting passes (Flake8)
- [ ] Type hints added
- [ ] Comments added for complex logic
- [ ] Docstrings added/updated
- [ ] No hardcoded values

## Testing Checklist
- [ ] All new code has unit tests
- [ ] All existing tests pass
- [ ] Test coverage maintained or improved
- [ ] Edge cases tested
- [ ] Error handling tested
```

**Benefits**:
- Ensures consistent PR format
- Prevents incomplete submissions
- Reminds contributors of quality standards
- Speeds up code review process
- Captures breaking changes early

### Code of Conduct

**File**: `CODE_OF_CONDUCT.md`

**Standard**: Contributor Covenant v2.1

**Purpose**: Establish community standards and enforcement guidelines.

**Key Sections**:
1. **Our Pledge**: Inclusive, harassment-free environment
2. **Our Standards**: Acceptable and unacceptable behavior
3. **Enforcement Responsibilities**: Moderator duties
4. **Scope**: When and where it applies
5. **Enforcement**: Reporting process
6. **Enforcement Guidelines**: 4-tier consequence system

**Enforcement Tiers**:
1. **Correction**: Private warning for minor issues
2. **Warning**: Public warning with interaction ban
3. **Temporary Ban**: Time-limited exclusion
4. **Permanent Ban**: Indefinite exclusion for severe violations

**Reporting**: Via issue tracker or direct contact to maintainers.

**Benefits**:
- Sets clear behavioral expectations
- Provides framework for handling conflicts
- Creates safe, welcoming environment
- Attracts diverse contributors

### Security Policy

**File**: `SECURITY.md`

**Purpose**: Document security practices, vulnerabilities, and responsible disclosure.

**Major Sections**:

#### Supported Versions
```markdown
| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | ✅                 |
| 1.x.x   | ❌                 |
```

#### Security Considerations
- **API Key Security**: Never commit config.json, use environment variables
- **Data Privacy**: Local processing, cloud API for corrections
- **No Telemetry**: No usage analytics collected
- **Windows Security**: Required permissions explained (keyboard hooks, clipboard)

#### Vulnerability Reporting
- **Process**: Private reporting via email or GitHub security advisories
- **Timeline**: 
  - Acknowledgment within 48 hours
  - Assessment within 7 days
  - Critical fixes in 1-3 days
  - High severity in 1-2 weeks
- **Disclosure**: 90-day coordinated disclosure

#### Severity Levels
- **Critical**: RCE, API key exposure, privilege escalation
- **High**: Unauthorized access, injection, auth bypass
- **Medium**: Info disclosure, DoS, insecure defaults
- **Low**: Minor leaks, best practice violations

#### Best Practices for Users
- Strong API keys
- Enable logging for monitoring
- Use latest version
- Run `safety check` for vulnerable dependencies

#### Known Limitations
- Global keyboard hooks (theoretical keylogger risk)
- Clipboard access for text injection
- Plain text API keys in config (future: Credential Manager)
- No end-to-end encryption (HTTPS only)

**Mitigation**:
- Open source for auditability
- No network access beyond Gemini API
- Local-only buffer operations
- User-controlled features

**Roadmap**:
- Windows Credential Manager for API keys
- Encrypted history database (SQLCipher)
- Local-only mode with Ollama
- Audit logging

**Benefits**:
- Builds user trust through transparency
- Establishes responsible disclosure process
- Documents known risks honestly
- Provides security roadmap

### CI/CD Workflow

**File**: `.github/workflows/tests.yml`

**Purpose**: Automated testing on every push and pull request.

**Jobs**:

#### 1. Test Job
```yaml
strategy:
  matrix:
    python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
```

**Steps**:
1. Checkout code
2. Setup Python (matrix versions)
3. Cache pip packages
4. Install dependencies
5. Run pytest with coverage
6. Upload coverage to Codecov

**Runs on**: `windows-latest` (GitHub-hosted Windows runner)

**Coverage Reporting**: Uploads XML report to Codecov for tracking trends.

#### 2. Lint Job
**Steps**:
1. Setup Python 3.11
2. Install Black, Flake8, Mypy
3. Check formatting with Black (--check)
4. Lint with Flake8 (2-pass: errors, then warnings)
5. Type check with Mypy

**Linting Rules**:
- Flake8: Max line length 100, complexity 10
- Black: Default settings (88 line length for formatting check)
- Mypy: Ignore missing imports for third-party libs

#### 3. Install Test Job
**Steps**:
1. Test `pip install -e .`
2. Verify `import correX` and version
3. Verify `correx --help` command
4. Run installation tests (test_install.py)

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests targeting `main` or `develop`
- Manual workflow dispatch

**Benefits**:
- Catches regressions before merge
- Ensures multi-version Python compatibility
- Verifies installation process
- Maintains code quality standards
- Provides coverage metrics over time

**Future Enhancement**: Add Windows version matrix (Server 2019, Server 2022, Windows 11) once project is on GitHub.

### Roadmap

**File**: `ROADMAP.md`

**Purpose**: Communicate project direction and planned features.

**Structure**:

#### Version 1.0.0 (Current - November 2025)
✅ Completed features (logging, testing, packaging, documentation)

#### Future Enhancements
**Security & Stability**:
- Windows Credential Manager for API keys
- Enhanced error handling
- Performance optimization
- Encrypted history database
- GUI improvements
- Auto-update system

**Multi-language & Accessibility**:
- Multi-language support
- Accessibility improvements (NVDA/JAWS)
- Local-only mode with Ollama
- Plugin system
- Advanced dictation commands

**Advanced Features**:
- Context-aware corrections
- Smart clipboard manager
- Code-aware corrections
- Macro system
- Cross-platform support (macOS/Linux)

**Community Ideas**:
- Custom AI models (OpenAI/Anthropic)
- Team collaboration
- Browser extension
- Voice training
- Gesture support

**Community-Driven**:
- Feature requests via GitHub issues
- Community voting on priorities
- Open discussion for implementation details

### File Structure Summary

```
CorreX/
├── .editorconfig                      # Coding style config
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md             # Bug report template
│   │   └── feature_request.md        # Feature request template
│   ├── PULL_REQUEST_TEMPLATE.md      # PR template
│   └── workflows/
│       └── tests.yml                 # CI/CD pipeline
├── CODE_OF_CONDUCT.md                # Community standards
├── SECURITY.md                       # Security policy
├── ROADMAP.md                        # Future plans
└── README.md                         # Updated with badges
```

### Integration with Existing Infrastructure

**Infrastructure Integration**:

1. **CI/CD ↔ Testing**: Workflow runs `pytest` suite (52 tests)
2. **CI/CD ↔ Linting**: Workflow enforces Black/Flake8/Mypy
3. **CI/CD ↔ Packaging**: Tests `pip install` from setup.py
4. **Roadmap ↔ CHANGELOG**: Released features flow from roadmap to changelog
5. **SECURITY.md ↔ Logging**: References logging for security monitoring
6. **Issue Templates ↔ Logging**: Bug reports request log excerpts
7. **PR Template ↔ Tests**: Requires test updates and coverage checks

### Community Contribution Workflow

**End-to-End Example**:

1. **User discovers bug** → Files issue using bug_report.md template
2. **Maintainer triages** → Labels, assigns milestone, adds to roadmap
3. **Contributor picks up** → Forks, creates branch, implements fix
4. **Contributor submits PR** → Fills PULL_REQUEST_TEMPLATE.md
5. **CI/CD runs** → Tests (52 tests), linting (Black/Flake8), coverage
6. **Maintainer reviews** → Checks code quality checklist, tests locally
7. **PR merged** → CHANGELOG.md updated, version bumped
8. **Release** → GitHub release created, PyPI package published
9. **User notified** → Issue auto-closed with release link

**All steps enabled by project infrastructure.**

### Maintenance Burden

**Ongoing Tasks**:
- Triage issues using templates (5 min/issue)
- Review PRs against checklist (15 min/PR)
- Monitor CI/CD failures (investigate failures)
- Update roadmap quarterly (1 hour)
- Respond to security reports (within 48 hours)
- Update CHANGELOG on releases (10 min)

**Automation Opportunities**:
- Auto-label issues based on template used
- Auto-close stale issues (90 days inactive)
- Auto-generate CHANGELOG from PR titles
- Auto-publish to PyPI on GitHub release

### Comparison to Other Projects

**Inspiration Sources**:
- **VS Code**: Issue templates, PR template structure
- **Django**: Comprehensive SECURITY.md
- **Pandas**: Detailed ROADMAP.md with timelines
- **FastAPI**: Modern GitHub Actions CI/CD
- **Linux Kernel**: Code of Conduct enforcement tiers

**CorreX Additions**:
- Security section specifically for API key management
- Roadmap with realistic effort estimates
- CI/CD testing across 5 Python versions
- EditorConfig for multi-editor consistency

### Benefits of Complete Infrastructure

1. **Professionalism**: Signals mature, well-maintained project
2. **Discoverability**: Badges and clear README attract users
3. **Contribution Friction**: Templates lower barrier to entry
4. **Quality Assurance**: CI/CD catches regressions automatically
5. **Security**: Clear vulnerability disclosure process
6. **Planning**: Roadmap aligns expectations
7. **Community**: Code of Conduct fosters healthy environment
8. **Consistency**: EditorConfig prevents style conflicts

### Future Infrastructure Enhancements

**Potential Future Enhancements**:
- Stale bot for auto-closing inactive issues
- Dependabot for dependency updates
- GitHub Discussions for Q&A
- Wiki for extended documentation
- GitHub Sponsors for funding
- Release Drafter for automatic CHANGELOG
- Semantic versioning bot
- Label sync across forks

---

## Conclusion

This document provides a complete technical blueprint for CorreX. With this information, the project can be reconstructed from scratch, maintained, extended, or forked without requiring prior knowledge of the codebase.

**Key Takeaways**:
1. **Architecture**: Multi-threaded with thread-safe state management
2. **Buffer System**: Per-window keystroke tracking with LRU eviction
3. **AI Integration**: Parallel candidate generation with tone presets
4. **Text Replacement**: Clipboard-first with pywinauto fallback
5. **Voice Recognition**: Multi-engine fallback chain with noise reduction
6. **GUI**: Tkinter with queue-based thread-safe updates
7. **Error Handling**: Graceful degradation at every failure point
8. **Privacy**: Local-first with minimal data retention
9. **Logging**: Centralized system with file rotation
10. **Testing**: Comprehensive unit tests with 88% coverage
11. **Validation**: Schema-based config validation
12. **Packaging**: Modern Python packaging with pip install support
13. **Open Source**: Complete GitHub infrastructure for collaboration

**Project Version**: 1.0.0  
**Last Updated**: November 1, 2025  
**Test Coverage**: 88% (52 unit tests)  
**Distribution**: PyPI-ready with modern packaging  
**Community**: GitHub-ready with templates, CI/CD, and policies

---

**End of Developer Notes**

