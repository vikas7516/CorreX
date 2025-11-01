# ⚡ QUICK START - CorreX

## 🚀 Launch
```bash
python -m correX
```

## ⚙️ First Time Setup
1. Click "▶ Show Instructions"
2. Get API key: https://makersuite.google.com/app/apikey
3. Paste in GUI
4. Click "💾 Save & Apply"

## 🎯 Usage
```
Type anywhere → Press TAB → Text corrects instantly!
```

## ⌨️ Keyboard Shortcuts
- **TAB** - Send to AI (get correction)
- **Ctrl+Left/Right** - Navigate suggestions
- **Any key** - Accept current suggestion

## 🎤 Voice Dictation
**How to Use:**
1. Press **Ctrl+Shift+D** (or your custom trigger)
2. Mic overlay appears at bottom-center with pulsing animation
3. Speak naturally - system listens continuously
4. Text is automatically typed into active window
5. Press the trigger again to stop listening

**Features:**
- **Multi-Engine Recognition**: Google Speech API (primary), Whisper (fallback), Sphinx (offline)
- **Noise Reduction**: Automatic ambient noise calibration for better accuracy
- **Configurable Trigger**: Change in GUI → Settings → Dictation Trigger
- **Visual Feedback**: Always-on-top pulsing mic overlay shows when listening
- **Buffer Integration**: Dictated text can be corrected with AI just like typed text

**Installation (Required):**
```powershell
pip install SpeechRecognition PyAudio
```

**Optional (Enhanced Accuracy):**
```powershell
pip install noisereduce numpy  # Noise reduction
pip install openai-whisper     # Offline high-accuracy
```

**Tips:**
- Speak clearly with natural pauses between sentences
- System auto-adjusts for ambient noise in first 0.5 seconds
- Works in ANY Windows app (same as text correction)
- No internet needed if Whisper/Sphinx installed
- Press trigger anytime to stop, even mid-sentence

**Troubleshooting:**
- **No microphone detected**: Check Windows Privacy Settings → Microphone → Allow apps to access
- **Poor accuracy in noise**: Install `noisereduce` for audio cleanup
- **PyAudio install fails**: Download precompiled wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

## 📊 Status Indicators
- **● Green** - Service active
- **● Red** - API not configured

## 🔧 Settings
- **Correction Trigger**: TAB (or F1-F6, Ctrl+Space)
- **Dictation Trigger**: Ctrl+Shift+D (customizable)
- **Clear Buffer Trigger**: Configurable or disabled
- **AI Candidates**: 1-5 suggestions per correction
- **Candidate Personalization**: Set tone (Original, Professional, Formal, Informal, Detailed, Creative) and temperature (0.0-1.0) for each candidate
- **Model**: gemini-2.0-flash-exp (recommended)

## 🔐 Privacy
- History auto-deletes after 1 hour
- Config saved permanently
- Clipboard never touched
- Speech processed via Google API or locally (Whisper/Sphinx)

## ✅ Works In
- Notepad
- Word
- Browsers (Chrome, Edge, Firefox)
- VS Code
- Chat apps (Discord, Slack, WhatsApp Web)
- Email clients
- **ANY Windows app!**

## 🎉 Features
✅ AI text correction with multiple candidates
✅ Per-candidate tone and temperature control
✅ Voice dictation with multi-engine recognition
✅ Internal buffer (no clipboard interference)
✅ Pure AI text (no explanations)
✅ Instant replacement
✅ Cross-app compatibility
✅ Noise reduction and adaptive calibration

---

**That's it! Start typing and press TAB, or speak with Ctrl+Shift+D!** 🚀
