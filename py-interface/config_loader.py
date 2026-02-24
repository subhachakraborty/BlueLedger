import yaml
import os
from pathlib import Path
from typing import Any, Optional


class Config:
    """Configuration manager that loads YAML and resolves environment variables"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration from YAML file

        Args:
            config_path: Path to configuration YAML file
        """
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        self._load_env_variables()
        self._create_directories()

    def _load_env_variables(self):
        """Replace ${VAR} placeholders with environment variables"""

        def replace_env_vars(obj):
            if isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                value = os.getenv(var_name)
                if value is None:
                    raise ValueError(
                        f"Environment variable '{var_name}' not set. "
                        f"Please set it before running the script."
                    )
                return value
            else:
                return obj

        self.config = replace_env_vars(self.config)

    def _create_directories(self):
        """Create necessary directories if they don't exist"""
        dirs_to_create = [
            self.get("project", "output_dir"),
            self.get("project", "cache_dir"),
            self.get("project", "log_dir"),
        ]

        for dir_path in dirs_to_create:
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get nested configuration value using dot notation

        Args:
            *keys: Sequence of keys to traverse
            default: Default value if key path doesn't exist

        Returns:
            Configuration value or default

        Example:
            config.get('sentinel_hub', 'client_id')
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value

    def get_required(self, *keys: str) -> Any:
        """
        Get required configuration value (raises error if missing)

        Args:
            *keys: Sequence of keys to traverse

        Returns:
            Configuration value

        Raises:
            ValueError: If configuration key is missing
        """
        value = self.get(*keys)
        if value is None:
            raise ValueError(f"Required configuration missing: {'.'.join(keys)}")
        return value

    def __repr__(self) -> str:
        """String representation (hides sensitive data)"""
        safe_config = self._mask_sensitive_data(self.config.copy())
        return f"Config({yaml.dump(safe_config, default_flow_style=False)})"

    def _mask_sensitive_data(self, obj):
        """Mask sensitive configuration values for display"""
        sensitive_keys = ["client_id", "client_secret", "password", "token", "key"]

        if isinstance(obj, dict):
            return {
                k: (
                    "***MASKED***"
                    if any(sens in k.lower() for sens in sensitive_keys)
                    else self._mask_sensitive_data(v)
                )
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._mask_sensitive_data(item) for item in obj]
        return obj
