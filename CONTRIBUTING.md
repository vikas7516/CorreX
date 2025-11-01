# Contributing to CorreX

Thank you for your interest in contributing to CorreX! This document provides guidelines and instructions for contributing to the project.

---

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **Windows 10/11** (CorreX is Windows-specific)
- **Git** for version control
- **Google Gemini API Key** for testing

### Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/vikas7516/CorreX.git
cd CorreX
```

---

## 🛠️ Development Setup

### 1. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\activate  # Windows PowerShell
```

### 2. Install in Development Mode

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Or manually install dependencies
pip install -r correX/requirements.txt
pip install pytest pytest-cov black flake8 mypy
```

### 3. Configure API Key

```bash
# Set environment variable
$env:GEMINI_API_KEY="your-api-key-here"

# Or configure via GUI on first run
python -m correX
```

### 4. Run the Application

```bash
# Run with verbose logging
python -m correX --verbose

# Run with log file
python -m correX --log-file correx_dev.log

# Run without GUI (requires configured API key)
python -m correX --no-gui
```

---

## 📝 Code Style

### Python Code Standards

CorreX follows **PEP 8** with some adjustments:

- **Line length:** 120 characters (instead of 79)
- **Type hints:** Use type hints for all function signatures
- **Docstrings:** Google-style docstrings for all public functions/classes
- **Imports:** Group imports (stdlib, third-party, local)

### Formatting with Black

```bash
# Format all Python files
black correX/

# Check formatting without changes
black --check correX/
```

### Linting with Flake8

```bash
# Run flake8
flake8 correX/ --max-line-length=120 --ignore=E203,W503
```

### Type Checking with Mypy

```bash
# Run mypy
mypy correX/ --ignore-missing-imports
```

---

## 🧪 Testing

### Manual Testing Checklist

Before submitting changes, test:

1. **Basic Correction:**
   - Type text in Notepad
   - Press TAB → verify correction appears
   - Use Ctrl+Left/Right → verify navigation works

2. **Voice Dictation:**
   - Press Ctrl+Shift+D → mic overlay appears
   - Speak clearly → text inserted correctly
   - Press Ctrl+Shift+D again → stops cleanly

3. **GUI:**
   - Open settings → verify all controls work
   - Change settings → verify persistence
   - Test button → verify overlay preview

4. **Error Handling:**
   - Invalid API key → graceful error message
   - Network disconnect → fallback behavior
   - Window focus change during correction → no crashes

### Unit Tests (Future)

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=correX tests/
```

---

## 📤 Submitting Changes

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Follow conventional commits format:

```
type(scope): short description

Longer description if needed

Fixes #123
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting
- `refactor:` Code restructuring
- `test:` Adding tests
- `chore:` Maintenance

**Examples:**
```
feat(dictation): add Whisper fallback support
fix(buffer): resolve NumLock alt key confusion
docs(readme): update installation instructions
```

### Pull Request Process

1. **Create a branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "feat(scope): description"
   ```

3. **Push to your fork:**
   ```bash
   git push origin feature/my-new-feature
   ```

4. **Open Pull Request:**
   - Go to GitHub and create PR
   - Fill out PR template
   - Link related issues
   - Request review

5. **Address feedback:**
   - Make requested changes
   - Push updates to same branch
   - PR will update automatically

### PR Checklist

- [ ] Code follows style guidelines
- [ ] All tests pass (if applicable)
- [ ] Documentation updated (if needed)
- [ ] No new warnings or errors
- [ ] Manually tested on Windows
- [ ] Commit messages are clear

---

## 🐛 Reporting Issues

### Before Reporting

1. Search existing issues
2. Try latest version
3. Check documentation (README, DEVNOTES)

### Issue Template

```markdown
**Description:**
Clear description of the problem

**Steps to Reproduce:**
1. Do this
2. Then this
3. Error occurs

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- CorreX Version: 1.0.0
- Python Version: 3.11
- Windows Version: Windows 11
- Gemini Model: gemini-2.0-flash-exp

**Logs:**
Paste relevant error messages or logs

**Screenshots:**
If applicable
```

### Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature request
- `documentation` - Documentation improvement
- `question` - Further information requested
- `help wanted` - Extra attention needed
- `good first issue` - Good for newcomers

---

## 🏗️ Architecture Overview

For detailed technical information, see **[DEVNOTES.md](DEVNOTES.md)**

### Key Modules

- **`main.py`** - Entry point, bootstrap
- **`autocorrect_service.py`** - Keyboard hooks, trigger handling
- **`gemini_corrector.py`** - API integration, parallel generation
- **`keystroke_buffer.py`** - Per-window text tracking
- **`text_buffer.py`** - Cross-app text replacement
- **`dictation_manager.py`** - Voice recognition
- **`gui/app_gui.py`** - Tkinter GUI
- **`logger.py`** - Centralized logging

### Threading Model

- **Main Thread:** Tkinter GUI event loop
- **Daemon Thread:** System tray icon
- **Keyboard Hook Thread:** Global keyboard events
- **Worker Pool:** Parallel API requests
- **Dictation Thread:** Audio capture/processing

---

## 💡 Development Tips

### Debugging

```python
# Enable debug logging
python -m correX --verbose --log-file debug.log

# Check what's in the keystroke buffer
# (Add debug prints in keystroke_buffer.py)
```

### Testing Trigger Keys

```python
# In autocorrect_service.py, add debug output:
def _is_trigger_pressed(self, event):
    result = # ... existing logic
    print(f"[DEBUG] Trigger check: {result} (event: {event})")
    return result
```

### Profiling Performance

```python
import cProfile
import pstats

# Profile API calls
profiler = cProfile.Profile()
profiler.enable()
# ... code to profile
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(10)
```

---

## 📚 Additional Resources

- **[README.md](README.md)** - User guide
- **[DEVNOTES.md](DEVNOTES.md)** - Technical documentation
- **[QUICK_START.md](QUICK_START.md)** - Quick reference
- **[Google Gemini API Docs](https://ai.google.dev/docs)**

---

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## 🙏 Thank You!

Your contributions make CorreX better for everyone. Whether it's code, documentation, bug reports, or feature ideas – we appreciate your help!

---

**Happy Coding!** 🚀
