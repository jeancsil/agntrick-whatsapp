"""Tests for agntrick_whatsapp constants."""

from pathlib import Path


def test_data_dir_is_absolute_path():
    """DATA_DIR should be an absolute Path."""
    from agntrick_whatsapp.constants import DATA_DIR

    assert isinstance(DATA_DIR, Path)
    assert DATA_DIR.is_absolute()


def test_logs_dir_is_absolute_path():
    """LOGS_DIR should be an absolute Path."""
    from agntrick_whatsapp.constants import LOGS_DIR

    assert isinstance(LOGS_DIR, Path)
    assert LOGS_DIR.is_absolute()


def test_data_dir_contains_app_name():
    """DATA_DIR should contain the app name."""
    from agntrick_whatsapp.constants import DATA_DIR

    assert "agntrick-whatsapp" in str(DATA_DIR)


def test_logs_dir_contains_app_name():
    """LOGS_DIR should contain the app name."""
    from agntrick_whatsapp.constants import LOGS_DIR

    assert "agntrick-whatsapp" in str(LOGS_DIR)


def test_base_dir_not_exported():
    """BASE_DIR should no longer be a public constant."""
    import agntrick_whatsapp.constants as c

    assert not hasattr(c, "BASE_DIR"), "BASE_DIR should be removed - use platformdirs instead"
