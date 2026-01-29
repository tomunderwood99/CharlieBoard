"""Settings management for the MBTA LED Controller."""
import json
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from .validation import validate_settings, DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

class SettingsManager:
    """Manages loading and saving of display settings."""
    
    def __init__(self, env_file: str = '.env'):
        """Initialize the settings manager.
        
        Args:
            env_file: Path to .env file
        """
        # Set up paths - try multiple locations for .env file
        self.utilities_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.utilities_dir)
        
        # Look for .env file in multiple locations (in order of preference)
        possible_env_paths = [
            # 1. Absolute path if provided
            env_file if os.path.isabs(env_file) else None,
            # 2. Relative to current working directory (most common)
            os.path.join(os.getcwd(), env_file) if not os.path.isabs(env_file) else None,
            # 3. In project root directory
            os.path.join(self.project_root, env_file),
            # 4. In utilities directory (legacy location)
            os.path.join(self.utilities_dir, env_file)
        ]
        
        # Find the first existing .env file
        self.env_file = None
        for path in possible_env_paths:
            if path and os.path.exists(path):
                self.env_file = path
                break
        
        # If no existing file found, default to project root for new file creation
        if self.env_file is None:
            self.env_file = os.path.join(self.project_root, env_file)
            
        self.last_modified = None
        
        # Use the centralized DEFAULT_SETTINGS from validation.py
        self._default_settings = DEFAULT_SETTINGS.copy()
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default settings.
        
        Returns:
            Dictionary containing default settings
        """
        return self._default_settings.copy()
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from .env file.
        
        Returns:
            Dictionary containing settings
        """
        try:
            if not os.path.exists(self.env_file):
                return self.get_default_settings()
            
            # Force reload environment variables from .env file
            # This ensures we get the latest values, overriding any cached ones
            load_dotenv(self.env_file, override=True)
            
            # Helper function to get environment variable with default
            def get_env(key: str, default: Any, cast_type: type = str):
                value = os.getenv(key)
                if value is None:
                    return default
                if cast_type == float:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                elif cast_type == bool:
                    return value.lower() in ('true', '1', 'yes', 'on')
                return value
            
            # Load settings from environment variables
            settings = {
                'route': get_env('ROUTE', self._default_settings['route']),
                'brightness': get_env('BRIGHTNESS', self._default_settings['brightness'], float),
                'power_switch': get_env('POWER_SWITCH', self._default_settings['power_switch']),
                'bedtime_start': get_env('BEDTIME_START', self._default_settings['bedtime_start']),
                'bedtime_end': get_env('BEDTIME_END', self._default_settings['bedtime_end']),
                'display_mode': get_env('DISPLAY_MODE', self._default_settings['display_mode'])
            }
            
            # Handle JSON color arrays
            color_keys = [
                'stopped_color', 'incoming_color', 'transit_color',
                'min_speed_color', 'max_speed_color', 'null_speed_color',
                'min_occupancy_color', 'max_occupancy_color', 'null_occupancy_color'
            ]
            
            for key in color_keys:
                env_value = os.getenv(key.upper())
                if env_value:
                    try:
                        settings[key] = json.loads(env_value)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Invalid JSON for {key}, using default")
                        settings[key] = self._default_settings[key]
                else:
                    settings[key] = self._default_settings[key]
            
            # Handle API key specially - convert 'None' string to None value
            api_key = os.getenv('MBTA_API_KEY')
            settings['mbta_api_key'] = None if api_key in ['None', 'none', '', None] else api_key

            # Handle debugger options - try JSON first, fall back to comma-separated
            debugger_str = os.getenv('DEBUGGER', '[]')
            try:
                settings['debugger'] = json.loads(debugger_str)
            except (json.JSONDecodeError, TypeError):
                settings['debugger'] = [opt.strip() for opt in debugger_str.split(',') if opt.strip()]

            # Handle show_debugger_options setting
            settings['show_debugger_options'] = get_env('SHOW_DEBUGGER_OPTIONS', self._default_settings['show_debugger_options'], bool)
            
            # Handle save_error_data setting (for debugging problematic API responses)
            settings['save_error_data'] = get_env('SAVE_ERROR_DATA', self._default_settings['save_error_data'], bool)
            
            # Station tracking removed for stable version

            # Validate settings
            settings = validate_settings(settings, self._default_settings)
            self.last_modified = os.path.getmtime(self.env_file)
            return settings

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return self.get_default_settings()
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save settings to .env file.
        
        Args:
            settings: Dictionary containing settings to save
            
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # Validate settings before saving
            settings_dict = validate_settings(settings, self._default_settings)
            
            # Preserve certain settings that shouldn't be overwritten from web interface
            # These are settings that are not configurable from the web UI
            # 'route' is set during initial setup and should not be changed via web interface
            preserve_keys = ['route', 'show_debugger_options', 'save_error_data']
            
            # Load current settings to preserve values for non-web-configurable settings
            if os.path.exists(self.env_file):
                current_settings = self.load_settings()
                for preserve_key in preserve_keys:
                    if preserve_key in current_settings:
                        # Preserve the existing value instead of using the default
                        settings_dict[preserve_key] = current_settings[preserve_key]
            
            # Create backup of existing .env file
            if os.path.exists(self.env_file):
                backup_file = f"{self.env_file}.bak"
                try:
                    with open(self.env_file, 'r') as src, open(backup_file, 'w') as dst:
                        dst.write(src.read())
                except Exception as e:
                    logger.warning(f"Failed to create .env backup: {e}")
            
            # Save to .env file
            with open(self.env_file, 'w') as f:
                for key, value in settings_dict.items():
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)
                    elif isinstance(value, bool):
                        value = 'true' if value else 'false'
                    f.write(f'{key.upper()}={value}\n')
            
            self.last_modified = os.path.getmtime(self.env_file)
            return True
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def check_and_reload(self) -> Dict[str, Any] | None:
        """Check if settings file has been modified and reload if needed.
        
        Returns:
            Dictionary containing new settings if reload occurred, None if no reload needed
        """
        try:
            if not os.path.exists(self.env_file):
                return self.get_default_settings()
            
            current_mtime = os.path.getmtime(self.env_file)
            if self.last_modified is None or current_mtime > self.last_modified:
                return self.load_settings()
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking settings: {e}")
            return self.get_default_settings()
    
    def force_reload(self) -> Dict[str, Any]:
        """Force reload settings from .env file, ignoring modification time checks.
        
        This is useful when you know the file has been updated but the modification
        time might not have changed (e.g., rapid successive saves).
        
        Returns:
            Dictionary containing current settings
        """
        self.last_modified = None
        return self.load_settings()
