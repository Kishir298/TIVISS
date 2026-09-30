from .config import ConfigValidationError, TIVISSConfig
from .config import TIVISSConfig

# Global settings instance loaded from environment
settings = TIVISSConfig.load_env()

__all__ = ["ConfigValidationError", "TIVISSConfig", "settings"]
