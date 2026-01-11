"""
Configuration Manager for QuickWhisper

Handles loading and saving of application settings and credentials.
- settings.json: User preferences, UI settings, shortcuts, etc.
- credentials.json: Sensitive data like API keys (to be encrypted in future)

Includes automatic migration from legacy .env files.
"""

import json
import os
import platform
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """Manages application configuration using JSON files."""
    
    # Default settings structure
    DEFAULT_SETTINGS = {
        "models": {
            "transcription_model": "gpt-4o-transcribe",
            "transcription_model_type": "gpt",
            "ai_model": "gpt-5-mini",
            "whisper_language": "auto"
        },
        "ui": {
            "hide_banner": False,
            "selected_prompt": "Default",
            "selected_input_device": ""
        },
        "shortcuts": {
            "record_edit": None,  # Will be set based on OS
            "record_transcribe": None,
            "cancel_recording": None,
            "cycle_prompt_back": None,
            "cycle_prompt_forward": None
        },
        "recording": {
            "location": "alongside",
            "custom_path": "",
            "file_handling": "overwrite"
        },
        "behavior": {
            "auto_hotkey_refresh": True,
            "auto_update_check": True
        }
    }
    
    # Default credentials structure
    DEFAULT_CREDENTIALS = {
        "openai_api_key": ""
    }
    
    def __init__(self, config_dir: str = "config"):
        """Initialize the config manager.
        
        Args:
            config_dir: Directory where config files are stored
        """
        self.config_dir = Path(config_dir)
        self.settings_path = self.config_dir / "settings.json"
        self.credentials_path = self.config_dir / "credentials.json"
        self.legacy_env_path = self.config_dir / ".env"
        
        # Detect OS for default shortcuts
        self.is_mac = platform.system() == 'Darwin'
        self._set_os_specific_defaults()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or migrate configuration
        self._settings: dict = {}
        self._credentials: dict = {}
        self._load_config()
    
    def _set_os_specific_defaults(self):
        """Set OS-specific default values."""
        if self.is_mac:
            self.DEFAULT_SETTINGS["shortcuts"]["record_edit"] = "command+alt+j"
            self.DEFAULT_SETTINGS["shortcuts"]["record_transcribe"] = "command+alt+shift+j"
            self.DEFAULT_SETTINGS["shortcuts"]["cancel_recording"] = "command+x"
            self.DEFAULT_SETTINGS["shortcuts"]["cycle_prompt_back"] = "command+["
            self.DEFAULT_SETTINGS["shortcuts"]["cycle_prompt_forward"] = "command+]"
        else:
            self.DEFAULT_SETTINGS["shortcuts"]["record_edit"] = "ctrl+alt+j"
            self.DEFAULT_SETTINGS["shortcuts"]["record_transcribe"] = "ctrl+alt+shift+j"
            self.DEFAULT_SETTINGS["shortcuts"]["cancel_recording"] = "win+x"
            self.DEFAULT_SETTINGS["shortcuts"]["cycle_prompt_back"] = "alt+left"
            self.DEFAULT_SETTINGS["shortcuts"]["cycle_prompt_forward"] = "alt+right"
    
    def _load_config(self):
        """Load configuration from files, migrating from .env if necessary."""
        # Check if we need to migrate from legacy .env
        if self.legacy_env_path.exists() and not self.settings_path.exists():
            self._migrate_from_env()
        else:
            self._load_settings()
            self._load_credentials()
    
    def _migrate_from_env(self):
        """Migrate settings from legacy .env file to new JSON format."""
        print("Migrating configuration from .env to JSON format...")
        
        env_vars = {}
        try:
            with open(self.legacy_env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error reading .env file: {e}")
            env_vars = {}
        
        # Build settings from env vars
        self._settings = self._deep_copy(self.DEFAULT_SETTINGS)
        
        # Models
        if env_vars.get("TRANSCRIPTION_MODEL"):
            self._settings["models"]["transcription_model"] = env_vars["TRANSCRIPTION_MODEL"]
        if env_vars.get("TRANSCRIPTION_MODEL_TYPE"):
            self._settings["models"]["transcription_model_type"] = env_vars["TRANSCRIPTION_MODEL_TYPE"]
        if env_vars.get("AI_MODEL"):
            self._settings["models"]["ai_model"] = env_vars["AI_MODEL"]
        if env_vars.get("WHISPER_LANGUAGE"):
            self._settings["models"]["whisper_language"] = env_vars["WHISPER_LANGUAGE"]
        
        # UI
        if env_vars.get("HIDE_BANNER"):
            self._settings["ui"]["hide_banner"] = env_vars["HIDE_BANNER"].lower() == "true"
        if env_vars.get("SELECTED_PROMPT"):
            self._settings["ui"]["selected_prompt"] = env_vars["SELECTED_PROMPT"]
        
        # Shortcuts
        if env_vars.get("SHORTCUT_RECORD_EDIT"):
            self._settings["shortcuts"]["record_edit"] = env_vars["SHORTCUT_RECORD_EDIT"]
        if env_vars.get("SHORTCUT_RECORD_TRANSCRIBE"):
            self._settings["shortcuts"]["record_transcribe"] = env_vars["SHORTCUT_RECORD_TRANSCRIBE"]
        if env_vars.get("SHORTCUT_CANCEL_RECORDING"):
            self._settings["shortcuts"]["cancel_recording"] = env_vars["SHORTCUT_CANCEL_RECORDING"]
        if env_vars.get("SHORTCUT_CYCLE_PROMPT_BACK"):
            self._settings["shortcuts"]["cycle_prompt_back"] = env_vars["SHORTCUT_CYCLE_PROMPT_BACK"]
        if env_vars.get("SHORTCUT_CYCLE_PROMPT_FORWARD"):
            self._settings["shortcuts"]["cycle_prompt_forward"] = env_vars["SHORTCUT_CYCLE_PROMPT_FORWARD"]
        
        # Recording
        if env_vars.get("RECORDING_LOCATION"):
            self._settings["recording"]["location"] = env_vars["RECORDING_LOCATION"]
        if env_vars.get("CUSTOM_RECORDING_PATH"):
            self._settings["recording"]["custom_path"] = env_vars["CUSTOM_RECORDING_PATH"]
        if env_vars.get("FILE_HANDLING"):
            self._settings["recording"]["file_handling"] = env_vars["FILE_HANDLING"]
        
        # Behavior
        if env_vars.get("AUTO_HOTKEY_REFRESH"):
            self._settings["behavior"]["auto_hotkey_refresh"] = env_vars["AUTO_HOTKEY_REFRESH"].lower() == "true"
        if env_vars.get("AUTO_UPDATE_CHECK"):
            self._settings["behavior"]["auto_update_check"] = env_vars["AUTO_UPDATE_CHECK"].lower() == "true"
        
        # Build credentials from env vars
        self._credentials = self._deep_copy(self.DEFAULT_CREDENTIALS)
        if env_vars.get("OPENAI_API_KEY"):
            self._credentials["openai_api_key"] = env_vars["OPENAI_API_KEY"]
        
        # Save to new format
        self.save_settings()
        self.save_credentials()
        
        # Rename old .env file as backup
        backup_path = self.legacy_env_path.with_suffix('.env.backup')
        try:
            self.legacy_env_path.rename(backup_path)
            print(f"Legacy .env file backed up to {backup_path}")
        except Exception as e:
            print(f"Could not backup .env file: {e}")
        
        print("Migration complete!")
    
    def _load_settings(self):
        """Load settings from JSON file."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                # Merge with defaults to handle any new settings
                self._settings = self._merge_with_defaults(loaded, self.DEFAULT_SETTINGS)
            except Exception as e:
                print(f"Error loading settings: {e}")
                self._settings = self._deep_copy(self.DEFAULT_SETTINGS)
        else:
            self._settings = self._deep_copy(self.DEFAULT_SETTINGS)
    
    def _load_credentials(self):
        """Load credentials from JSON file."""
        if self.credentials_path.exists():
            try:
                with open(self.credentials_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                self._credentials = self._merge_with_defaults(loaded, self.DEFAULT_CREDENTIALS)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                self._credentials = self._deep_copy(self.DEFAULT_CREDENTIALS)
        else:
            self._credentials = self._deep_copy(self.DEFAULT_CREDENTIALS)
    
    def _merge_with_defaults(self, loaded: dict, defaults: dict) -> dict:
        """Recursively merge loaded config with defaults to fill in missing keys."""
        result = self._deep_copy(defaults)
        for key, value in loaded.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self._merge_with_defaults(value, result[key])
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of a nested dict/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def save_settings(self):
        """Save settings to JSON file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
            raise
    
    def save_credentials(self):
        """Save credentials to JSON file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.credentials_path, 'w', encoding='utf-8') as f:
                json.dump(self._credentials, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving credentials: {e}")
            raise
    
    # ========== Settings Accessors ==========
    
    # Models
    @property
    def transcription_model(self) -> str:
        return self._settings["models"]["transcription_model"]
    
    @transcription_model.setter
    def transcription_model(self, value: str):
        self._settings["models"]["transcription_model"] = value
    
    @property
    def transcription_model_type(self) -> str:
        return self._settings["models"]["transcription_model_type"]
    
    @transcription_model_type.setter
    def transcription_model_type(self, value: str):
        self._settings["models"]["transcription_model_type"] = value
    
    @property
    def ai_model(self) -> str:
        return self._settings["models"]["ai_model"]
    
    @ai_model.setter
    def ai_model(self, value: str):
        self._settings["models"]["ai_model"] = value
    
    @property
    def whisper_language(self) -> str:
        return self._settings["models"]["whisper_language"]
    
    @whisper_language.setter
    def whisper_language(self, value: str):
        self._settings["models"]["whisper_language"] = value
    
    # UI
    @property
    def hide_banner(self) -> bool:
        return self._settings["ui"]["hide_banner"]
    
    @hide_banner.setter
    def hide_banner(self, value: bool):
        self._settings["ui"]["hide_banner"] = value
    
    @property
    def selected_prompt(self) -> str:
        return self._settings["ui"]["selected_prompt"]
    
    @selected_prompt.setter
    def selected_prompt(self, value: str):
        self._settings["ui"]["selected_prompt"] = value
    
    @property
    def selected_input_device(self) -> str:
        return self._settings["ui"].get("selected_input_device", "")
    
    @selected_input_device.setter
    def selected_input_device(self, value: str):
        self._settings["ui"]["selected_input_device"] = value
    
    # Shortcuts
    @property
    def shortcuts(self) -> dict:
        return self._settings["shortcuts"]
    
    def get_shortcut(self, name: str) -> str:
        return self._settings["shortcuts"].get(name, "")
    
    def set_shortcut(self, name: str, value: str):
        self._settings["shortcuts"][name] = value
    
    # Recording
    @property
    def recording_location(self) -> str:
        return self._settings["recording"]["location"]
    
    @recording_location.setter
    def recording_location(self, value: str):
        self._settings["recording"]["location"] = value
    
    @property
    def custom_recording_path(self) -> str:
        return self._settings["recording"]["custom_path"]
    
    @custom_recording_path.setter
    def custom_recording_path(self, value: str):
        self._settings["recording"]["custom_path"] = value
    
    @property
    def file_handling(self) -> str:
        return self._settings["recording"]["file_handling"]
    
    @file_handling.setter
    def file_handling(self, value: str):
        self._settings["recording"]["file_handling"] = value
    
    # Behavior
    @property
    def auto_hotkey_refresh(self) -> bool:
        return self._settings["behavior"]["auto_hotkey_refresh"]
    
    @auto_hotkey_refresh.setter
    def auto_hotkey_refresh(self, value: bool):
        self._settings["behavior"]["auto_hotkey_refresh"] = value
    
    @property
    def auto_update_check(self) -> bool:
        return self._settings["behavior"]["auto_update_check"]
    
    @auto_update_check.setter
    def auto_update_check(self, value: bool):
        self._settings["behavior"]["auto_update_check"] = value
    
    # ========== Credentials Accessors ==========
    
    @property
    def openai_api_key(self) -> str:
        return self._credentials.get("openai_api_key", "")
    
    @openai_api_key.setter
    def openai_api_key(self, value: str):
        self._credentials["openai_api_key"] = value
    
    def has_api_key(self) -> bool:
        """Check if an API key is configured."""
        return bool(self._credentials.get("openai_api_key", "").strip())


# Global config manager instance (singleton pattern)
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reset_config():
    """Reset the global config manager (useful for testing)."""
    global _config_manager
    _config_manager = None

