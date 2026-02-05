"""Configuration management for AXPOC application."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

from src.utils.exceptions import ConfigurationError
from src.utils.log_config import get_logger
from src.utils.xml_tier import normalize_xml_tier

logger = get_logger(__name__)


ALLOWED_RANKING_MODES = {"rewrite", "verbatim"}
ALLOWED_CONTEXT_LEVELS = {
    "full_hierarchical",
    "chapter_statement_selection",
    "hierarchical_only",
    "statement_selection_only",
    "chapter_only",
    "none",
}


@dataclass
class LLMProviderConfig:
    """Configuration for LLM providers."""

    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    enabled: bool = True


@dataclass
class AppConfig:
    """Main application configuration class."""

    # Stripped away foreign code, not relevant for log-configuration

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None


class ConfigManager:
    """Configuration manager for AXPOC application.

    Stripped all non-relevant code for log-configuration.

    """

    def __init__(self, config_dir: Optional[str] = None) -> None:
        """Initialize configuration manager.

        Args:
            config_dir: Directory containing configuration files. If None, REQUIRES AXPOC_CONFIG_PATH env var.

        Raises:
            ConfigurationError: If AXPOC_CONFIG_PATH is not set and config_dir is None
        """
        # CRITICAL: REQUIRE AXPOC_CONFIG_PATH environment variable in production
        # This ensures we always know where the mounted config directory is
        if config_dir is None:
            config_dir = os.getenv("AXPOC_CONFIG_PATH")
            if not config_dir:
                error_msg = (
                    "AXPOC_CONFIG_PATH environment variable is required but not set. "
                    "This variable must point to the mounted configuration directory (e.g., /app/config). "
                    "Please set AXPOC_CONFIG_PATH in your environment or docker-compose.yml."
                )
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.yaml"
        # DO NOT STORE config here - it will be loaded fresh on every get_config() call

        # Load environment variables from .env file ONLY if it exists
        # This allows the app to work in CI/CD environments where env vars are set directly
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv()
            logger.info("Loaded environment variables from .env file")
        else:
            logger.info("No .env file found, using environment variables directly")

        # Validate that configuration CAN be loaded (but don't cache it)
        try:
            _ = self._load_configuration()
            logger.info("Configuration validation passed on startup")
        except Exception as e:
            logger.exception("Failed to load configuration on startup")
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _load_configuration(self) -> AppConfig:
        """Load configuration from environment variables and config files.

        CRITICAL: This method creates a NEW AppConfig instance every time.
        It NEVER caches or reuses previous instances.

        Returns:
            Fresh AppConfig instance loaded from disk and environment
        """
        try:
            # Create fresh config instance - NEVER reuse cached one
            config = AppConfig()

            # Load from environment variables first
            self._load_from_env(config)

            logger.debug("Configuration loaded successfully from disk")
            return config

        except Exception as e:
            logger.exception("Failed to load configuration")
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _load_from_env(self, config: AppConfig) -> None:
        """Load configuration from environment variables.

        Args:
            config: AppConfig instance to populate (never cached)
        """

        # Some specific code of other app deleted for brevity

        # Logging
        config.log_level = os.getenv("AXPOC_LOG_LEVEL", config.log_level)
        config.log_file = os.getenv("AXPOC_LOG_FILE")
