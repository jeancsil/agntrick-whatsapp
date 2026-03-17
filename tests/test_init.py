"""Tests for agntrick_whatsapp package initialization."""

from unittest.mock import patch


def test_version_is_accessible() -> None:
    """Test that __version__ is accessible from the package."""
    from agntrick_whatsapp import __version__

    assert isinstance(__version__, str)
    assert __version__ != ""


def test_version_is_known() -> None:
    """Test that __version__ returns a version (not 'unknown') when installed."""
    from agntrick_whatsapp import __version__

    # When installed with uv, version should be resolved
    assert __version__ != "unknown"


def test_all_exports() -> None:
    """Test that __all__ contains expected exports."""
    from agntrick_whatsapp import __all__

    assert "__version__" in __all__


def test_version_fallback_when_not_installed() -> None:
    """Test that __version__ falls back to 'unknown' when package is not found."""
    import importlib
    import importlib.metadata

    import agntrick_whatsapp

    # Re-run the version resolution logic with a mock that raises PackageNotFoundError
    with patch.object(importlib.metadata, "version", side_effect=importlib.metadata.PackageNotFoundError("test")):
        # Re-execute the module-level code by reimporting
        importlib.reload(agntrick_whatsapp)
        assert agntrick_whatsapp.__version__ == "unknown"

    # Reload again to restore the real version
    importlib.reload(agntrick_whatsapp)
