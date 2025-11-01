# CorreX Roadmap

This document outlines potential future features and improvements for CorreX. Community feedback and contributions are welcome.

---

## Version 1.0.0 ✅ (Current - November 2025)

**Status**: Released  
**Focus**: Production-ready release with core features

### Completed Features
- ✅ Comprehensive logging system with rotation
- ✅ Modern Python packaging (setup.py + pyproject.toml)
- ✅ CLI options (--verbose, --quiet, --log-file)
- ✅ Full test suite (52 tests, 88% coverage)
- ✅ Configuration validation with JSON schema
- ✅ Professional documentation
- ✅ MIT License and open-source infrastructure
- ✅ Code quality tooling (Black, Flake8, Mypy)
- ✅ GitHub templates and CI/CD workflows

---

## Future Enhancements

**Status**: Community-driven  
**Focus**: Feature requests and improvements

### Potential Features

#### Security & Stability
- [ ] **Windows Credential Manager Integration**
  - Secure API key storage in Windows Credential Manager
  - Migration tool for existing config.json keys

- [ ] **Enhanced Error Handling**
  - Graceful degradation when Gemini API is unavailable
  - Better error messages for configuration mistakes
  - Auto-retry logic with exponential backoff

- [ ] **Performance Optimization**
  - Reduce memory footprint
  - Optimize keyboard hook latency
  - Cache frequent corrections locally

- [ ] **Encrypted History Database**
  - SQLCipher integration for history.db
  - User-configurable encryption passphrase

#### User Interface
- [ ] **Improved GUI**
  - Modern UI design
  - Real-time hotkey conflict detection
  - Visual feedback for active corrections
  - Dark mode support

- [ ] **Auto-update System**
  - Check for updates on startup
  - One-click update from tray icon
  - Changelog display in GUI

#### Multi-language & Accessibility
- [ ] **Multi-Language Support**
  - Auto-detect text language before correction
  - Language-specific correction prompts
  - Support for multiple languages via Gemini
  - Per-application language preferences

- [ ] **Accessibility Improvements**
  - Screen reader compatibility (NVDA/JAWS)
  - High contrast mode
  - Keyboard-only navigation
  - Configurable audio feedback

- [ ] **Local-Only Mode** - Offline correction using local models

- [ ] **Custom AI Models** - Support for OpenAI/Anthropic endpoints
- [ ] **Team Collaboration** - Shared correction templates
- [ ] **Markdown/LaTeX Support** - Special handling for formatted text
- [ ] **Voice Training** - Adapt to user's accent
- [ ] **Gesture Support** - Touchpad/mouse gestures
- [ ] **Browser Extension** - Web-based editor integration
- [ ] **GUI Improvements** - Modern UI framework
- [ ] **Async I/O** - Asynchronous API calls
- [ ] **Internationalization** - Multi-language UI
- [ ] **Installer** - NSIS or MSI installer with auto-start

---

## Contributing

We welcome community input! Here's how you can help:

1. **Vote on Features**: Use 👍 reactions on feature request issues
2. **Propose Features**: Open a feature request using the template
3. **Discuss**: Comment on existing feature requests
4. **Implement**: Check "Help Wanted" labels on GitHub

---

**Last Updated**: November 2025  
**Version**: 1.0.0
