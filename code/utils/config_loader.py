# -*- coding: utf-8 -*-
"""
Configuration Loader Module
Loads configuration from YAML file and environment variables
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Configuration manager"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration

        Args:
            config_path: Path to config.yaml file (default: ./config.yaml)
        """
        if config_path is None:
            # Find config.yaml in project root
            self.root_dir = Path(__file__).parent.parent
            config_path = self.root_dir / "config.yaml"
        else:
            self.root_dir = Path(config_path).parent
            config_path = Path(config_path)

        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key

        Args:
            key: Dot-separated key path (e.g., 'paths.workspace_dir')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def get_env(self, key: str, default: str = "") -> str:
        """
        Get environment variable value

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Environment variable value
        """
        return os.environ.get(key, default)

    def get_with_env_fallback(
        self,
        config_key: str,
        env_key: str,
        default: str = ""
    ) -> str:
        """
        Get value from config, fallback to environment variable

        Args:
            config_key: Configuration key path
            env_key: Environment variable name
            default: Default value

        Returns:
            Configuration value or environment variable
        """
        # First try config value (may contain ${VAR} format)
        config_value = self.get(config_key, "")

        if config_value:
            # Expand environment variables in config value
            if "${" in config_value and "}" in config_value:
                import re
                match = re.search(r'\$\{([^}]+)\}', config_value)
                if match:
                    env_var = match.group(1)
                    return os.environ.get(env_var, default)
            return config_value

        # Fallback to environment variable
        return os.environ.get(env_key, default)

    @property
    def paths(self) -> 'Paths':
        """Get paths helper"""
        return Paths(self.root_dir, self)

    def get_path(self, key: str) -> Path:
        """
        Get path relative to project root

        Args:
            key: Path configuration key

        Returns:
            Absolute Path object
        """
        relative_path = self.get(f"paths.{key}")
        if relative_path:
            return self.root_dir / relative_path

        # Fallback to direct path config
        path_value = self.get(key)
        if path_value:
            path = Path(path_value)
            if not path.is_absolute():
                return self.root_dir / path
            return path

        raise KeyError(f"Path not found: {key}")


class Paths:
    """Path helper class"""

    def __init__(self, root_dir: Path, config: Config):
        self.root = root_dir
        self.config = config

    @property
    def data_dir(self) -> Path:
        return self.root / self.config.get("paths.data_dir", "./data")

    @property
    def workspace_dir(self) -> Path:
        return self.root / self.config.get("paths.workspace_dir", "./workspace")

    @property
    def scan_results_dir(self) -> Path:
        return self.root / self.config.get("paths.scan_results_dir", "./scan_results")

    @property
    def execution_logs_dir(self) -> Path:
        return self.root / self.config.get("paths.execution_logs_dir", "./workspace/dynamic")

    @property
    def tasks_dir(self) -> Path:
        return self.root / self.config.get("paths.tasks_dir", "./tasks")

    @property
    def zip_dir(self) -> Path:
        return self.workspace_dir / "zip"

    @property
    def repo_dir(self) -> Path:
        return self.workspace_dir / "repo"

    @property
    def static_scan_dir(self) -> Path:
        return self.workspace_dir / "static"

    def get_risk_dir(self, risk_level: str) -> Path:
        """Get directory for specific risk level"""
        valid_levels = ["critical", "high", "medium", "low", "safe"]
        risk_level = risk_level.lower()
        if risk_level not in valid_levels:
            raise ValueError(f"Invalid risk level: {risk_level}")
        return self.static_scan_dir / risk_level

    def get_scan_result_dir(self, category: str) -> Path:
        """Get scan result directory for category"""
        valid_cats = ["SAFE", "SUSPICIOUS", "MALICIOUS", "ERROR"]
        if category.upper() not in valid_cats:
            raise ValueError(f"Invalid category: {category}")
        return self.scan_results_dir / category.upper()


# Global config instance
_global_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get global configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config
