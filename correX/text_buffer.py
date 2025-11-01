"""Cross-application text buffer manipulation using Windows APIs."""
from __future__ import annotations

import time
from typing import Optional, Tuple

MAX_CLIPBOARD_RETRIES = 5
CLIPBOARD_RETRY_DELAY = 0.05

try:
    import win32gui
    import win32con
    import win32api
    import win32clipboard
    from pywinauto import Desktop
    from pywinauto.controls.win32_controls import EditWrapper
    from pywinauto.controls.uiawrapper import UIAWrapper
except ImportError:
    win32gui = None
    win32con = None  # type: ignore[assignment]
    win32api = None  # type: ignore[assignment]
    win32clipboard = None  # type: ignore[assignment]
    Desktop = None  # type: ignore[assignment]
    EditWrapper = None  # type: ignore[assignment]
    UIAWrapper = None  # type: ignore[assignment]
    print("[ERROR] pywin32 not installed. Run: pip install pywin32 pywinauto")


class TextBufferManager:
    """Manages direct text buffer access across different Windows applications."""

    def __init__(self):
        """Initialize the text buffer manager."""
        self._last_hwnd = None
        self._last_text = ""

    def select_all_text(self) -> bool:
        """
        Select all text in the currently active text control AND copy to clipboard.
        This should be called BEFORE getting text.
        
        Returns:
            True if successful, False otherwise
        """
        if win32gui is None or win32api is None or win32con is None:
            return False
        
        try:
            # CRITICAL: Save window handle for focus restoration
            current_hwnd = win32gui.GetForegroundWindow()
            focused_control = win32gui.GetFocus()
            
            # Send Ctrl+A to select all text
            print(f"[DEBUG] Sending Ctrl+A to select all text...")
            self._send_keystroke(win32con.VK_CONTROL, ord('A'))
            
            # Now copy it to clipboard (Ctrl+C)
            print(f"[DEBUG] Sending Ctrl+C to copy text...")
            self._send_keystroke(win32con.VK_CONTROL, ord('C'))
            time.sleep(0.05)
            
            # Restore focus immediately
            try:
                if current_hwnd and win32gui.IsWindow(current_hwnd):
                    win32gui.SetForegroundWindow(current_hwnd)
                    if focused_control and win32gui.IsWindow(focused_control):
                        win32gui.SetFocus(focused_control)
            except Exception as focus_error:
                print(f"[WARNING] Could not restore focus after copy: {focus_error}")
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to select all text: {e}")
            return False

    def get_active_text(self) -> Tuple[Optional[str], Optional[any]]:
        """
        Get text from the currently active text control.
        Assumes text was already selected and copied by select_all_text().
        
        Returns:
            Tuple of (text_content, control_handle)
            Returns (None, None) if text cannot be retrieved.
        """
        if win32gui is None:
            return None, None

        try:
            # Get foreground window
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None
            
            # Validate window handle is still valid
            if not win32gui.IsWindow(hwnd):
                print(f"[WARNING] Window handle {hwnd} is no longer valid")
                return None, None

            # PRIMARY: Read from clipboard (should already be there from select_all_text)
            text = self._get_clipboard_text()
            if text and text.strip() and not self._looks_like_window_title(text):
                print(f"[DEBUG] Got text from clipboard ({len(text)} chars)")
                self._last_hwnd = hwnd
                self._last_text = text
                return text, hwnd
            
            # FALLBACK: Try other methods if clipboard didn't work
            print(f"[DEBUG] Clipboard empty, trying other methods...")
            text, control = self._try_get_text_multiple_methods(hwnd)
            
            if text is not None:
                self._last_hwnd = hwnd
                self._last_text = text
                return text, control
            
            return None, None

        except Exception as e:
            print(f"[ERROR] Failed to get active text: {e}")
            return None, None

    def set_active_text(self, text: str, control: Optional[any] = None) -> bool:
        """
        Set text in the currently active text control.
        Uses clipboard method as primary (most reliable across all apps).
        
        Args:
            text: The new text content
            control: Optional control handle from get_active_text()
            
        Returns:
            True if successful, False otherwise
        """
        if win32gui is None:
            return False

        try:
            print(f"[REPLACE] Starting text replacement ({len(text)} chars)...")
            
            # Validate window is still valid if control is a window handle
            if isinstance(control, int) and not win32gui.IsWindow(control):
                print(f"[WARNING] Window handle {control} is no longer valid, trying foreground window")
                control = None
            
            # PRIMARY METHOD: Clipboard paste (most reliable, works everywhere)
            # This is what Windows autocorrect actually uses
            if self._set_text_via_clipboard(text):
                return True
            
            # FALLBACK 1: Try UI Automation
            print(f"[REPLACE] Clipboard failed, trying UI Automation...")
            if self._set_text_via_uiautomation(text):
                print(f"[REPLACE] ✓ Text replaced via UI Automation")
                return True

            # FALLBACK 2: Try control handle if provided
            if control is not None:
                print(f"[REPLACE] UI Automation failed, trying control handle...")
                if self._set_text_via_control(control, text):
                    print(f"[REPLACE] ✓ Text replaced via control")
                    return True

            # FALLBACK 3: Try direct Win32 API
            print(f"[REPLACE] Control failed, trying Win32 API...")
            hwnd = win32gui.GetForegroundWindow()
            if hwnd and win32gui.IsWindow(hwnd):
                if self._set_text_via_win32(hwnd, text):
                    print(f"[REPLACE] ✓ Text replaced via Win32")
                    return True

            print(f"[ERROR] ✗ All text replacement methods failed!")
            return False

        except Exception as e:
            print(f"[ERROR] Failed to set active text: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _try_get_text_multiple_methods(self, hwnd: int) -> Tuple[Optional[str], Optional[any]]:
        """Try multiple methods to retrieve text from active control."""
        
        # Method 1: Try UI Automation first (most reliable, non-invasive)
        text, control = self._get_text_via_pywinauto(hwnd)
        if text and len(text.strip()) > 0 and not self._looks_like_window_title(text):
            return text, control

        # Method 2: Try Direct Win32 API (fast, non-invasive but may get window titles)
        text = self._get_text_via_win32(hwnd)
        if text and len(text.strip()) > 0 and not self._looks_like_window_title(text):
            return text, hwnd

        # Method 3: Try clipboard as last resort (invasive - modifies clipboard)
        text = self._get_text_via_clipboard()
        if text and len(text.strip()) > 0 and not self._looks_like_window_title(text):
            return text, None

        return None, None
    
    def _looks_like_window_title(self, text: str) -> bool:
        """Check if text looks like a window title rather than content."""
        if not text:
            return False
        
        # Window titles typically:
        # 1. End with " - AppName" pattern
        # 2. Are shorter than 100 chars
        # 3. Don't contain newlines
        # 4. May contain special window title patterns
        
        if len(text) < 100 and "\n" not in text:
            # Check for common window title patterns
            title_patterns = [" - Notepad", " - Word", " - Chrome", " - Firefox", 
                            " - Microsoft", "*" + text[-10:], "Untitled"]
            for pattern in title_patterns:
                if pattern in text:
                    return True
        
        return False

    def _get_text_via_win32(self, hwnd: int) -> Optional[str]:
        """Get text using Win32 GetWindowText (works for Edit controls)."""
        try:
            # Try getting text from the window itself
            length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
            if length > 0:
                # Create buffer for Unicode text (2 bytes per character + null terminator)
                buffer = win32gui.PyMakeBuffer((length + 1) * 2)
                result = win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
                if result > 0:
                    # Properly decode the buffer
                    text = buffer[:result * 2].tobytes().decode('utf-16-le', errors='ignore')
                    if text.strip():
                        return text

            # Try focused child control
            focused_hwnd = win32gui.GetFocus()
            if focused_hwnd and focused_hwnd != hwnd:
                length = win32gui.SendMessage(focused_hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
                if length > 0:
                    # Create buffer for Unicode text (2 bytes per character + null terminator)
                    buffer = win32gui.PyMakeBuffer((length + 1) * 2)
                    result = win32gui.SendMessage(focused_hwnd, win32con.WM_GETTEXT, length + 1, buffer)
                    if result > 0:
                        # Properly decode the buffer
                        text = buffer[:result * 2].tobytes().decode('utf-16-le', errors='ignore')
                        if text.strip():
                            return text

        except Exception as e:
            print(f"[DEBUG] Win32 getText failed: {e}")
        
        return None

    def _get_text_via_pywinauto(self, hwnd: int) -> Tuple[Optional[str], Optional[any]]:
        """Get text using pywinauto (works for complex controls)."""
        try:
            from pywinauto.application import Application
            
            app = Application(backend="uia").connect(handle=hwnd, timeout=1)
            window = app.window(handle=hwnd)
            
            # Try to find focused edit control
            try:
                focused = window.descendants(control_type="Edit", depth=10)
                for edit in focused:
                    try:
                        text = edit.window_text()
                        if text and len(text.strip()) > 0:
                            return text, edit
                    except Exception:
                        # Skip controls that can't be read
                        continue
            except Exception:
                # If we can't enumerate descendants, try main window
                pass

            # Try to get text from main window
            try:
                text = window.window_text()
                if text and len(text.strip()) > 0:
                    return text, window
            except Exception:
                # Main window text not accessible
                pass

        except Exception as e:
            print(f"[DEBUG] pywinauto getText failed: {e}")
        
        return None, None

    def _get_text_via_clipboard(self) -> Optional[str]:
        """Get text by selecting all and copying to clipboard."""
        try:
            # Save current clipboard
            original_clipboard = self._get_clipboard_text()

            # Select all and copy (Ctrl+A, Ctrl+C)
            self._send_keystroke(win32con.VK_CONTROL if win32con else 0, ord('A'))
            time.sleep(0.05)

            self._send_keystroke(win32con.VK_CONTROL if win32con else 0, ord('C'))
            time.sleep(0.05)

            # Get clipboard text
            text = self._get_clipboard_text()

            # Restore original clipboard
            if original_clipboard is not None:
                self._set_clipboard_text(original_clipboard)

            return text if text and text != original_clipboard else None

        except Exception as e:
            print(f"[DEBUG] Clipboard getText failed: {e}")

        return None

    def _set_text_via_control(self, control: any, text: str) -> bool:
        """Set text using control handle."""
        try:
            if hasattr(control, 'set_text'):
                control.set_text(text)
                return True
            elif hasattr(control, 'SetWindowText'):
                control.SetWindowText(text)
                return True
        except Exception as e:
            print(f"[DEBUG] Control setText failed: {e}")
        
        return False

    def _set_text_via_win32(self, hwnd: int, text: str) -> bool:
        """Set text using Win32 SetWindowText."""
        try:
            # Try main window
            win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, text)
            
            # Verify it worked
            time.sleep(0.01)
            length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
            if length > 0:
                return True

            # Try focused control
            focused_hwnd = win32gui.GetFocus()
            if focused_hwnd and focused_hwnd != hwnd:
                win32gui.SendMessage(focused_hwnd, win32con.WM_SETTEXT, 0, text)
                time.sleep(0.01)
                length = win32gui.SendMessage(focused_hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
                if length > 0:
                    return True

        except Exception as e:
            print(f"[DEBUG] Win32 setText failed: {e}")
        
        return False

    def _set_text_via_uiautomation(self, text: str) -> bool:
        """Set text using UI Automation."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            from pywinauto.application import Application
            
            app = Application(backend="uia").connect(handle=hwnd, timeout=1)
            window = app.window(handle=hwnd)
            
            # Find focused edit control
            focused = window.descendants(control_type="Edit", depth=10)
            for edit in focused:
                try:
                    edit.set_text(text)
                    return True
                except Exception:
                    # Skip controls that can't be set
                    continue

        except Exception as e:
            print(f"[DEBUG] UI Automation setText failed: {e}")
        
        return False

    def _set_text_via_clipboard(self, text: str) -> bool:
        """Set text by pasting from clipboard (most reliable, works everywhere)."""
        if win32gui is None or win32api is None or win32con is None or win32clipboard is None:
            return False

        try:
            # CRITICAL: Save the current window handle to restore focus
            current_hwnd = win32gui.GetForegroundWindow()
            focused_control = win32gui.GetFocus()
            
            print(f"[CLIPBOARD] Saving original clipboard...")
            
            # Save current clipboard
            original_clipboard = self._get_clipboard_text()
            
            # Set clipboard to new text
            print(f"[CLIPBOARD] Setting new text to clipboard...")
            if not self._set_clipboard_text(text):
                print(f"[ERROR] Failed to set clipboard")
                return False
            
            # Small delay to ensure clipboard is set
            time.sleep(0.03)
            
            # Select all text first (to ensure we replace everything)
            print(f"[CLIPBOARD] Selecting all text (Ctrl+A)...")
            self._send_keystroke(win32con.VK_CONTROL if win32con else 0, ord('A'))
            time.sleep(0.05)

            # Now paste with Ctrl+V
            print(f"[CLIPBOARD] Pasting corrected text (Ctrl+V)...")
            self._send_keystroke(win32con.VK_CONTROL if win32con else 0, ord('V'))
            
            # Wait for paste to complete
            time.sleep(0.08)
            
            # CRITICAL: Restore focus to original window/control
            try:
                if current_hwnd and win32gui.IsWindow(current_hwnd):
                    win32gui.SetForegroundWindow(current_hwnd)
                    if focused_control and win32gui.IsWindow(focused_control):
                        win32gui.SetFocus(focused_control)
            except Exception as focus_error:
                print(f"[WARNING] Could not restore focus: {focus_error}")
            
            # Restore original clipboard
            print(f"[CLIPBOARD] Restoring original clipboard...")
            if original_clipboard is not None:
                self._set_clipboard_text(original_clipboard)
            
            print(f"[CLIPBOARD] ✓ Text replacement completed!")
            return True

        except Exception as e:
            print(f"[ERROR] Clipboard setText failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_clipboard_text(self) -> Optional[str]:
        """Get text from Windows clipboard."""
        if win32clipboard is None or win32con is None:
            return None

        for attempt in range(MAX_CLIPBOARD_RETRIES):
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as clipboard_error:
                print(f"[DEBUG] Clipboard read attempt {attempt + 1} failed: {clipboard_error}")
                time.sleep(CLIPBOARD_RETRY_DELAY)
        return None

    def _set_clipboard_text(self, text: str) -> bool:
        """Set text to Windows clipboard."""
        if win32clipboard is None or win32con is None:
            return False

        for attempt in range(MAX_CLIPBOARD_RETRIES):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                    return True
                finally:
                    win32clipboard.CloseClipboard()
            except Exception as clipboard_error:
                print(f"[ERROR] Failed to set clipboard (attempt {attempt + 1}): {clipboard_error}")
                time.sleep(CLIPBOARD_RETRY_DELAY)
        return False

    def _send_keystroke(self, modifier: int, keycode: int) -> None:
        """Send a modifier+key keystroke with basic error handling."""
        if win32api is None or win32con is None:
            return

        try:
            win32api.keybd_event(modifier, 0, 0, 0)
            win32api.keybd_event(keycode, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(keycode, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(modifier, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[WARNING] Failed to send keystroke {modifier}+{keycode}: {e}")
