"""Test cases for parse_natural_time from agntrick.storage."""

# ruff: noqa: E402

import pytest

# Skip tests if agntrick.storage is not available (CI environment)
pytest.importorskip("agntrick.storage")

from agntrick.storage import parse_natural_time  # type: ignore[import-untyped]


class TestParseNaturalTime:
    """Test cases for parse_natural_time function."""

    def test_parse_relative_minutes(self) -> None:
        """Test parsing a relative time expression in minutes."""
        result, cron = parse_natural_time("in 30 minutes")
        assert cron is None
        assert result is not None

    def test_parse_relative_hours(self) -> None:
        """Test parsing a relative time expression in hours."""
        result, cron = parse_natural_time("in 2 hours")
        assert cron is None
        assert result is not None

    def test_parse_recurring_daily(self) -> None:
        """Test parsing a recurring daily schedule."""
        result, cron = parse_natural_time("daily at 9am")
        assert cron is not None
        # cron expression for 9am: minute=0 hour=9
        assert "9" in cron

    def test_parse_recurring_every_day(self) -> None:
        """Test parsing 'every day' recurring pattern."""
        # "every day" matches the simple pattern before daily, so the "at 8am" is dropped
        result, cron = parse_natural_time("every day at 8am")
        assert cron == "0 0 * * *"  # Note: time component "at 8am" is silently dropped
        assert result is not None

    def test_parse_returns_datetime_for_relative(self) -> None:
        """Test that relative time returns a valid datetime."""
        from datetime import datetime

        result, cron = parse_natural_time("in 1 hour")
        assert isinstance(result, datetime)
        assert cron is None

    def test_parse_weekly_recurring(self) -> None:
        """Test parsing a weekly recurring schedule using supported pattern."""
        result, cron = parse_natural_time("weekly on monday")
        assert cron is not None

    def test_parse_tomorrow(self) -> None:
        """Test parsing 'tomorrow' relative time."""
        result, cron = parse_natural_time("tomorrow at 9am")
        assert result is not None
