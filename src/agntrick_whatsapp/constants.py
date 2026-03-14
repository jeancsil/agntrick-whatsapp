"""Framework constants."""

from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory for persistent data
DATA_DIR = BASE_DIR / "data"

# Logs directory
LOGS_DIR = BASE_DIR / "logs"