"""
Configuration Manager for QuickWhisper

Handles loading and saving of application settings and credentials.
- settings.json: User preferences, UI settings, shortcuts, etc.
- credentials.json: Sensitive data like API keys (encrypted)

Includes automatic migration from legacy .env files.
"""

import base64
import json
import os
import platform
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


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
            "hide_banner": True,
            "selected_prompt": "Default",
            "selected_input_device": "",
            "dark_mode": True,
            "hidpi_mode": "auto",  # "auto", "enabled", or "disabled"
            "window_x": None,  # Saved window position (None = center on screen)
            "window_y": None,
            "language_mode": "auto",  # "auto" or "manual"
            "language": "en"  # Language code when mode is "manual"
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
            "auto_update_check": True,
            "paste_method": "auto",  # "auto", "sendinput" (Windows), "pynput", "pyautogui"
            "close_to_tray": False  # False = close app on X, True = minimize to tray on X
        }
    }
    
    # Default credentials structure
    DEFAULT_CREDENTIALS = {
        "openai_api_key": "",
        "openai_api_key_encrypted": False
    }
    
    # Hardcoded encryption key components (not ideal, but better than plaintext)
    # In a production app, this would be derived from machine-specific info or user password
    _ENCRYPTION_SALT = b'QuickWhisper_Salt_2024'
    _ENCRYPTION_PASSWORD = b'QW_Secure_Key_v1_xK9mP2nL'
    
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
    
    def _get_fernet(self) -> Fernet:
        """Get a Fernet instance for encryption/decryption."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._ENCRYPTION_SALT,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._ENCRYPTION_PASSWORD))
        return Fernet(key)
    
    def _encrypt_value(self, plaintext: str) -> str:
        """Encrypt a string value and return base64-encoded ciphertext."""
        if not plaintext:
            return ""
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    def _decrypt_value(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext and return the plaintext."""
        if not ciphertext:
            return ""
        try:
            fernet = self._get_fernet()
            encrypted = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except Exception as e:
            print(f"Error decrypting value: {e}")
            return ""
    
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
        
        # Build credentials from env vars (store encrypted)
        self._credentials = self._deep_copy(self.DEFAULT_CREDENTIALS)
        if env_vars.get("OPENAI_API_KEY"):
            # Encrypt the API key during migration
            self._credentials["openai_api_key"] = self._encrypt_value(env_vars["OPENAI_API_KEY"])
            self._credentials["openai_api_key_encrypted"] = True
        
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
        """Load credentials from JSON file and encrypt if necessary."""
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
        
        # Check if API key needs to be encrypted
        self._ensure_api_key_encrypted()
    
    def _ensure_api_key_encrypted(self):
        """Encrypt the API key if it's stored in plaintext."""
        api_key = self._credentials.get("openai_api_key", "")
        is_encrypted = self._credentials.get("openai_api_key_encrypted", False)
        
        if api_key and not is_encrypted:
            print("Encrypting API key for secure storage...")
            encrypted_key = self._encrypt_value(api_key)
            self._credentials["openai_api_key"] = encrypted_key
            self._credentials["openai_api_key_encrypted"] = True
            self.save_credentials()
            print("API key has been encrypted.")
    
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
    
    @property
    def dark_mode(self) -> bool:
        return self._settings["ui"].get("dark_mode", True)

    @dark_mode.setter
    def dark_mode(self, value: bool):
        self._settings["ui"]["dark_mode"] = value

    @property
    def hidpi_mode(self) -> str:
        """Get HiDPI mode: 'auto', 'enabled', or 'disabled'."""
        return self._settings["ui"].get("hidpi_mode", "auto")

    @hidpi_mode.setter
    def hidpi_mode(self, value: str):
        """Set HiDPI mode: 'auto', 'enabled', or 'disabled'."""
        if value in ("auto", "enabled", "disabled"):
            self._settings["ui"]["hidpi_mode"] = value

    @property
    def window_x(self) -> Optional[int]:
        """Get saved window X position (None = not saved/center on screen)."""
        return self._settings["ui"].get("window_x")

    @window_x.setter
    def window_x(self, value: Optional[int]):
        self._settings["ui"]["window_x"] = value

    @property
    def window_y(self) -> Optional[int]:
        """Get saved window Y position (None = not saved/center on screen)."""
        return self._settings["ui"].get("window_y")

    @window_y.setter
    def window_y(self, value: Optional[int]):
        self._settings["ui"]["window_y"] = value

    @property
    def language_mode(self) -> str:
        """Get language mode: 'auto' or 'manual'."""
        return self._settings["ui"].get("language_mode", "auto")

    @language_mode.setter
    def language_mode(self, value: str):
        """Set language mode: 'auto' or 'manual'."""
        if value in ("auto", "manual"):
            self._settings["ui"]["language_mode"] = value

    @property
    def language(self) -> str:
        """Get the configured language code (used when language_mode is 'manual')."""
        return self._settings["ui"].get("language", "en")

    @language.setter
    def language(self, value: str):
        """Set the language code."""
        self._settings["ui"]["language"] = value

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

    @property
    def paste_method(self) -> str:
        return self._settings["behavior"].get("paste_method", "auto")

    @paste_method.setter
    def paste_method(self, value: str):
        self._settings["behavior"]["paste_method"] = value

    @property
    def close_to_tray(self) -> bool:
        """If True, clicking X minimizes to tray. If False, clicking X closes the app."""
        return self._settings["behavior"].get("close_to_tray", False)

    @close_to_tray.setter
    def close_to_tray(self, value: bool):
        self._settings["behavior"]["close_to_tray"] = value

    # ========== Credentials Accessors ==========
    
    @property
    def openai_api_key(self) -> str:
        """Get the decrypted API key."""
        stored_key = self._credentials.get("openai_api_key", "")
        is_encrypted = self._credentials.get("openai_api_key_encrypted", False)
        
        if stored_key and is_encrypted:
            return self._decrypt_value(stored_key)
        return stored_key
    
    @openai_api_key.setter
    def openai_api_key(self, value: str):
        """Set the API key (will be stored encrypted)."""
        if value:
            self._credentials["openai_api_key"] = self._encrypt_value(value)
            self._credentials["openai_api_key_encrypted"] = True
        else:
            self._credentials["openai_api_key"] = ""
            self._credentials["openai_api_key_encrypted"] = False
    
    def has_api_key(self) -> bool:
        """Check if an API key is configured."""
        # Check the stored value directly, not the decrypted one
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

