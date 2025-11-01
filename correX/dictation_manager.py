"""Speech-to-text dictation manager with noise reduction and multi-engine support."""
from __future__ import annotations

import threading
import time
from typing import Optional, Callable
import speech_recognition as sr

# Optional dependencies for enhanced audio processing
try:
    import noisereduce as nr
    import numpy as np
    HAS_NOISE_REDUCTION = True
except ImportError:
    HAS_NOISE_REDUCTION = False
    nr = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

try:
    import whisper  # type: ignore[import-not-found]
    HAS_WHISPER = True  # Available if import succeeds; can be disabled at runtime if needed
except ImportError:
    HAS_WHISPER = False
    whisper = None  # type: ignore[assignment]


class DictationManager:
    """
    Manages speech-to-text dictation with advanced noise reduction.
    Supports multiple recognition engines for best accuracy.
    """
    
    def __init__(self):
        """Initialize dictation manager."""
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        self.listen_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Callbacks
        self.on_text_recognized: Optional[Callable[[str], None]] = None
        self.on_listening_started: Optional[Callable[[], None]] = None
        self.on_listening_stopped: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Configure recognizer for better accuracy
        self.recognizer.energy_threshold = 300  # Lower for quiet environments
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8  # How long to wait for speech continuation
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.5
        
        # Recognition engines priority (try in order, filtered by availability)
        self.engines = self._compute_engine_priority()

        # Whisper model cache (lazy-loaded)
        self._whisper_model = None
        self._whisper_model_name = "base"
        
        print("[DICTATION] Manager initialized")
    
    def start_listening(self) -> bool:
        """
        Start listening for speech input.
        Returns True if started successfully.
        """
        with self._lock:
            if self.is_listening:
                print("[DICTATION] Already listening")
                return False
            
            try:
                # Initialize microphone
                if self.microphone is None:
                    self.microphone = sr.Microphone()
                
                # Adjust for ambient noise
                print("[DICTATION] Calibrating for ambient noise...")
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                self.is_listening = True
                self._stop_event.clear()
                
                # Start listening in background thread
                self.listen_thread = threading.Thread(
                    target=self._listen_loop,
                    daemon=True,
                    name="DictationListener"
                )
                self.listen_thread.start()
                
                if self.on_listening_started:
                    self.on_listening_started()
                
                print("[DICTATION] Started listening")
                return True
                
            except Exception as e:
                print(f"[DICTATION] Failed to start: {e}")
                if self.on_error:
                    self.on_error(f"Microphone error: {str(e)}")
                return False
    
    def stop_listening(self) -> None:
        """Stop listening for speech input."""
        with self._lock:
            if not self.is_listening:
                return
            
            self.is_listening = False
            self._stop_event.set()
            
            if self.on_listening_stopped:
                self.on_listening_stopped()
            
            print("[DICTATION] Stopped listening")
    
    def _listen_loop(self) -> None:
        """Background loop that continuously listens and recognizes speech."""
        try:
            with self.microphone as source:
                while self.is_listening:
                    try:
                        if self._stop_event.is_set():
                            break
                        # Listen for audio with timeout
                        print("[DICTATION] Listening for speech...")
                        audio = self.recognizer.listen(
                            source,
                            timeout=1.0,  # Short timeout to remain responsive to stop
                            phrase_time_limit=30  # Max 30 seconds per phrase
                        )
                        
                        if not self.is_listening or self._stop_event.is_set():
                            break
                        
                        print("[DICTATION] Processing audio...")
                        
                        # Apply noise reduction if available
                        if HAS_NOISE_REDUCTION:
                            audio = self._apply_noise_reduction(audio)
                        
                        # Try recognition with multiple engines
                        text = self._recognize_audio(audio)
                        
                        if text and self.on_text_recognized:
                            print(f"[DICTATION] Recognized: '{text}'")
                            self.on_text_recognized(text)
                        
                    except sr.WaitTimeoutError:
                        # No speech detected, continue listening
                        continue
                    except Exception as e:
                        print(f"[DICTATION] Recognition error: {e}")
                        if self.on_error:
                            self.on_error(f"Recognition failed: {str(e)}")
                        time.sleep(0.5)  # Brief pause before retrying
                        
        except Exception as e:
            print(f"[DICTATION] Listen loop error: {e}")
            if self.on_error:
                self.on_error(f"Fatal error: {str(e)}")
        finally:
            with self._lock:
                self.is_listening = False
    
    def _apply_noise_reduction(self, audio: sr.AudioData) -> sr.AudioData:
        """Apply noise reduction to improve recognition accuracy."""
        try:
            # Convert audio to numpy array
            audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
            
            # Apply noise reduction
            reduced_noise = nr.reduce_noise(
                y=audio_data,
                sr=audio.sample_rate,
                stationary=False,
                prop_decrease=0.8
            )
            
            # Convert back to AudioData
            # Ensure int16 dtype as required by AudioData
            if hasattr(np, 'issubdtype') and np.issubdtype(reduced_noise.dtype, np.floating):
                # Scale float range [-1,1] or arbitrary to int16 range
                scaled = reduced_noise
                # If values are in [-1, 1], scale; otherwise clip to int16
                if scaled.max(initial=1) <= 1.0 and scaled.min(initial=-1) >= -1.0:
                    scaled = scaled * 32767.0
                int16_data = np.clip(scaled, -32768, 32767).astype(np.int16)
            else:
                int16_data = reduced_noise.astype(np.int16, copy=False)

            return sr.AudioData(
                int16_data.tobytes(),
                audio.sample_rate,
                audio.sample_width
            )
        except Exception as e:
            print(f"[DICTATION] Noise reduction failed: {e}")
            return audio  # Return original audio if processing fails
    
    def _recognize_audio(self, audio: sr.AudioData) -> Optional[str]:
        """
        Try to recognize audio using multiple engines.
        Returns recognized text or None.
        """
        engines = self.engines or []

        for engine in engines:
            if engine == 'google':
                try:
                    print("[DICTATION] Trying Google Speech Recognition...")
                    text = self.recognizer.recognize_google(audio, language='en-US')
                    if text:
                        return text.strip()
                except sr.UnknownValueError:
                    print("[DICTATION] Google could not understand audio")
                except sr.RequestError as e:
                    print(f"[DICTATION] Google API error: {e}")
                except Exception as e:
                    print(f"[DICTATION] Google recognition error: {e}")

            elif engine == 'whisper' and HAS_WHISPER:
                try:
                    print("[DICTATION] Trying Whisper...")
                    # Save audio to temporary file for Whisper
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio.get_wav_data())
                        temp_path = f.name

                    model = self._get_whisper_model()
                    result = model.transcribe(temp_path, language='en') if model else None

                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

                    if result and isinstance(result, dict) and result.get('text'):
                        return result['text'].strip()
                except Exception as e:
                    print(f"[DICTATION] Whisper recognition error: {e}")

            elif engine == 'sphinx':
                try:
                    print("[DICTATION] Trying Sphinx (offline)...")
                    text = self.recognizer.recognize_sphinx(audio)
                    if text:
                        return text.strip()
                except sr.UnknownValueError:
                    print("[DICTATION] Sphinx could not understand audio")
                except Exception as e:
                    print(f"[DICTATION] Sphinx recognition error: {e}")

        return None

    def _compute_engine_priority(self) -> list[str]:
        """Compute engine priority list based on availability."""
        engines: list[str] = []
        # Prefer Google first (usually most accurate with internet)
        engines.append('google')
        # Add Whisper if installed
        if HAS_WHISPER:
            engines.append('whisper')
        # Always include offline sphinx as last resort
        engines.append('sphinx')
        return engines

    def _get_whisper_model(self):
        """Lazy-load and cache Whisper model to avoid per-request load."""
        if not HAS_WHISPER or whisper is None:
            return None
        try:
            if self._whisper_model is None:
                print(f"[DICTATION] Loading Whisper model '{self._whisper_model_name}' (once)...")
                self._whisper_model = whisper.load_model(self._whisper_model_name)
            return self._whisper_model
        except Exception as e:
            print(f"[DICTATION] Failed to load Whisper model: {e}")
            return None
    
    def is_active(self) -> bool:
        """Check if dictation is currently active."""
        with self._lock:
            return self.is_listening
