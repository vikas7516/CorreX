"""Configuration manager for persistent settings."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable, Tuple

try:
    from .gemini_corrector import GeminiCorrector
except ImportError:  # pragma: no cover - fallback when module unavailable
    GeminiCorrector = None  # type: ignore


# Configuration validation schema
CONFIG_SCHEMA: Dict[str, Tuple[type, Callable[[Any], bool], str]] = {
    "api_key": (str, lambda x: True, "Must be a string"),
    "model_name": (str, lambda x: len(x) > 0, "Must be a non-empty string"),
    "trigger_key": (str, lambda x: len(x) > 0, "Must be a non-empty string"),
    "clear_buffer_trigger_key": (str, lambda x: len(x) > 0, "Must be a non-empty string"),
    "dictation_trigger_key": (str, lambda x: len(x) > 0, "Must be a non-empty string"),
    "versions_per_correction": (int, lambda x: 1 <= x <= 5, "Must be between 1 and 5"),
    "paragraph_enabled": (bool, lambda x: True, "Must be a boolean"),
    "start_on_boot": (bool, lambda x: True, "Must be a boolean"),
    "minimize_to_tray": (bool, lambda x: True, "Must be a boolean"),
    "show_notifications": (bool, lambda x: True, "Must be a boolean"),
}


def validate_config_value(key: str, value: Any) -> Tuple[bool, str]:
    """Validate a single configuration value.
    
    Args:
        key: Configuration key
        value: Value to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if key not in CONFIG_SCHEMA:
        return True, ""  # Unknown keys are allowed (for forward compatibility)
    
    expected_type, validator, error_msg = CONFIG_SCHEMA[key]
    
    # Type check
    if not isinstance(value, expected_type):
        return False, f"{key}: {error_msg} (got {type(value).__name__})"
    
    # Value validation
    if not validator(value):
        return False, f"{key}: {error_msg} (value: {value})"
    
    return True, ""


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate entire configuration dictionary.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    for key, value in config.items():
        is_valid, error_msg = validate_config_value(key, value)
        if not is_valid:
            errors.append(error_msg)
    
    return len(errors) == 0, errors


class ConfigManager:
    """
    Manages application configuration with JSON persistence.
    
    Configuration is PERMANENT and saved forever until:
    - Manually changed via GUI
    - Config file deleted
    - reset() method called
    
    Unlike history (which auto-deletes hourly), config persists across:
    - App restarts
    - System reboots
    - Updates
    """
    
    def __init__(self, config_file: str = "correx_config.json"):
        """Initialize config manager."""
        self.config_dir = Path.home() / ".correx"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / config_file
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from file."""
        data = None
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load config: {e}")

        if not isinstance(data, dict):
            data = self._default_config()

        # Ensure new schema keys exist
        if "candidate_settings" not in data:
            data["candidate_settings"] = self._default_candidate_settings()
        else:
            data["candidate_settings"] = self._normalize_candidate_settings(data.get("candidate_settings"))

        return data
    
    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "api_key": "",
            "model_name": "gemini-2.0-flash-exp",
            "trigger_key": "ctrl+space",
            "clear_buffer_trigger_key": "ctrl+shift+delete",
            "dictation_trigger_key": "ctrl+shift+d",
            "versions_per_correction": 3,
            "candidate_settings": self._default_candidate_settings(),
            "paragraph_enabled": True,
            "start_on_boot": False,
            "minimize_to_tray": True,
            "show_notifications": True,
        }

    def _default_candidate_settings(self) -> List[Dict[str, Any]]:
        if GeminiCorrector and hasattr(GeminiCorrector, "default_candidate_settings"):
            try:
                return GeminiCorrector.default_candidate_settings()
            except Exception as error:
                print(f"[WARNING] Failed to load default candidate settings from GeminiCorrector: {error}")
        return [
            {"temperature": 0.30, "tone": "original"},
            {"temperature": 0.55, "tone": "professional"},
            {"temperature": 0.60, "tone": "formal"},
            {"temperature": 0.65, "tone": "informal"},
            {"temperature": 0.80, "tone": "creative"},
        ]

    def _normalize_candidate_settings(self, settings: Any) -> List[Dict[str, Any]]:
        if GeminiCorrector and hasattr(GeminiCorrector, "normalize_candidate_settings"):
            try:
                return GeminiCorrector.normalize_candidate_settings(settings)
            except Exception as error:
                print(f"[WARNING] Candidate settings invalid in config; resetting defaults: {error}")
        return self._default_candidate_settings()
    
    def save(self) -> bool:
        """Save current configuration to file with validation."""
        # Validate config before saving
        is_valid, errors = validate_config(self.config)
        if not is_valid:
            print(f"[WARNING] Config validation errors: {'; '.join(errors)}")
            print("[WARNING] Saving anyway, but some values may be invalid")
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value and save."""
        self.config[key] = value
        self.save()
    
    def get_api_key(self) -> Optional[str]:
        """Get saved API key."""
        key = self.get("api_key", "")
        return key if key else None
    
    def set_api_key(self, api_key: str) -> None:
        """Save API key."""
        self.set("api_key", api_key)
    
    def get_model_name(self) -> str:
        """Get saved model name."""
        return self.get("model_name", "gemini-2.0-flash-exp")
    
    def set_model_name(self, model_name: str) -> None:
        """Save model name."""
        self.set("model_name", model_name)
    
    def get_trigger_key(self) -> str:
        """Get saved trigger key."""
        return self.get("trigger_key", "ctrl+space")
    
    def set_trigger_key(self, key: str) -> None:
        """Save trigger key."""
        self.set("trigger_key", key)

    def get_clear_buffer_trigger_key(self) -> str:
        """Get saved clear-buffer trigger key."""
        return self.get("clear_buffer_trigger_key", "ctrl+shift+delete")

    def set_clear_buffer_trigger_key(self, key: str) -> None:
        """Save clear-buffer trigger key (blank disables)."""
        self.set("clear_buffer_trigger_key", key)
    
    def get_versions_per_correction(self) -> int:
        """Get number of versions to generate."""
        return self.get("versions_per_correction", 3)
    
    def set_versions_per_correction(self, count: int) -> None:
        """Save versions per correction."""
        self.set("versions_per_correction", count)

    def get_candidate_settings(self) -> List[Dict[str, Any]]:
        """Retrieve per-candidate tone/temperature configuration."""
        settings = self._normalize_candidate_settings(self.get("candidate_settings"))
        if self.config.get("candidate_settings") != settings:
            self.config["candidate_settings"] = settings
            self.save()
        return [dict(item) for item in settings]

    def set_candidate_settings(self, settings: List[Dict[str, Any]]) -> None:
        """Persist per-candidate personalization settings."""
        normalized = self._normalize_candidate_settings(settings)
        self.set("candidate_settings", normalized)
    
    def is_paragraph_enabled(self) -> bool:
        """Check if paragraph correction is enabled."""
        return self.get("paragraph_enabled", True)
    
    def set_paragraph_enabled(self, enabled: bool) -> None:
        """Save paragraph enabled state."""
        self.set("paragraph_enabled", enabled)
    
    def is_start_on_boot(self) -> bool:
        """Check if start on boot is enabled."""
        return self.get("start_on_boot", False)
    
    def set_start_on_boot(self, enabled: bool) -> None:
        """Save start on boot state and update Windows registry."""
        self.set("start_on_boot", enabled)
        self._update_startup_registry(enabled)
    
    def should_minimize_to_tray(self) -> bool:
        """Check if should minimize to tray."""
        return self.get("minimize_to_tray", True)
    
    def set_minimize_to_tray(self, enabled: bool) -> None:
        """Save minimize to tray preference."""
        self.set("minimize_to_tray", enabled)
    
    def should_show_notifications(self) -> bool:
        """Check if should show notifications."""
        return self.get("show_notifications", True)
    
    def set_show_notifications(self, enabled: bool) -> None:
        """Save notification preference."""
        self.set("show_notifications", enabled)
    
    def _update_startup_registry(self, enabled: bool) -> bool:
        """Add/remove from Windows startup registry."""
        try:
            import winreg
            import sys
            
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "CorreX"
            
            # Get path to the script
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                app_path = sys.executable
            else:
                # Running as script
                script_path = Path(__file__).parent / "main.py"
                python_path = sys.executable
                app_path = f'"{python_path}" "{script_path}"'
            
            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )
            
            if enabled:
                # Add to startup
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
                print(f"[CONFIG] Added to Windows startup")
            else:
                # Remove from startup
                try:
                    winreg.DeleteValue(key, app_name)
                    print(f"[CONFIG] Removed from Windows startup")
                except FileNotFoundError:
                    pass  # Already not in startup
            
            winreg.CloseKey(key)
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to update startup registry: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset all settings to default values."""
        try:
            self.config = self._default_config()
            success = self.save()
            if success:
                print(f"[CONFIG] Configuration reset to defaults")
            return success
        except Exception as e:
            print(f"[ERROR] Failed to reset config: {e}")
            return False
    
    def delete_config_file(self) -> bool:
        """Delete the configuration file completely."""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                print(f"[CONFIG] Configuration file deleted")
                return True
            return False
        except Exception as e:
            print(f"[ERROR] Failed to delete config file: {e}")
            return False
