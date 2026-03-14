"""Time parsing utilities for scheduling tasks."""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

import croniter
from dateutil.relativedelta import relativedelta


class TimeParser:
    """Utility class for parsing and converting various time formats."""

    @staticmethod
    def parse_time_input(time_input: str) -> Tuple[datetime, str]:
        """Parse various time input formats and return datetime and description.

        Args:
            time_input: Time string in various formats.

        Returns:
            Tuple of (datetime, description).

        Examples:
            parse_time_input("in 2 hours") -> (datetime, "2 hours from now")
            parse_time_input("tomorrow at 9am") -> (datetime, "tomorrow at 9:00 AM")
            parse_time_input("next Monday") -> (datetime, "next Monday")
            parse_time_input("2024-12-25 10:00") -> (datetime, "2024-12-25 10:00:00")
        """
        now = datetime.now()
        time_input = time_input.lower().strip()

        # Handle "in X [unit]" format
        if time_input.startswith("in "):
            return TimeParser._parse_relative_time(time_input[3:], now)

        # Handle specific datetime formats
        if re.match(r"\d{4}-\d{2}-\d{2}", time_input):
            return TimeParser._parse_datetime(time_input)

        # Handle relative day names
        if time_input.startswith("next "):
            return TimeParser._parse_next_weekday(time_input[5:], now)

        # Handle simple time like "9am", "3:30pm"
        if re.match(r"\d{1,2}:\d{2}\s*(am|pm)|\d{1,2}\s*(am|pm)", time_input):
            return TimeParser._parse_simple_time(time_input, now)

        # Handle day names
        if time_input in ["today", "tomorrow", "yesterday"]:
            return TimeParser._parse_special_day(time_input, now)

        raise ValueError(f"Unable to parse time input: {time_input}")

    @staticmethod
    def _parse_relative_time(time_str: str, base_time: datetime) -> Tuple[datetime, str]:
        """Parse relative time expressions like "2 hours", "3 days", "1 week"."""
        words = time_str.split()
        if len(words) != 2:
            raise ValueError(f"Invalid relative time format: {time_str}")

        amount = int(words[0])
        unit = words[1]

        if unit.endswith("s"):
            unit = unit[:-1]  # Remove plural 's'

        delta_map = {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": relativedelta(months=amount),
            "year": relativedelta(years=amount),
        }

        if unit not in delta_map:
            raise ValueError(f"Unsupported time unit: {unit}")

        if unit == "month":
            result_time = base_time + relativedelta(months=amount)
        elif unit == "year":
            result_time = base_time + relativedelta(years=amount)
        else:
            if unit == "week":
                result_time = base_time + timedelta(weeks=amount)
            elif unit == "day":
                result_time = base_time + timedelta(days=amount)
            elif unit == "hour":
                result_time = base_time + timedelta(hours=amount)
            elif unit == "minute":
                result_time = base_time + timedelta(minutes=amount)
        description = f"{amount} {unit}{'s' if amount != 1 else ''} from now"

        return result_time, description
        description = f"{amount} {unit}{'s' if amount != 1 else ''} from now"

        return result_time, description

    @staticmethod
    def _parse_datetime(datetime_str: str) -> Tuple[datetime, str]:
        """Parse datetime string in format YYYY-MM-DD HH:MM or YYYY-MM-DD."""
        try:
            if " " in datetime_str:
                return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"), datetime_str
            else:
                dt = datetime.strptime(datetime_str, "%Y-%m-%d")
                return dt, datetime_str
        except ValueError:
            raise ValueError(f"Invalid datetime format: {datetime_str}")

    @staticmethod
    def _parse_next_weekday(weekday: str, base_time: datetime) -> Tuple[datetime, str]:
        """Parse "next <weekday>" format."""
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        weekday = weekday.lower()
        if weekday not in weekday_map:
            raise ValueError(f"Invalid weekday: {weekday}")

        target_weekday = weekday_map[weekday]
        current_weekday = base_time.weekday()

        days_ahead = (target_weekday - current_weekday + 7) % 7
        if days_ahead == 0:
            days_ahead = 7  # Next week

        result_time = base_time + timedelta(days=days_ahead)
        return result_time, f"next {weekday.capitalize()}"

    @staticmethod
    def _parse_simple_time(time_str: str, base_time: datetime) -> Tuple[datetime, str]:
        """Parse simple time expressions like "9am", "3:30pm"."""
        time_str = time_str.lower().replace(" ", "")

        if "am" in time_str or "pm" in time_str:
            # Convert 12-hour format to 24-hour
            if "am" in time_str:
                time_part = time_str.replace("am", "")
                is_pm = False
            else:
                time_part = time_str.replace("pm", "")
                is_pm = True

            if ":" in time_part:
                hour, minute = map(int, time_part.split(":"))
            else:
                hour = int(time_part)
                minute = 0

            # Adjust for 12-hour format
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0

            result_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return result_time, f"{hour:02d}:{minute:02d} {'PM' if is_pm else 'AM'}"

        raise ValueError(f"Invalid time format: {time_str}")

    @staticmethod
    def _parse_special_day(day: str, base_time: datetime) -> Tuple[datetime, str]:
        """Parse special day names like "today", "tomorrow", "yesterday"."""
        if day == "today":
            return base_time.replace(hour=9, minute=0, second=0, microsecond=0), "today at 9:00 AM"
        elif day == "tomorrow":
            tomorrow = base_time + timedelta(days=1)
            return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0), "tomorrow at 9:00 AM"
        elif day == "yesterday":
            yesterday = base_time - timedelta(days=1)
            return yesterday.replace(hour=9, minute=0, second=0, microsecond=0), "yesterday at 9:00 AM"
        else:
            raise ValueError(f"Invalid special day: {day}")

    @staticmethod
    def validate_cron_expression(cron_expr: str) -> bool:
        """Validate a cron expression.

        Args:
            cron_expr: Cron expression string.

        Returns:
            True if valid, False otherwise.
        """
        try:
            croniter.croniter(cron_expr)
            return True
        except (ValueError, KeyError):
            return False

    @staticmethod
    def get_next_run_time(cron_expr: str) -> Optional[datetime]:
        """Get the next run time for a cron expression.

        Args:
            cron_expr: Cron expression string.

        Returns:
            Next run datetime or None if invalid.
        """
        try:
            cron = croniter.croniter(cron_expr)
            return datetime.fromtimestamp(cron.get_current())
        except (ValueError, KeyError):
            return None

    @staticmethod
    def cron_to_description(cron_expr: str) -> str:
        """Convert cron expression to human-readable description.

        Args:
            cron_expr: Cron expression string.

        Returns:
            Human-readable description.
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            return "Invalid cron expression"

        minute, hour, day, month, weekday = parts

        descriptions = []

        if minute != "*":
            descriptions.append(f"minute {minute}")
        if hour != "*":
            descriptions.append(f"hour {hour}")
        if day != "*":
            descriptions.append(f"day {day}")
        if month != "*":
            descriptions.append(f"month {month}")
        if weekday != "*":
            descriptions.append(f"weekday {weekday}")

        if len(descriptions) == 0:
            return "Every minute"
        else:
            return " and ".join(descriptions)
