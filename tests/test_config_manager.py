"""Unit tests for config_manager.py module."""
from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from correX.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures with temporary config file."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.json"
        
        # Mock the default config location
        with patch('correX.config_manager.Path.home') as mock_home:
            mock_home.return_value = Path(self.temp_dir)
            self.config = ConfigManager()
            self.config.config_file = self.config_file
    
    def tearDown(self):
        """Clean up test files."""
        if self.config_file.exists():
            self.config_file.unlink()
        Path(self.temp_dir).rmdir()
    
    def test_initialization_creates_default_config(self):
        """Test that initialization creates default config."""
        self.assertIsNotNone(self.config.config)
        self.assertIn('api_key', self.config.config)
        self.assertIn('trigger_key', self.config.config)
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        test_key = "test_api_key_12345"
        self.config.set_api_key(test_key)
        self.config.save_config()
        
        # Create new config manager to load from file
        new_config = ConfigManager()
        new_config.config_file = self.config_file
        new_config.load_config()
        
        self.assertEqual(new_config.get_api_key(), test_key)
    
    def test_set_and_get_api_key(self):
        """Test API key getter and setter."""
        test_key = "sk-test-key"
        self.config.set_api_key(test_key)
        self.assertEqual(self.config.get_api_key(), test_key)
    
    def test_set_and_get_trigger_key(self):
        """Test trigger key getter and setter."""
        test_trigger = "F2"
        self.config.set_trigger_key(test_trigger)
        self.assertEqual(self.config.get_trigger_key(), test_trigger)
    
    def test_set_and_get_num_versions(self):
        """Test num_versions getter and setter."""
        self.config.set_num_versions(3)
        self.assertEqual(self.config.get_num_versions(), 3)
    
    def test_num_versions_validation(self):
        """Test that num_versions is clamped to valid range."""
        self.config.set_num_versions(0)
        self.assertGreaterEqual(self.config.get_num_versions(), 1)
        
        self.config.set_num_versions(10)
        self.assertLessEqual(self.config.get_num_versions(), 5)
    
    def test_temperature_validation(self):
        """Test that temperature is clamped to valid range."""
        self.config.set_temperature(-1.0)
        self.assertGreaterEqual(self.config.get_temperature(), 0.0)
        
        self.config.set_temperature(3.0)
        self.assertLessEqual(self.config.get_temperature(), 2.0)
    
    def test_get_default_values(self):
        """Test default configuration values."""
        defaults = self.config.get_default_config()
        
        self.assertEqual(defaults['trigger_key'], 'tab')
        self.assertEqual(defaults['num_versions'], 5)
        self.assertIn('temperature', defaults)
        self.assertIn('max_buffer_chars', defaults)
    
    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        # Change some values
        self.config.set_api_key("custom_key")
        self.config.set_trigger_key("F5")
        self.config.set_num_versions(2)
        
        # Reset
        self.config.reset_to_defaults()
        
        # Verify defaults restored (except API key which should be preserved)
        self.assertEqual(self.config.get_trigger_key(), 'tab')
        self.assertEqual(self.config.get_num_versions(), 5)
    
    def test_invalid_json_handling(self):
        """Test handling of corrupted config file."""
        # Write invalid JSON
        self.config_file.write_text("{ invalid json }")
        
        # Should load defaults without crashing
        new_config = ConfigManager()
        new_config.config_file = self.config_file
        new_config.load_config()
        
        self.assertIsNotNone(new_config.config)
        self.assertEqual(new_config.get_trigger_key(), 'tab')
    
    def test_missing_config_file(self):
        """Test behavior when config file doesn't exist."""
        non_existent = Path(self.temp_dir) / "nonexistent.json"
        
        new_config = ConfigManager()
        new_config.config_file = non_existent
        new_config.load_config()
        
        # Should create default config
        self.assertIsNotNone(new_config.config)
        self.assertEqual(new_config.get_trigger_key(), 'tab')
    
    def test_model_name_config(self):
        """Test model name configuration."""
        test_model = "gemini-1.5-pro"
        self.config.set_model_name(test_model)
        self.assertEqual(self.config.get_model_name(), test_model)
    
    def test_candidate_settings(self):
        """Test candidate personalization settings."""
        test_settings = [
            {'tone': 'professional', 'temperature': 0.5},
            {'tone': 'formal', 'temperature': 0.6},
        ]
        
        self.config.set_candidate_settings(test_settings)
        loaded_settings = self.config.get_candidate_settings()
        
        self.assertEqual(len(loaded_settings), 2)
        self.assertEqual(loaded_settings[0]['tone'], 'professional')
        self.assertEqual(loaded_settings[1]['temperature'], 0.6)
    
    def test_startup_config(self):
        """Test startup configuration."""
        self.config.set_startup_enabled(True)
        self.assertTrue(self.config.is_startup_enabled())
        
        self.config.set_startup_enabled(False)
        self.assertFalse(self.config.is_startup_enabled())
    
    def test_notification_config(self):
        """Test notification configuration."""
        self.config.set_notifications_enabled(True)
        self.assertTrue(self.config.are_notifications_enabled())
        
        self.config.set_notifications_enabled(False)
        self.assertFalse(self.config.are_notifications_enabled())
    
    def test_config_persistence(self):
        """Test that config changes persist across saves."""
        changes = {
            'api_key': 'test_key',
            'trigger_key': 'F3',
            'num_versions': 3,
            'temperature': 0.7,
        }
        
        for key, value in changes.items():
            self.config.config[key] = value
        
        self.config.save_config()
        
        # Load fresh instance
        new_config = ConfigManager()
        new_config.config_file = self.config_file
        new_config.load_config()
        
        for key, expected_value in changes.items():
            self.assertEqual(new_config.config[key], expected_value)


if __name__ == '__main__':
    unittest.main()
