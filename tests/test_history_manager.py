"""Unit tests for history_manager.py module."""
from __future__ import annotations

import unittest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

from correX.history_manager import HistoryManager


class TestHistoryManager(unittest.TestCase):
    """Test cases for HistoryManager class."""
    
    def setUp(self):
        """Set up test fixtures with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = Path(self.temp_dir) / "test_history.db"
        self.history = HistoryManager(db_path=self.db_file)
    
    def tearDown(self):
        """Clean up test files."""
        self.history.close()
        if self.db_file.exists():
            self.db_file.unlink()
        Path(self.temp_dir).rmdir()
    
    def test_initialization(self):
        """Test database initialization."""
        self.assertTrue(self.db_file.exists())
        self.assertIsNotNone(self.history.conn)
    
    def test_save_correction(self):
        """Test saving a correction to history."""
        original = "This is a test"
        corrected = "This is a test."
        tone = "professional"
        
        success = self.history.save_correction(original, corrected, tone)
        self.assertTrue(success)
    
    def test_retrieve_recent_history(self):
        """Test retrieving recent corrections."""
        # Add some test data
        test_data = [
            ("original 1", "corrected 1", "professional"),
            ("original 2", "corrected 2", "formal"),
            ("original 3", "corrected 3", "informal"),
        ]
        
        for original, corrected, tone in test_data:
            self.history.save_correction(original, corrected, tone)
        
        # Retrieve history
        history = self.history.get_recent_history(limit=10)
        
        self.assertEqual(len(history), 3)
        # Should be in reverse chronological order
        self.assertEqual(history[0]['original_text'], "original 3")
    
    def test_history_limit(self):
        """Test that limit parameter works correctly."""
        # Add 5 corrections
        for i in range(5):
            self.history.save_correction(f"original {i}", f"corrected {i}", "original")
        
        # Request only 3
        history = self.history.get_recent_history(limit=3)
        self.assertEqual(len(history), 3)
    
    def test_cleanup_old_entries(self):
        """Test automatic cleanup of old entries."""
        # Add an old entry (manually set timestamp)
        cursor = self.history.conn.cursor()
        old_timestamp = (datetime.now() - timedelta(hours=2)).isoformat()
        
        cursor.execute(
            "INSERT INTO history (original_text, corrected_text, tone, timestamp) VALUES (?, ?, ?, ?)",
            ("old text", "old corrected", "original", old_timestamp)
        )
        self.history.conn.commit()
        
        # Add a recent entry
        self.history.save_correction("new text", "new corrected", "original")
        
        # Run cleanup (1 hour threshold)
        self.history.cleanup_old_entries(hours=1)
        
        # Should only have recent entry
        history = self.history.get_recent_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['original_text'], "new text")
    
    def test_get_statistics(self):
        """Test getting history statistics."""
        # Add some corrections
        for i in range(5):
            self.history.save_correction(f"text {i}", f"corrected {i}", "professional")
        
        stats = self.history.get_statistics()
        
        self.assertIn('total_corrections', stats)
        self.assertEqual(stats['total_corrections'], 5)
        self.assertIn('today_corrections', stats)
    
    def test_empty_history(self):
        """Test behavior with empty history."""
        history = self.history.get_recent_history(limit=10)
        self.assertEqual(len(history), 0)
        
        stats = self.history.get_statistics()
        self.assertEqual(stats['total_corrections'], 0)
    
    def test_duplicate_corrections(self):
        """Test saving duplicate corrections."""
        text = "same text"
        corrected = "same corrected"
        
        # Save same correction twice
        self.history.save_correction(text, corrected, "original")
        self.history.save_correction(text, corrected, "original")
        
        # Should have 2 entries (duplicates allowed)
        history = self.history.get_recent_history(limit=10)
        self.assertEqual(len(history), 2)
    
    def test_special_characters_in_text(self):
        """Test handling special characters."""
        original = "Text with 'quotes' and \"double quotes\""
        corrected = "Corrected: 'quotes' & \"double\""
        
        success = self.history.save_correction(original, corrected, "original")
        self.assertTrue(success)
        
        history = self.history.get_recent_history(limit=1)
        self.assertEqual(history[0]['original_text'], original)
        self.assertEqual(history[0]['corrected_text'], corrected)
    
    def test_unicode_text(self):
        """Test handling unicode characters."""
        original = "Hello 世界 🌍"
        corrected = "你好 World 🚀"
        
        success = self.history.save_correction(original, corrected, "original")
        self.assertTrue(success)
        
        history = self.history.get_recent_history(limit=1)
        self.assertEqual(history[0]['original_text'], original)
    
    def test_long_text(self):
        """Test handling very long text."""
        original = "a" * 10000
        corrected = "b" * 10000
        
        success = self.history.save_correction(original, corrected, "original")
        self.assertTrue(success)
        
        history = self.history.get_recent_history(limit=1)
        self.assertEqual(len(history[0]['original_text']), 10000)
    
    def test_search_history(self):
        """Test searching history by keyword."""
        test_entries = [
            ("hello world", "Hello, world!", "professional"),
            ("goodbye world", "Goodbye, world!", "formal"),
            ("test message", "Test message.", "original"),
        ]
        
        for original, corrected, tone in test_entries:
            self.history.save_correction(original, corrected, tone)
        
        # Search for "world"
        results = self.history.search_history("world")
        self.assertEqual(len(results), 2)
        
        # Search for non-existent term
        results = self.history.search_history("nonexistent")
        self.assertEqual(len(results), 0)
    
    def test_delete_entry(self):
        """Test deleting a specific entry."""
        self.history.save_correction("test", "corrected", "original")
        
        history = self.history.get_recent_history(limit=1)
        entry_id = history[0]['id']
        
        success = self.history.delete_entry(entry_id)
        self.assertTrue(success)
        
        history = self.history.get_recent_history(limit=10)
        self.assertEqual(len(history), 0)
    
    def test_clear_all_history(self):
        """Test clearing entire history."""
        # Add multiple entries
        for i in range(10):
            self.history.save_correction(f"text {i}", f"corrected {i}", "original")
        
        success = self.history.clear_all_history()
        self.assertTrue(success)
        
        history = self.history.get_recent_history(limit=100)
        self.assertEqual(len(history), 0)
    
    def test_concurrent_access(self):
        """Test that multiple saves work correctly."""
        # Rapidly save multiple corrections
        for i in range(100):
            self.history.save_correction(f"text {i}", f"corrected {i}", "original")
        
        history = self.history.get_recent_history(limit=100)
        self.assertEqual(len(history), 100)
    
    def test_database_connection_persistence(self):
        """Test that database connection persists across operations."""
        self.history.save_correction("test1", "corrected1", "original")
        self.assertIsNotNone(self.history.conn)
        
        self.history.save_correction("test2", "corrected2", "original")
        self.assertIsNotNone(self.history.conn)
        
        history = self.history.get_recent_history(limit=10)
        self.assertEqual(len(history), 2)


if __name__ == '__main__':
    unittest.main()
