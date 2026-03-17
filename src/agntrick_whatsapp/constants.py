"""Framework constants."""

from pathlib import Path

import platformdirs

# Data directory for persistent data (follows OS conventions)
DATA_DIR = Path(platformdirs.user_data_dir("agntrick-whatsapp"))

# Logs directory
LOGS_DIR = Path(platformdirs.user_log_dir("agntrick-whatsapp"))
