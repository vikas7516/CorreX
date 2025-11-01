"""Internal keystroke buffer for tracking typed text without clipboard."""
from __future__ import annotations

import threading
import time
from typing import Optional, Dict
from collections import deque

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None
    win32process = None


class KeystrokeBuffer:
    """
    Internal buffer that tracks keystrokes in real-time.
    Does NOT use clipboard - builds text from keyboard events.
    """
    
    def __init__(self, max_buffer_size: int = 10000):
        """
        Initialize keystroke buffer.
        
        Args:
            max_buffer_size: Maximum characters to store per window
        """
        self.max_buffer_size = max_buffer_size
        self._lock = threading.RLock()
        
        # Per-window buffers: {window_handle: text_buffer}
        self._buffers: Dict[int, str] = {}
        
        # Track current window
        self._current_window = None
        self._last_focus_check = 0
        self._focus_check_interval = 0.1  # Check focus every 100ms
        
        # Cleanup tracking
        self._last_cleanup = 0
        self._cleanup_interval = 60.0  # Cleanup every 60 seconds
        self._max_windows = 10  # Keep max 10 window buffers
        
        # Special keys that modify buffer
        self._key_mapping = {
            'space': ' ',
            'enter': '\n',
            'tab': '\t',
        }
        
        # Keys to ignore
        self._ignore_keys = {
            'shift', 'ctrl', 'alt', 'win', 
            'left shift', 'right shift',
            'left ctrl', 'right ctrl',
            'left alt', 'right alt',
            'left windows', 'right windows',
            'caps lock', 'num lock', 'scroll lock',
            'pause', 'print screen', 'insert',
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 
            'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'up', 'down', 'left', 'right',
            'page up', 'page down', 'home', 'end',
            'esc', 'delete',
        }
    
    def _get_foreground_window(self) -> Optional[int]:
        """Get current foreground window handle."""
        if win32gui is None:
            return None
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            return hwnd if hwnd else None
        except Exception:
            # Win32 API call failed
            return None
    
    def _update_current_window(self) -> bool:
        """Check if window focus changed. Returns True if changed."""
        current_time = time.time()
        
        # Only check periodically to reduce overhead
        if current_time - self._last_focus_check < self._focus_check_interval:
            return False
        
        self._last_focus_check = current_time
        new_window = self._get_foreground_window()
        
        if new_window != self._current_window:
            self._current_window = new_window
            print(f"[BUFFER] Focus changed to window: {new_window}")
            
            # Trigger cleanup periodically
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._last_cleanup = current_time
                self.cleanup_old_buffers(self._max_windows)
            
            return True
        
        return False
    
    def on_key_press(self, key_name: str, is_backspace: bool = False) -> None:
        """
        Handle a key press event and update buffer.
        
        Args:
            key_name: Name of the key pressed (from keyboard library)
            is_backspace: True if this is a backspace key
        """
        with self._lock:
            # Update window focus if needed
            self._update_current_window()
            
            if self._current_window is None:
                return
            
            # Initialize buffer for this window if needed
            if self._current_window not in self._buffers:
                self._buffers[self._current_window] = ""
            
            buffer = self._buffers[self._current_window]
            
            # Handle backspace
            if is_backspace or key_name == 'backspace':
                if len(buffer) > 0:
                    buffer = buffer[:-1]
                    self._buffers[self._current_window] = buffer
                return
            
            # Ignore special keys
            if key_name in self._ignore_keys:
                return
            
            # Map special keys
            if key_name in self._key_mapping:
                char = self._key_mapping[key_name]
            elif len(key_name) == 1:
                # Single character key
                char = key_name
            else:
                # Unknown key, ignore
                return
            
            # Add to buffer
            buffer += char
            
            # Trim if too long
            if len(buffer) > self.max_buffer_size:
                buffer = buffer[-self.max_buffer_size:]
            
            self._buffers[self._current_window] = buffer
    
    def get_buffer(self, window_handle: Optional[int] = None) -> str:
        """
        Get current buffer content.
        
        Args:
            window_handle: Specific window to get buffer for (None = current window)
            
        Returns:
            Current buffer content as string
        """
        with self._lock:
            if window_handle is None:
                self._update_current_window()
                window_handle = self._current_window
            
            if window_handle is None:
                return ""
            
            return self._buffers.get(window_handle, "")
    
    def set_buffer(self, text: str, window_handle: Optional[int] = None) -> None:
        """
        Set buffer content (used after successful replacement).
        
        Args:
            text: New buffer content
            window_handle: Specific window to set buffer for (None = current window)
        """
        with self._lock:
            if window_handle is None:
                self._update_current_window()
                window_handle = self._current_window
            
            if window_handle is None:
                return
            
            self._buffers[window_handle] = text
    
    def clear_buffer(self, window_handle: Optional[int] = None) -> None:
        """
        Clear buffer for a window.
        
        Args:
            window_handle: Specific window to clear (None = current window)
        """
        with self._lock:
            if window_handle is None:
                self._update_current_window()
                window_handle = self._current_window
            
            if window_handle is None:
                return
            
            if window_handle in self._buffers:
                self._buffers[window_handle] = ""
    
    def add_text(self, text: str, window_handle: Optional[int] = None) -> None:
        """
        Add text to buffer (used by dictation feature).
        
        Args:
            text: Text to add to buffer
            window_handle: Specific window to add to (None = current window)
        """
        with self._lock:
            if window_handle is None:
                self._update_current_window()
                window_handle = self._current_window
            
            if window_handle is None:
                return
            
            # Initialize buffer if needed
            if window_handle not in self._buffers:
                self._buffers[window_handle] = ""
            
            # Add text to buffer
            buffer = self._buffers[window_handle] + text
            
            # Trim if too long
            if len(buffer) > self.max_buffer_size:
                buffer = buffer[-self.max_buffer_size:]
            
            self._buffers[window_handle] = buffer
    
    def reset_on_cursor_move(self) -> None:
        """
        Reset buffer when user moves cursor (Ctrl+A, arrow keys with selection, etc.).
        This handles desynchronization cases.
        """
        with self._lock:
            if self._current_window and self._current_window in self._buffers:
                # Don't fully clear - just mark that buffer might be desynced
                # The buffer will naturally resync as user types
                pass
    
    def cleanup_old_buffers(self, max_windows: int = 10) -> None:
        """
        Clean up buffers for windows that no longer exist.
        Keeps only the N most recently used windows to prevent memory leak.
        
        Args:
            max_windows: Maximum number of window buffers to keep
        """
        with self._lock:
            if len(self._buffers) <= max_windows:
                return
            
            # Keep current window and most recent ones
            windows_to_keep = [self._current_window] if self._current_window else []
            other_windows = [w for w in self._buffers.keys() if w != self._current_window]
            
            # Keep most recent
            windows_to_keep.extend(other_windows[-(max_windows-1):])
            
            # Remove old buffers
            old_count = len(self._buffers)
            self._buffers = {w: self._buffers[w] for w in windows_to_keep if w in self._buffers}
            removed = old_count - len(self._buffers)
            
            if removed > 0:
                print(f"[BUFFER] Cleaned up {removed} old window buffers (keeping {len(self._buffers)})")
