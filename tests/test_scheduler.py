"""Test cases for scheduling time parsing."""

import pytest
from datetime import datetime, time
from unittest.mock import Mock, patch

from agntrick_whatsapp.scheduler import TimeParser, ScheduleManager


class TestTimeParser:
    """Test cases for TimeParser class."""

    def test_parse_simple_time(self):
        """Test parsing a simple time string."""
        parser = TimeParser()
        result = parser.parse("9am")
        assert result == time(9, 0)

    def test_parse_time_with_minutes(self):
        """Test parsing time with minutes."""
        parser = TimeParser()
        result = parser.parse("9:30am")
        assert result == time(9, 30)

    def test_parse_24hour_time(self):
        """Test parsing 24-hour format time."""
        parser = TimeParser()
        result = parser.parse("14:00")
        assert result == time(14, 0)

    def test_parse_invalid_time(self):
        """Test parsing invalid time."""
        parser = TimeParser()
        with pytest.raises(ValueError):
            parser.parse("25:00")

    def test_parse_time_period(self):
        """Test parsing time with period indicator."""
        parser = TimeParser()
        result = parser.parse("9pm")
        assert result == time(21, 0)

    def test_parse_relative_time(self):
        """Test parsing relative time."""
        parser = TimeParser()
        with patch('agntrick_whatsapp.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0)
            result = parser.parse("in 30 minutes")
            expected = datetime(2024, 1, 1, 10, 30)
            assert result == expected


class TestScheduleManager:
    """Test cases for ScheduleManager class."""

    def test_init(self):
        """Test schedule manager initialization."""
        manager = ScheduleManager()
        assert manager is not None

    def test_add_schedule(self):
        """Test adding a new schedule."""
        manager = ScheduleManager()
        schedule_id = manager.add_schedule(
            command="/hello",
            cron_expression="0 9 * * *",
            user_id="12345"
        )
        assert schedule_id is not None
        assert len(manager.schedules) == 1

    def test_get_schedules_for_user(self):
        """Test getting schedules for a specific user."""
        manager = ScheduleManager()
        manager.add_schedule(
            command="/hello",
            cron_expression="0 9 * * *",
            user_id="12345"
        )
        manager.add_schedule(
            command="/world",
            cron_expression="0 10 * * *",
            user_id="12345"
        )

        schedules = manager.get_schedules_for_user("12345")
        assert len(schedules) == 2

    def test_remove_schedule(self):
        """Test removing a schedule."""
        manager = ScheduleManager()
        schedule_id = manager.add_schedule(
            command="/hello",
            cron_expression="0 9 * * *",
            user_id="12345"
        )

        manager.remove_schedule(schedule_id)
        assert len(manager.schedules) == 0

    def test_get_next_execution_time(self):
        """Test getting the next execution time."""
        manager = ScheduleManager()
        schedule_id = manager.add_schedule(
            command="/hello",
            cron_expression="0 9 * * *",
            user_id="12345"
        )

        next_time = manager.get_next_execution_time(schedule_id)
        assert isinstance(next_time, datetime)

    def test_validate_cron_expression(self):
        """Test validating cron expressions."""
        manager = ScheduleManager()

        # Valid expressions
        assert manager.validate_cron_expression("0 9 * * *") is True
        assert manager.validate_cron_expression("*/5 * * * *") is True

        # Invalid expressions
        assert manager.validate_cron_expression("invalid") is False
        assert manager.validate_cron_expression("0 9 * * * *") is False

    def test_list_active_schedules(self):
        """Test listing all active schedules."""
        manager = ScheduleManager()
        manager.add_schedule(
            command="/hello",
            cron_expression="0 9 * * *",
            user_id="12345"
        )

        schedules = manager.list_active_schedules()
        assert len(schedules) == 1
        assert schedules[0]["command"] == "/hello"