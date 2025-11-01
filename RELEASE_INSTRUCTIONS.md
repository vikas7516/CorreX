# CorreX Release Instructions

## Current Build Status
PyInstaller is building `CorreX.exe` - a standalone Windows executable.

## What You'll Get

After the build completes (3-5 minutes), you'll have:

### **dist/CorreX.exe**
- **Single executable file** (~80-150 MB)
- Contains Python + all dependencies bundled
- No installation required - just double-click to run
- Users DON'T need Python installed

## Distribution Options

### Option 1: Simple ZIP Distribution (Easiest)
1. Wait for build to complete
2. Compress `dist/CorreX.exe` → `CorreX-v1.0.0-Windows.zip`
3. Upload to GitHub Releases
4. Users download, unzip, and run

### Option 2: Professional Installer (Recommended)
Create a Windows installer using **Inno Setup**:
- Single `.exe` installer file
- Adds to Start Menu
- Creates desktop shortcut  
- Professional uninstaller
- ~85-160 MB installer size

## GitHub Release Steps

### 1. Create Release on GitHub
```
1. Go to https://github.com/vikas7516/CorreX/releases/new
2. Tag version: v1.0.0
3. Release title: CorreX v1.0.0 - AI-Powered Text Correction & Dictation
4. Description: (see template below)
5. Upload: CorreX-v1.0.0-Windows.zip or CorreX-Setup-v1.0.0.exe
6. Publish release
```

### 2. Release Description Template
```markdown
## 🎉 CorreX v1.0.0 - Initial Release

AI-powered text correction and voice dictation assistant for Windows.

### ✨ Features
- **Intelligent Text Correction** - Press `Ctrl+Space` for AI grammar fixes
- **Voice Dictation** - Press `Ctrl+Shift+V` to dictate text
- **Multiple Tone Modes** - Original, Professional, Formal, Informal, Detailed
- **System Tray Integration** - Runs quietly in background
- **Privacy-First** - All processing via your own Gemini API key

### 📥 Installation

#### Quick Start
1. Download `CorreX-v1.0.0-Windows.zip`
2. Extract and run `CorreX.exe`
3. Enter your Google Gemini API key
4. Start using hotkeys anywhere in Windows!

#### Requirements
- Windows 10/11
- Google Gemini API key (free at https://makersuite.google.com/app/apikey)
- Microphone (for voice dictation)

### 📖 Documentation
- [Quick Start Guide](https://github.com/vikas7516/CorreX/blob/main/QUICK_START.md)
- [Full Documentation](https://github.com/vikas7516/CorreX/blob/main/README.md)

### 🐛 Known Issues
- First run may take a few seconds to load
- Requires internet connection for AI corrections

### 🙏 Feedback
Report issues: https://github.com/vikas7516/CorreX/issues
```

## File Sizes (Approximate)
- `CorreX.exe`: 80-150 MB
- `CorreX-v1.0.0-Windows.zip`: 30-60 MB (compressed)
- `CorreX-Setup-v1.0.0.exe` (with installer): 85-160 MB

## Testing Before Release
1. Run `dist\CorreX.exe` 
2. Test Ctrl+Space correction
3. Test Ctrl+Shift+V dictation
4. Verify system tray icon
5. Test with fresh API key entry

## Next Steps After Build
1. **Test the executable**: `.\dist\CorreX.exe`
2. **Create ZIP**: Compress `dist\CorreX.exe`
3. **GitHub Release**: Upload to releases page
4. **(Optional)** Create professional installer with Inno Setup

---

**Current Status**: Building executable... ⏳
**Build Tool**: PyInstaller 6.16.0
**Target**: Windows 11 (x64)
