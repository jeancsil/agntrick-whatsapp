"""Test cases for scheduling time parsing."""

from datetime import datetime
from unittest.mock import patch

import pytest

from agntrick_whatsapp.storage.scheduler import TimeParser


class TestTimeParser:
    """Test cases for TimeParser class."""

    def test_parse_simple_time(self):
        """Test parsing a simple time string."""
        parser = TimeParser()
        result, desc = parser.parse_time_input("9am")
        assert result.hour == 9
        assert result.minute == 0

    def test_parse_time_with_minutes(self):
        """Test parsing time with minutes."""
        parser = TimeParser()
        result, desc = parser.parse_time_input("9:30am")
        assert result.hour == 9
        assert result.minute == 30

    def test_parse_24hour_time(self):
        """Test parsing 24-hour format time."""
        parser = TimeParser()
        result, desc = parser.parse_time_input("14:00")
        assert result.hour == 14
        assert result.minute == 0

    def test_parse_invalid_time(self):
        """Test parsing invalid time."""
        parser = TimeParser()
        with pytest.raises(ValueError):
            parser.parse_time_input("25:00")

    def test_parse_time_period(self):
        """Test parsing time with period indicator."""
        parser = TimeParser()
        result, desc = parser.parse_time_input("9pm")
        assert result.hour == 21
        assert result.minute == 0

    def test_parse_relative_time(self):
        """Test parsing relative time."""
        parser = TimeParser()
        with patch("agntrick_whatsapp.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0)
            result, desc = parser.parse_time_input("in 30 minutes")
            expected = datetime(2024, 1, 1, 10, 30)
            assert result == expected


# ScheduleManager tests removed - class not yet implemented
