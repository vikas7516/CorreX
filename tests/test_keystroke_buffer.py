"""Unit tests for keystroke_buffer.py module."""
from __future__ import annotations

import unittest
from correX.keystroke_buffer import KeystrokeBuffer


class TestKeystrokeBuffer(unittest.TestCase):
    """Test cases for KeystrokeBuffer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.buffer = KeystrokeBuffer(max_chars=100)
    
    def test_initialization(self):
        """Test buffer initialization."""
        self.assertEqual(self.buffer.max_chars, 100)
        self.assertEqual(len(self.buffer._buffers), 0)
    
    def test_add_single_keystroke(self):
        """Test adding a single character."""
        hwnd = 12345
        self.buffer.add_keystroke(hwnd, 'a')
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, 'a')
    
    def test_add_multiple_keystrokes(self):
        """Test adding multiple characters."""
        hwnd = 12345
        for char in "hello":
            self.buffer.add_keystroke(hwnd, char)
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, 'hello')
    
    def test_per_window_isolation(self):
        """Test that different windows have separate buffers."""
        hwnd1 = 12345
        hwnd2 = 67890
        
        self.buffer.add_keystroke(hwnd1, 'a')
        self.buffer.add_keystroke(hwnd1, 'b')
        self.buffer.add_keystroke(hwnd2, 'x')
        self.buffer.add_keystroke(hwnd2, 'y')
        
        text1 = self.buffer.get_text(hwnd1)
        text2 = self.buffer.get_text(hwnd2)
        
        self.assertEqual(text1, 'ab')
        self.assertEqual(text2, 'xy')
    
    def test_backspace_handling(self):
        """Test backspace removes last character."""
        hwnd = 12345
        self.buffer.add_keystroke(hwnd, 'h')
        self.buffer.add_keystroke(hwnd, 'e')
        self.buffer.add_keystroke(hwnd, 'l')
        self.buffer.add_keystroke(hwnd, 'l')
        self.buffer.add_keystroke(hwnd, 'o')
        
        self.buffer.handle_backspace(hwnd)
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, 'hell')
    
    def test_backspace_empty_buffer(self):
        """Test backspace on empty buffer doesn't crash."""
        hwnd = 12345
        self.buffer.handle_backspace(hwnd)
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, '')
    
    def test_buffer_overflow(self):
        """Test that buffer respects max_chars limit."""
        small_buffer = KeystrokeBuffer(max_chars=10)
        hwnd = 12345
        
        # Add 20 characters
        for i in range(20):
            small_buffer.add_keystroke(hwnd, 'a')
        
        text = small_buffer.get_text(hwnd)
        self.assertEqual(len(text), 10)
        self.assertEqual(text, 'a' * 10)
    
    def test_clear_buffer(self):
        """Test clearing a specific window's buffer."""
        hwnd = 12345
        self.buffer.add_keystroke(hwnd, 'h')
        self.buffer.add_keystroke(hwnd, 'i')
        
        self.buffer.clear_buffer(hwnd)
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, '')
    
    def test_clear_all_buffers(self):
        """Test clearing all buffers."""
        hwnd1 = 12345
        hwnd2 = 67890
        
        self.buffer.add_keystroke(hwnd1, 'a')
        self.buffer.add_keystroke(hwnd2, 'b')
        
        self.buffer.clear_all_buffers()
        
        text1 = self.buffer.get_text(hwnd1)
        text2 = self.buffer.get_text(hwnd2)
        
        self.assertEqual(text1, '')
        self.assertEqual(text2, '')
    
    def test_get_nonexistent_buffer(self):
        """Test getting text from window with no buffer."""
        hwnd = 99999
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, '')
    
    def test_special_characters(self):
        """Test handling of special characters."""
        hwnd = 12345
        special_chars = "Hello, World! 123 @#$%"
        
        for char in special_chars:
            self.buffer.add_keystroke(hwnd, char)
        
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, special_chars)
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        hwnd = 12345
        unicode_text = "Hello 世界 🌍"
        
        for char in unicode_text:
            self.buffer.add_keystroke(hwnd, char)
        
        text = self.buffer.get_text(hwnd)
        self.assertEqual(text, unicode_text)
    
    def test_lru_eviction(self):
        """Test that old windows are evicted when limit reached."""
        buffer = KeystrokeBuffer(max_chars=100, max_windows=3)
        
        # Add data to 4 different windows
        for i in range(4):
            hwnd = 1000 + i
            buffer.add_keystroke(hwnd, str(i))
        
        # First window should be evicted
        text = buffer.get_text(1000)
        self.assertEqual(text, '')
        
        # Last 3 windows should still have data
        for i in range(1, 4):
            hwnd = 1000 + i
            text = buffer.get_text(hwnd)
            self.assertEqual(text, str(i))


if __name__ == '__main__':
    unittest.main()
