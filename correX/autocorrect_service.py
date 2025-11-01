"""Background service - API-triggered paragraph autocorrect with internal keystroke buffer."""
from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Optional, TYPE_CHECKING, Callable, List, Dict, Any

import keyboard

from .gemini_corrector import GeminiCorrector
from .text_buffer import TextBufferManager
from .keystroke_buffer import KeystrokeBuffer
from .dictation_manager import DictationManager
from .mic_overlay import MicOverlay

if TYPE_CHECKING:
    from .history_manager import HistoryManager
else:
    try:
        from .history_manager import HistoryManager
    except ImportError:
        HistoryManager = None


class AutoCorrectService:
    """
    API-triggered autocorrect with candidate selection.
    
    Two types of triggers:
    1. API Trigger (default TAB) - Sends text to API, shows first candidate immediately
    2. Navigation Trigger (default Ctrl+Arrow) - Cycles candidates (only in selection mode)
    """

    def __init__(
        self,
        corrector: GeminiCorrector,
        *,
        enable_paragraph: bool = True,
        trigger_key: str = "ctrl+space",
        clear_buffer_trigger_key: str = "ctrl+shift+delete",
        dictation_trigger_key: str = "ctrl+shift+d",
        versions_per_correction: int = 3,
        candidate_settings: Optional[List[Dict[str, Any]]] = None,
        history_manager: Optional["HistoryManager"] = None,
    ) -> None:
        self._corrector = corrector
        self._paragraph_enabled = enable_paragraph
        normalized_trigger = self.normalize_trigger_key(trigger_key) or "ctrl+space"
        normalized_clear = self.normalize_trigger_key(clear_buffer_trigger_key) if clear_buffer_trigger_key else ""
        normalized_dictation = self.normalize_trigger_key(dictation_trigger_key) or "ctrl+shift+d"

        self._trigger_key = normalized_trigger
        self._clear_buffer_trigger_key = normalized_clear or ""
        self._dictation_trigger_key = normalized_dictation
        self._candidate_settings = self._prepare_candidate_settings(candidate_settings)
        self._versions_per_correction = self._sanitize_version_count(versions_per_correction)
        self._history_manager = history_manager
        
        self._running = False
        self._suppress_events = False
        self._last_input_snapshot = ""
        self._last_region_snapshot = ""
        self._last_requested_region = ""
        self._last_preview_text = ""
        self._current_prefix = ""
        self._current_suffix = ""
        self._current_region_original = ""
        self._accepted_text_accumulator = ""
        self._status_listeners: list[Callable[[bool], None]] = []
        self._lock = threading.RLock()
        
        # GUI callbacks for loading indicator
        self._gui_callbacks = None
        
        # Internal keystroke buffer (tracks typing in real-time)
        self._keystroke_buffer = KeystrokeBuffer()
        
        # Text buffer manager (for UIAutomation replacement)
        self._buffer_manager = TextBufferManager()
        
        self._pending_correction = False
        
        # Baseline tracking for incremental refinement
        self._baseline_text = ""
        self._last_control = None
        
        # Candidate selection mode
        self._in_selection_mode = False
        self._current_candidates = []
        self._current_candidate_index = 0

        self._keyboard_hook = None
        self._executor = None
        
        # Dictation components
        self._dictation_manager = DictationManager()
        self._mic_overlay = MicOverlay()
        self._setup_dictation_callbacks()

    @staticmethod
    def _sanitize_version_count(count: Any) -> int:
        try:
            value = int(count)
        except (TypeError, ValueError):
            value = 1
        return max(1, min(value, GeminiCorrector.MAX_CANDIDATES))

    def _prepare_candidate_settings(self, settings: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        try:
            return GeminiCorrector.normalize_candidate_settings(settings)
        except Exception as error:
            print(f"[WARNING] Candidate settings invalid; using defaults: {error}")
            return GeminiCorrector.normalize_candidate_settings(None)

    def start(self) -> None:
        """Start the autocorrect service."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._ensure_executor()
            # Install non-suppressing global hook and manage suppression manually
            self._keyboard_hook = keyboard.on_press(self._on_key_event)
            print(f"[INFO] AutoCorrectService started")
            print(f"[INFO] API Trigger: {self._trigger_key.upper()} | Navigation: Ctrl+Left/Right")

    def stop(self) -> None:
        """Stop the autocorrect service."""
        # Stop dictation if active
        if self._dictation_manager.is_active():
            try:
                self.stop_dictation()
            except Exception as dictation_error:
                print(f"[WARNING] Failed to stop dictation: {dictation_error}")
        
        # Check state and unhook keyboard with lock
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._keyboard_hook is not None:
                keyboard.unhook(self._keyboard_hook)
                self._keyboard_hook = None
            
            executor_to_shutdown = self._executor
            self._executor = None
        
        # Shutdown executor OUTSIDE lock to prevent deadlock
        # (tasks may need to acquire lock during cleanup)
        if executor_to_shutdown is not None:
            print(f"[INFO] Shutting down executor (waiting for pending tasks)...")
            try:
                executor_to_shutdown.shutdown(wait=True, cancel_futures=False)
                print(f"[INFO] Executor shutdown complete")
            except Exception as e:
                print(f"[WARNING] Executor shutdown error: {e}")
        
        print(f"[INFO] AutoCorrectService stopped")

    @property
    def paragraph_enabled(self) -> bool:
        return self._paragraph_enabled

    def set_paragraph_enabled(self, enabled: bool) -> None:
        self._paragraph_enabled = enabled
        print(f"[CONFIG] Paragraph correction {'enabled' if enabled else 'disabled'}")
        for listener in list(self._status_listeners):
            try:
                listener(enabled)
            except Exception as listener_error:
                print(f"[WARNING] Status listener error: {listener_error}")

    def get_trigger_key(self) -> str:
        return self._trigger_key
    
    @staticmethod
    def get_valid_trigger_keys() -> list[str]:
        """Retained for backwards compatibility with older configs/UI."""
        return [
            'ctrl+space',
            'ctrl+shift+space',
            'ctrl+shift+d',
            'tab',
            'shift+tab',
            'ctrl+tab',
            'ctrl+shift+delete',
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6',
            'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
        ]

    @staticmethod
    def normalize_trigger_key(raw: Optional[str]) -> Optional[str]:
        """
        Normalize a trigger string into a canonical form understood by the
        keyboard hook (e.g. "ctrl+shift+d"). Returns None when the input cannot
        be expressed as a supported trigger combination.
        """
        if raw is None:
            return None

        candidate = raw.strip().lower()
        if not candidate:
            return None

        parts = [part.strip() for part in candidate.split('+') if part.strip()]
        if not parts:
            return None

        modifier_aliases = {
            'control': 'ctrl',
            'control_l': 'ctrl',
            'control_r': 'ctrl',
            'ctrl_l': 'ctrl',
            'ctrl_r': 'ctrl',
            'command': 'ctrl',
            'cmd': 'ctrl',
            'option': 'alt',
            'option_l': 'alt',
            'option_r': 'alt',
            'alt_l': 'alt',
            'alt_r': 'alt',
            'meta': 'alt',
            'meta_l': 'alt',
            'meta_r': 'alt',
            'shift_l': 'shift',
            'shift_r': 'shift',
        }

        key_aliases = {
            'return': 'enter',
            'enter': 'enter',
            'escape': 'esc',
            'esc': 'esc',
            'space': 'space',
            'spacebar': 'space',
            'backspace': 'backspace',
            'delete': 'delete',
            'del': 'delete',
            'insert': 'insert',
            'ins': 'insert',
            'tab': 'tab',
            'caps_lock': 'caps lock',
            'capslock': 'caps lock',
            'page_up': 'page up',
            'pageup': 'page up',
            'prior': 'page up',
            'page_down': 'page down',
            'pagedown': 'page down',
            'next': 'page down',
            'home': 'home',
            'end': 'end',
            'up': 'up',
            'down': 'down',
            'left': 'left',
            'right': 'right',
            'minus': '-',
            'equal': '=',
            'comma': ',',
            'period': '.',
            'slash': '/',
            'backslash': '\\',
            'bracketleft': '[',
            'bracketright': ']',
            'semicolon': ';',
            'apostrophe': "'",
            'grave': '`',
            'print': 'print screen',
            'print_screen': 'print screen',
            'scroll_lock': 'scroll lock',
            'scrolllock': 'scroll lock',
            'pause': 'pause',
            'break': 'pause',
            'num_lock': 'num lock',
            'numlock': 'num lock',
        }

        allowed_base_keys = set(str(i) for i in range(10))
        allowed_base_keys.update(chr(i) for i in range(ord('a'), ord('z') + 1))
        allowed_base_keys.update({
            'enter', 'esc', 'space', 'backspace', 'delete', 'insert', 'tab', 'caps lock',
            'page up', 'page down', 'home', 'end', 'up', 'down', 'left', 'right',
            'print screen', 'scroll lock', 'pause', 'num lock',
            '-', '=', ',', '.', '/', '\\', '[', ']', ';', "'", '`'
        })
        allowed_base_keys.update({f"f{i}" for i in range(1, 25)})

        modifiers_in_order = ['ctrl', 'shift', 'alt']
        modifiers: list[str] = []
        base_key: Optional[str] = None

        for part in parts:
            normalized_part = modifier_aliases.get(part, part)
            if normalized_part in modifiers_in_order:
                if normalized_part not in modifiers:
                    modifiers.append(normalized_part)
                continue

            mapped_key = key_aliases.get(normalized_part, normalized_part)
            # Special case for digits & letters already handled above.
            if len(mapped_key) == 1 and mapped_key.isalpha():
                mapped_key = mapped_key.lower()
            if mapped_key.isdigit():
                mapped_key = mapped_key

            if mapped_key.startswith('f') and mapped_key[1:].isdigit():
                base_key = mapped_key
            elif mapped_key in allowed_base_keys:
                base_key = mapped_key
            else:
                # Allow plain alphabetic strings even if not in aliases
                if mapped_key.isalpha() and len(mapped_key) == 1:
                    base_key = mapped_key
                else:
                    return None

        if base_key is None:
            return None

        ordered_modifiers = [m for m in modifiers_in_order if m in modifiers]
        return '+'.join(ordered_modifiers + [base_key])

    def set_trigger_key(self, key: str) -> bool:
        """
        Set the trigger key with validation.
        Returns True if successful, False if invalid key.
        """
        normalized = self.normalize_trigger_key(key)
        if not normalized:
            print(f"[ERROR] Invalid trigger key: {key}")
            return False
        if normalized == self._dictation_trigger_key:
            print("[ERROR] Trigger key cannot match dictation trigger")
            return False
        if self._clear_buffer_trigger_key and normalized == self._clear_buffer_trigger_key:
            print("[ERROR] Trigger key cannot match clear-buffer trigger")
            return False

        try:
            self._trigger_key = normalized
            print(f"[CONFIG] Trigger key changed to: {normalized.upper()}")
            print("[INFO] New trigger active immediately - no restart needed!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to set trigger key: {e}")
            return False

    def get_clear_buffer_trigger_key(self) -> str:
        return self._clear_buffer_trigger_key

    def set_clear_buffer_trigger_key(self, key: str) -> bool:
        """Set or disable the clear-buffer trigger key."""
        try:
            if not key:
                self._clear_buffer_trigger_key = ""
                print("[CONFIG] Clear-buffer trigger disabled")
                return True

            normalized = self.normalize_trigger_key(key)
            if not normalized:
                print(f"[ERROR] Invalid clear-buffer trigger: {key}")
                return False
            if normalized == self._trigger_key:
                print("[ERROR] Clear-buffer trigger cannot match the main correction trigger")
                return False
            if normalized == self._dictation_trigger_key:
                print("[ERROR] Clear-buffer trigger cannot match the dictation trigger")
                return False

            self._clear_buffer_trigger_key = normalized
            print(f"[CONFIG] Clear-buffer trigger set to: {normalized.upper()}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to set clear-buffer trigger: {e}")
            return False

    def set_versions_per_correction(self, count: int) -> bool:
        if not isinstance(count, int) or not (1 <= count <= GeminiCorrector.MAX_CANDIDATES):
            return False
        with self._lock:
            self._versions_per_correction = count
        print(f"[CONFIG] Versions per correction: {count}")
        return True
    
    def get_versions_per_correction(self) -> int:
        return self._versions_per_correction

    def get_candidate_settings(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(cfg) for cfg in self._candidate_settings]

    def set_candidate_settings(self, settings: List[Dict[str, Any]]) -> bool:
        normalized = self._prepare_candidate_settings(settings)
        with self._lock:
            self._candidate_settings = normalized
        print("[CONFIG] Candidate personalization updated:")
        for idx, cfg in enumerate(normalized, 1):
            print(
                f"         • Candidate {idx}: tone={cfg['tone']} | temperature={cfg['temperature']:.2f}"
            )
        return True

    def add_status_listener(self, listener: Callable[[bool], None]) -> None:
        """Register a callback invoked when paragraph-enabled state changes."""
        if listener not in self._status_listeners:
            self._status_listeners.append(listener)

    def attach_overlay_root(self, root: object) -> None:
        """Provide the Tk root so UI overlays can operate on the main thread."""
        try:
            self._mic_overlay.attach_root(root)
        except Exception as overlay_error:
            print(f"[WARNING] Failed to attach overlay root: {overlay_error}")

    def _on_key_event(self, event: keyboard.KeyboardEvent) -> None:
        """Handle keyboard events and suppress only when required."""
        try:
            # Only handle key DOWN events, ignore key UP events
            if event.event_type != keyboard.KEY_DOWN:
                return
            
            if not self._running or self._suppress_events:
                return

            name = event.name or ""
            
            # Check if this is our trigger combination (e.g., ctrl+space)
            is_trigger = self._is_trigger_pressed(name)
            is_clear_trigger = False
            if self._clear_buffer_trigger_key:
                is_clear_trigger = self._is_trigger_pressed(name, self._clear_buffer_trigger_key)
            
            is_dictation_trigger = False
            if self._dictation_trigger_key:
                is_dictation_trigger = self._is_trigger_pressed(name, self._dictation_trigger_key)

            # Handle dictation trigger
            if is_dictation_trigger:
                threading.Thread(target=self.toggle_dictation, daemon=True).start()
                if event and hasattr(event, "suppress_event"):
                    event.suppress_event()
                return

            if is_clear_trigger:
                threading.Thread(target=self._safe_clear_saved_paragraphs, daemon=True).start()
                if event and hasattr(event, "suppress_event"):
                    event.suppress_event()
                return
            
            # If NOT in selection mode and NOT our trigger, allow everything through
            # This ensures normal typing, Ctrl+A, Ctrl+C, Ctrl+V, etc. work perfectly
            if not self._in_selection_mode and not is_trigger:
                # Check for navigation that might desync buffer (Ctrl+Left/Right)
                is_ctrl_nav = name in ["left", "right"] and (keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"))
                
                if is_ctrl_nav:
                    # User is navigating - reset buffer but DON'T feed navigation keys to buffer
                    self._keystroke_buffer.reset_on_cursor_move()
                else:
                    # Normal typing - feed to buffer for paragraph tracking
                    self._keystroke_buffer.on_key_press(name, is_backspace=(name == 'backspace'))
                
                return
            
            # Check for navigation triggers (Ctrl+Left/Right) when IN selection mode
            is_ctrl_left = name == "left" and (keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"))
            is_ctrl_right = name == "right" and (keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"))
            
            if self._in_selection_mode and (is_ctrl_left or is_ctrl_right):
                # In selection mode - navigate candidates
                direction = 1 if is_ctrl_right else -1
                threading.Thread(target=self._safe_navigate_candidates, args=(direction,), daemon=True).start()
                if event and hasattr(event, "suppress_event"):
                    event.suppress_event()
                return
            
            # If in selection mode
            if self._in_selection_mode:
                if is_trigger:
                    # Trigger while in selection mode: accept current and trigger new correction
                    self._accept_candidate()
                    threading.Thread(target=self._safe_trigger_correction, daemon=True).start()
                    if event and hasattr(event, "suppress_event"):
                        event.suppress_event()
                    return
                else:
                    # Any other key: accept current candidate and allow key through
                    # Skip modifier keys (they don't end selection, just modify next key)
                    modifier_keys = ['shift', 'ctrl', 'alt', 'left ctrl', 'right ctrl', 
                                   'left shift', 'right shift', 'left alt', 'right alt', 
                                   'win', 'left windows', 'right windows', 'caps lock',
                                   'num lock', 'scroll lock', 'pause', 'print screen']
                    if name not in modifier_keys:
                        self._accept_candidate()
                    return
            
            # Handle trigger press (when NOT in selection mode)
            if is_trigger and self._paragraph_enabled:
                threading.Thread(target=self._safe_trigger_correction, daemon=True).start()
                if event and hasattr(event, "suppress_event"):
                    event.suppress_event()
                return
            
            # Default: allow everything through
            return
            
        except Exception as e:
            print(f"[ERROR] Key event handler crashed: {e}")
            import traceback
            traceback.print_exc()
            # Reset state on error to prevent broken state
            self._in_selection_mode = False
            self._pending_correction = False
            return
    
    def _is_trigger_pressed(self, key_name: str, trigger: Optional[str] = None) -> bool:
        """
        Check if the trigger combination is pressed.
        Supports simple keys (tab, f1) and combos (ctrl+space).
        """
        try:
            active_trigger = (trigger or self._trigger_key or "").lower()
            if not active_trigger:
                return False

            parts = [part.strip() for part in active_trigger.split('+') if part.strip()]
            if not parts:
                return False

            key = parts[-1]
            modifiers = parts[:-1]

            if key_name != key:
                return False

            if not modifiers:
                return True

            def _modifier_pressed(mod: str) -> bool:
                if mod == "ctrl":
                    return keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl")
                if mod == "alt":
                    return keyboard.is_pressed("left alt") or keyboard.is_pressed("right alt")
                if mod == "shift":
                    return keyboard.is_pressed("left shift") or keyboard.is_pressed("right shift")
                return False

            for mod in modifiers:
                if not _modifier_pressed(mod):
                    return False
            return True
            
        except Exception as e:
            print(f"[ERROR] Trigger check failed: {e}")
            return False

    def _safe_trigger_correction(self) -> None:
        """Safe wrapper for _trigger_correction with error handling."""
        try:
            self._ensure_executor()
            self._trigger_correction()
        except Exception as e:
            print(f"[ERROR] Trigger correction failed: {e}")
            import traceback
            traceback.print_exc()
            self._pending_correction = False
            self._in_selection_mode = False
    
    def _safe_clear_saved_paragraphs(self) -> None:
        """Safe wrapper to clear saved paragraphs from a background thread."""
        try:
            self.clear_saved_paragraphs()
        except Exception as e:
            print(f"[ERROR] Failed to clear saved paragraphs: {e}")
            import traceback
            traceback.print_exc()

    def _safe_navigate_candidates(self, direction: int) -> None:
        """Safe wrapper for _navigate_candidates with error handling."""
        try:
            self._navigate_candidates(direction)
        except Exception as e:
            print(f"[ERROR] Navigate candidates failed: {e}")
            import traceback
            traceback.print_exc()

    def _trigger_correction(self) -> None:
        """Trigger API correction using internal keystroke buffer."""
        # Prevent multiple simultaneous corrections
        if not self._paragraph_enabled:
            return
        
        with self._lock:
            if self._pending_correction:
                print("[DEBUG] Correction already in progress, ignoring trigger")
                return

            self._pending_correction = True
            self._current_prefix = ""
            self._current_suffix = ""
            self._current_region_original = ""
        
        try:
            print(f"\n[TRIGGER] {self._trigger_key.upper()} pressed")
            
            # STEP 1: Get text from internal buffer
            print(f"[STEP 1] Reading text from internal buffer...")
            buffer_text = self._keystroke_buffer.get_buffer()
            used_fallback = False
            control = self._last_control
            
            if not buffer_text or not buffer_text.strip():
                print("[INFO] Internal buffer empty - falling back to clipboard method")
                # Fallback: Use old method (select all + clipboard)
                try:
                    with self._suspend_events():
                        if not self._buffer_manager.select_all_text():
                            print("[ERROR] Failed to select text")
                            self._pending_correction = False
                            # Hide loading indicator on error
                            if self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                                try:
                                    self._gui_callbacks['stop_loading']()
                                except Exception:
                                    pass
                            return
                        time.sleep(0.1)
                    
                    buffer_text, control = self._buffer_manager.get_active_text()
                    self._last_control = control
                    used_fallback = True
                    
                    if not buffer_text or not buffer_text.strip():
                        print("[ERROR] No text found in buffer or clipboard")
                        self._pending_correction = False
                        # Hide loading indicator on error
                        if self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                            try:
                                self._gui_callbacks['stop_loading']()
                            except Exception:
                                pass
                        return
                except Exception as e:
                    print(f"[ERROR] Fallback method failed: {e}")
                    self._pending_correction = False
                    # Hide loading indicator on error
                    if self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                        try:
                            self._gui_callbacks['stop_loading']()
                        except Exception:
                            pass
                    return
            
            buffer_segment = buffer_text or ""
            if self._accepted_text_accumulator:
                if buffer_segment.startswith(self._accepted_text_accumulator):
                    full_text = buffer_segment
                else:
                    full_text = f"{self._accepted_text_accumulator}{buffer_segment}"
            else:
                full_text = buffer_segment
            
            self._last_input_snapshot = full_text
            preview_for_log = full_text.strip() or full_text
            preview_snippet = preview_for_log[:80]
            if len(preview_for_log) > 80:
                preview_snippet += "..."
            print(f"[SUCCESS] Got text from buffer ({len(full_text)} chars): '{preview_snippet}'")
            
            # Validate text length
            if len(full_text) > 10000:
                print("[ERROR] Text too long (max 10,000 chars)")
                self._pending_correction = False
                # Hide loading indicator on error
                if self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                    try:
                        self._gui_callbacks['stop_loading']()
                    except Exception:
                        pass
                return
            
            # STEP 2: Get delta (new text since baseline)
            region_to_refine = self._get_delta(full_text)
            self._current_region_original = region_to_refine
            self._last_region_snapshot = region_to_refine
            region_payload = region_to_refine.strip()
            self._last_requested_region = region_payload
            if region_to_refine:
                prefix_len = full_text.rfind(region_to_refine)
                if prefix_len == -1:
                    prefix_len = max(0, len(full_text) - len(region_to_refine))
            else:
                prefix_len = len(full_text)
            suffix_start = min(len(full_text), prefix_len + len(region_to_refine))
            self._current_prefix = full_text[:prefix_len]
            self._current_suffix = full_text[suffix_start:]
            
            if not region_payload:
                print("[DEBUG] No new text to refine")
                self._pending_correction = False
                self._current_prefix = ""
                self._current_suffix = ""
                self._current_region_original = ""
                # Hide loading indicator
                if self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                    try:
                        self._gui_callbacks['stop_loading']()
                    except Exception:
                        pass
                return
            
            payload_preview = region_payload[:80]
            if len(region_payload) > 80:
                payload_preview += "..."
            print(f"[STEP 2] Sending to API ({len(region_payload)} chars): '{payload_preview}'")
            
            # STEP 3: Generate candidates via API
            num_versions = self._versions_per_correction
            print(f"[STEP 3] Requesting {num_versions} correction versions from Gemini...")
            
            # Show loading indicator (check if service is still running)
            if self._running and self._gui_callbacks and 'start_loading' in self._gui_callbacks:
                try:
                    self._gui_callbacks['start_loading']()
                except Exception:
                    pass
            
            try:
                if self._executor is None:
                    raise RuntimeError("Correction executor not available")
                candidate_payload = [dict(cfg) for cfg in self._candidate_settings[:num_versions]]
                future = self._executor.submit(
                    self._corrector.cleanup_paragraph,
                    region_payload,
                    num_versions,
                    candidate_payload,
                )
                future.add_done_callback(lambda f: self._store_and_show_candidates(f, full_text))
            except Exception as e:
                print(f"[ERROR] Failed to submit API request: {e}")
                # Hide loading indicator on error (check if service is still running)
                if self._running and self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
                    try:
                        self._gui_callbacks['stop_loading']()
                    except Exception:
                        pass
                self._pending_correction = False
                self._current_prefix = ""
                self._current_suffix = ""
                self._current_region_original = ""
                return
            
        except Exception as e:
            print(f"[ERROR] Trigger failed: {e}")
            import traceback
            traceback.print_exc()
            self._pending_correction = False
            self._current_prefix = ""
            self._current_suffix = ""
            self._current_region_original = ""

    def _ensure_executor(self) -> None:
        """Ensure the background executor exists before scheduling work."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correction")

    def _get_delta(self, full_text: str) -> str:
        """Get new text since baseline."""
        if not self._baseline_text:
            return full_text
        
        if full_text.startswith(self._baseline_text):
            delta = full_text[len(self._baseline_text):]
            if delta:
                trimmed = delta.strip()
                if trimmed:
                    print(f"[DELTA] Baseline: {len(self._baseline_text)} chars | New: {len(trimmed)} chars")
                return delta
            return ""
        else:
            print(f"[DELTA] Baseline changed - refining all")
            self._baseline_text = ""
            return full_text

    def _prepare_candidate_preview(self, candidate: str) -> tuple[str, str]:
        """Combine the candidate with the original whitespace context."""
        region_original = self._current_region_original or ""
        prefix = self._current_prefix or ""
        suffix = self._current_suffix or ""
        leading_len = len(region_original) - len(region_original.lstrip())
        trailing_len = len(region_original) - len(region_original.rstrip())
        leading_ws = region_original[:leading_len] if leading_len > 0 else ""
        trailing_ws = region_original[len(region_original) - trailing_len:] if trailing_len > 0 else ""

        replacement = f"{leading_ws}{candidate}{trailing_ws}"
        new_text = f"{prefix}{replacement}{suffix}"
        return replacement, new_text

    def _store_and_show_candidates(self, future: Future, original_full_text: str) -> None:
        """Store candidates and immediately show first one."""
        # Hide loading indicator (check if service is still running)
        if self._running and self._gui_callbacks and 'stop_loading' in self._gui_callbacks:
            try:
                self._gui_callbacks['stop_loading']()
            except Exception:
                pass
        
        try:
            # The callback is invoked when future is done; fetch result directly
            try:
                candidates = future.result()
            except Exception as api_error:
                print(f"[ERROR] API request failed: {api_error}")
                with self._lock:
                    self._pending_correction = False
                    self._in_selection_mode = False
                    self._current_prefix = ""
                    self._current_suffix = ""
                    self._current_region_original = ""
                    self._last_region_snapshot = ""
                    self._last_requested_region = ""
                    self._last_preview_text = ""
                return
            
            if not candidates or not isinstance(candidates, list):
                print("[ERROR] No valid candidates returned from API")
                with self._lock:
                    self._pending_correction = False
                    self._in_selection_mode = False
                    self._current_prefix = ""
                    self._current_suffix = ""
                    self._current_region_original = ""
                    self._last_region_snapshot = ""
                    self._last_requested_region = ""
                    self._last_preview_text = ""
                return
            
            # Filter out empty candidates and duplicates
            seen = set()
            unique_candidates = []
            for c in candidates:
                if c and c.strip() and c.strip() not in seen:
                    unique_candidates.append(c.strip())
                    seen.add(c.strip())
            
            candidates = unique_candidates
            
            if not candidates:
                print("[ERROR] All candidates were empty or duplicates")
                with self._lock:
                    self._pending_correction = False
                    self._in_selection_mode = False
                    self._current_prefix = ""
                    self._current_suffix = ""
                    self._current_region_original = ""
                    self._last_region_snapshot = ""
                    self._last_requested_region = ""
                    self._last_preview_text = ""
                return
            
            print(f"[API] ✓ Received {len(candidates)} unique candidates")
            for idx, cand in enumerate(candidates, 1):
                print(f"[API]   {idx}. '{cand[:60]}{'...' if len(cand) > 60 else ''}'")
            
            # Store candidates with lock
            with self._lock:
                self._current_candidates = candidates
                self._current_candidate_index = 0
                self._in_selection_mode = True
                self._pending_correction = False
            
            # Show first candidate immediately
            self._show_candidate(0)
            
            print(f"[SELECT] Showing candidate 1/{len(candidates)}")
            print(f"[SELECT] Press Ctrl+Arrow to navigate, any key to accept")
            
        except Exception as e:
            print(f"[ERROR] Failed to process candidates: {e}")
            import traceback
            traceback.print_exc()
            # Exit selection mode on error with lock
            with self._lock:
                self._pending_correction = False
                self._in_selection_mode = False
                self._current_candidates = []
                self._current_prefix = ""
                self._current_suffix = ""
                self._current_region_original = ""
                self._last_region_snapshot = ""
                self._last_requested_region = ""
                self._last_preview_text = ""

    def _show_candidate(self, index: int) -> None:
        """Display a candidate by replacing text with error handling."""
        try:
            if not self._current_candidates or index >= len(self._current_candidates):
                return
            
            candidate = self._current_candidates[index]
            _, new_text = self._prepare_candidate_preview(candidate)
            
            print(f"\n[REPLACING] Candidate {index + 1}/{len(self._current_candidates)}")
            print(f"[REPLACING] Text: '{new_text[:100]}{'...' if len(new_text) > 100 else ''}'")
            
            # Replace text (this will select all and paste)
            with self._suspend_events():
                success = self._buffer_manager.set_active_text(new_text, self._last_control)
                
                if success:
                    self._last_preview_text = new_text
                    print(f"[SUCCESS] ✓ Text replaced in your window!")
                    print(f"[SUCCESS] ✓ Displayed candidate {index + 1}/{len(self._current_candidates)}")
                    
                    # IMPORTANT: Update internal buffer to stay in sync
                    self._keystroke_buffer.set_buffer(new_text)
                else:
                    print(f"[ERROR] ✗ Failed to replace text in window")
                    print(f"[HELP] Try manually selecting all text (Ctrl+A) and press TAB again")
        except Exception as e:
            print(f"[ERROR] Show candidate failed: {e}")
            import traceback
            traceback.print_exc()

    def _navigate_candidates(self, direction: int) -> None:
        """Navigate between candidates (only in selection mode)."""
        with self._lock:
            if not self._in_selection_mode or not self._current_candidates:
                print(f"[WARN] Cannot navigate - selection_mode: {self._in_selection_mode}, candidates: {len(self._current_candidates) if self._current_candidates else 0}")
                return
            
            # Cycle through candidates
            self._current_candidate_index = (self._current_candidate_index + direction) % len(self._current_candidates)
            candidate_num = self._current_candidate_index + 1
            total = len(self._current_candidates)
        
        print(f"\n[NAVIGATE] → Switching to candidate {candidate_num}/{total}")
        
        self._show_candidate(self._current_candidate_index)

    def _accept_candidate(self) -> None:
        """Accept current candidate and exit selection mode."""
        with self._lock:
            if not self._in_selection_mode:
                return
            
            if not self._current_candidates:
                print("[WARN] No candidates to accept")
                self._in_selection_mode = False
                return
            
            candidate = self._current_candidates[self._current_candidate_index]
            candidate_num = self._current_candidate_index + 1
        
        try:
            final_text = self._last_preview_text
            if not final_text:
                _, final_text = self._prepare_candidate_preview(candidate)

            # Save to history with accurate original text
            if self._history_manager:
                original_segment = self._current_region_original or self._last_region_snapshot or self._last_requested_region or candidate
                original = original_segment.strip()
                self._history_manager.add_correction(
                    original=original,
                    corrected=candidate,
                    selected_version=candidate_num,
                    total_versions=len(self._current_candidates)
                )
            
            with self._lock:
                self._baseline_text = final_text
                self._last_input_snapshot = final_text
                self._accepted_text_accumulator = final_text
                
                # Reset region tracking after acceptance
                self._last_region_snapshot = ""
                self._last_requested_region = ""
                self._last_preview_text = ""
                self._current_prefix = ""
                self._current_suffix = ""
                self._current_region_original = ""
                
                # Exit selection mode
                self._in_selection_mode = False
                self._current_candidates = []
                self._current_candidate_index = 0
            
            # CRITICAL: Clear internal buffer after acceptance
            # User will continue typing fresh text after correction
            self._keystroke_buffer.clear_buffer()
            
            print(f"[ACCEPT] ✓ Accepted candidate {candidate_num}")
            print(f"[ACCEPT] New baseline: {len(self._baseline_text)} chars")
            print(f"[ACCEPT] Buffer cleared - ready for new input")
            
        except Exception as e:
            print(f"[ERROR] Failed to accept candidate: {e}")
            import traceback
            traceback.print_exc()
            # Exit selection mode on error with lock
            with self._lock:
                self._in_selection_mode = False
                self._current_candidates = []
                self._current_candidate_index = 0
                self._current_prefix = ""
                self._current_suffix = ""
                self._current_region_original = ""
                self._last_region_snapshot = ""
                self._last_requested_region = ""
                self._last_preview_text = ""
    
    def _get_original_text_for_history(self) -> str:
        """Get the original text that was corrected."""
        if self._current_region_original:
            return self._current_region_original.strip()
        if self._last_requested_region:
            return self._last_requested_region
        if self._last_region_snapshot:
            return self._last_region_snapshot.strip()
        if hasattr(self._buffer_manager, '_last_text'):
            return self._buffer_manager._last_text
        return ""

    def clear_saved_paragraphs(self) -> None:
        """Clear accumulated accepted text and reset incremental state."""
        with self._lock:
            self._accepted_text_accumulator = ""
            self._baseline_text = ""
            self._last_input_snapshot = ""
            self._last_region_snapshot = ""
            self._last_requested_region = ""
            self._last_preview_text = ""
            self._current_prefix = ""
            self._current_suffix = ""
            self._current_region_original = ""
            self._pending_correction = False
            self._in_selection_mode = False
            self._current_candidates = []
            self._current_candidate_index = 0
            self._keystroke_buffer.clear_buffer()
            print("[CONFIG] Saved paragraph buffer cleared")

    # ==================== DICTATION METHODS ====================
    
    def get_dictation_trigger_key(self) -> str:
        """Get the current dictation trigger key."""
        return self._dictation_trigger_key
    
    def set_dictation_trigger_key(self, key: str) -> bool:
        """Set the dictation trigger key with validation."""
        if not key:
            print("[ERROR] Dictation trigger cannot be empty")
            return False
        
        normalized = self.normalize_trigger_key(key)
        if not normalized:
            print(f"[ERROR] Invalid dictation trigger: {key}")
            return False

        # Ensure no conflicts with other triggers
        if normalized == self._trigger_key:
            print("[ERROR] Dictation trigger cannot match correction trigger")
            return False

        if self._clear_buffer_trigger_key and normalized == self._clear_buffer_trigger_key:
            print("[ERROR] Dictation trigger cannot match clear-buffer trigger")
            return False

        try:
            self._dictation_trigger_key = normalized
            print(f"[CONFIG] Dictation trigger set to: {normalized.upper()}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to set dictation trigger: {e}")
            return False
    
    def is_dictation_active(self) -> bool:
        """Check if dictation is currently active."""
        return self._dictation_manager.is_active()
    
    def toggle_dictation(self) -> None:
        """Toggle dictation on/off."""
        if self._dictation_manager.is_active():
            self.stop_dictation()
        else:
            self.start_dictation()
    
    def start_dictation(self) -> bool:
        """Start listening for speech input."""
        print("[DICTATION] Starting...")
        success = self._dictation_manager.start_listening()
        if success:
            self._mic_overlay.show()
            print("[DICTATION] Active - speak now")
        else:
            print("[DICTATION] Failed to start")
        return success
    
    def stop_dictation(self) -> None:
        """Stop listening for speech input."""
        print("[DICTATION] Stopping...")
        self._dictation_manager.stop_listening()
        self._mic_overlay.hide()
        print("[DICTATION] Stopped")
    
    def _setup_dictation_callbacks(self) -> None:
        """Set up callbacks for dictation events."""
        self._dictation_manager.on_text_recognized = self._on_dictation_text
        self._dictation_manager.on_listening_started = lambda: print("[DICTATION] Mic active")
        self._dictation_manager.on_listening_stopped = lambda: print("[DICTATION] Mic inactive")
        self._dictation_manager.on_error = self._on_dictation_error
    
    def _on_dictation_text(self, text: str) -> None:
        """Handle recognized text from dictation."""
        if not text or not text.strip():
            return
        
        print(f"[DICTATION] Typing: '{text}'")
        
        try:
            # Type the recognized text
            with self._suspend_events():
                time.sleep(0.1)
                keyboard.write(text)
                time.sleep(0.1)
            
            # Add to keystroke buffer for correction tracking
            self._keystroke_buffer.add_text(text)
            
            print(f"[DICTATION] ✓ Typed {len(text)} characters")
            
        except Exception as e:
            print(f"[DICTATION] Failed to type text: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_dictation_error(self, error_msg: str) -> None:
        """Handle dictation errors."""
        print(f"[DICTATION ERROR] {error_msg}")
        # Auto-stop on fatal errors
        if "fatal" in error_msg.lower() or "microphone" in error_msg.lower():
            self.stop_dictation()

    @contextmanager
    def _suspend_events(self):
        """Suspend keyboard event processing."""
        self._suppress_events = True
        try:
            yield
        finally:
            time.sleep(0.05)
            self._suppress_events = False
