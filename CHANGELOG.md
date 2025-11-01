# Changelog

All notable changes to CorreX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2025-11-01

### 🎉 Initial Release

First production-ready release with professional features, documentation, and packaging.

### Added
- **Package Distribution:** Full `setup.py` configuration for pip installation
- **Centralized Logging:** New `logger.py` module with proper logging infrastructure
- **Command-Line Options:** Added `--verbose`, `--quiet`, `--log-file` flags
- **License File:** MIT License added to project root
- **Version Metadata:** Added `__version__`, `__author__`, `__license__` to `__init__.py`
- **Git Support:** Comprehensive `.gitignore` for clean version control
- **Manifest File:** `MANIFEST.in` for proper package data inclusion
- **Contributing Guide:** Complete `CONTRIBUTING.md` with development guidelines
- **Changelog:** This file to track version history

### Changed
- **Installation Methods:** Now supports both `pip install .` and direct run
- **Documentation:** Enhanced README with multiple installation options
- **Logging Configuration:** Added programmatic and CLI-based logging controls

### Technical Improvements
- Thread-safe architecture with proper locking
- Parallel API generation using ThreadPoolExecutor
- Comprehensive error handling at all layers
- Clean shutdown with resource cleanup
- Per-candidate AI configuration (tone + temperature)

### Documentation
- **DEVNOTES.md** (3,266 lines): Complete technical blueprint
- **README.md**: Enhanced user guide with examples
- **QUICK_START.md**: Fast reference guide
- **DICTATION_FEATURE.md**: Voice dictation documentation
- **CONTRIBUTING.md**: Developer contribution guidelines

---

## [1.5.0] - 2025-10-XX

### Added
- Multi-engine voice dictation (Google, Whisper, Sphinx)
- Noise reduction for voice input
- Visual microphone overlay with pulsing animation
- Configurable dictation hotkey (default: Ctrl+Shift+D)

### Changed
- Voice dictation now works across all applications
- Improved audio quality with ambient noise calibration

---

## [1.0.0] - 2025-10-XX

### Added
- AI-powered text correction using Google Gemini API
- Multiple correction candidates (up to 5)
- Per-candidate tone and temperature configuration
- Internal keystroke buffer (no clipboard interference)
- System tray icon with menu
- Modern Tkinter GUI for configuration
- Loading overlay with customizable position
- Cross-application text replacement
- History tracking with auto-cleanup
- Configurable trigger keys
- Buffer clearing hotkey
- Windows startup support

### Core Features
- **Tones:** Original, Professional, Formal, Informal, Detailed, Creative
- **Temperature Control:** 0.0-1.0 per candidate
- **Text Replacement:** Clipboard + pywinauto fallback
- **Error Handling:** Graceful degradation on failures

---

## [0.5.0] - Early Development

### Initial Implementation
- Basic keyboard hook functionality
- Simple clipboard-based text replacement
- Single correction candidate
- Manual API key configuration

---

## [Unreleased]

### Planned Features
- Offline AI mode (local model)
- Multi-language support
- Context-aware correction (detect code vs prose)
- Encrypted config storage
- Plugin system for custom correctors
- Auto-update mechanism
- History search and replay
- Customizable prompt templates
- Per-application correction profiles

### Known Issues
- Clipboard timing issues on very fast systems (50ms delay may not be enough)
- Window focus during correction can cause misplaced text
- Some Electron apps require pywinauto fallback
- Terminal applications incompatible (cmd.exe, PowerShell)
- Virtual machines and remote desktop not supported

---

## Version History Summary

| Version | Date       | Status          | Highlights                           |
|---------|------------|-----------------|--------------------------------------|
| 1.0.0   | 2025-11-01 | ✅ Production   | Initial release with all features    |

---

## Installation

```bash
# From source
pip install -e .

# Or direct run
python -m correX
```

**Command-Line Options:**
```bash
# Enable debug logging
correx --verbose

# Write logs to file
correx --log-file correx.log

# Quiet mode (errors only)
correx --quiet
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

---

## Links

- **GitHub Repository:** https://github.com/vikas7516/CorreX
- **Issue Tracker:** https://github.com/vikas7516/CorreX/issues
- **Documentation:** [DEVNOTES.md](DEVNOTES.md)
- **License:** [MIT License](LICENSE)

---

**Current Version:** 1.0.0  
**Last Updated:** November 1, 2025
