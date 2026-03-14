"""Command parsing and handling for WhatsApp integration."""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum


class CommandType(Enum):
    """Types of commands that can be parsed."""
    TEXT = "text"
    COMMAND = "command"
    SCHEDULE = "schedule"
    MEDIA = "media"
    SYSTEM = "system"


class ParsedCommand:
    """Represents a parsed command with its components."""

    def __init__(
        self,
        command_type: CommandType,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        raw_text: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.command_type = command_type
        self.command = command
        self.args = args or []
        self.raw_text = raw_text
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "command_type": self.command_type.value,
            "command": self.command,
            "args": self.args,
            "raw_text": self.raw_text,
            "metadata": self.metadata
        }


class CommandParser:
    """Parser for WhatsApp commands."""

    def __init__(self, prefix: str = "/"):
        self.prefix = prefix
        # Common command patterns
        self.command_patterns = {
            "schedule": re.compile(rf"^{self.prefix}schedule\s+(.+)", re.IGNORECASE),
            "list": re.compile(rf"^{self.prefix}list\s+(.+)", re.IGNORECASE),
            "help": re.compile(rf"^{self.prefix}help\s*(.*)", re.IGNORECASE),
            "system": re.compile(rf"^{self.prefix}system\s+(.+)", re.IGNORECASE),
        }

    def parse(self, text: str) -> dict:
        """Parse a text message into a command structure."""
        text = text.strip()

        if not text:
            return {
                "command": None,
                "args": []
            }

        # Check for command patterns
        for command_type, pattern in self.command_patterns.items():
            match = pattern.match(text)
            if match:
                args = match.group(1).strip().split() if match.group(1) else []

                # Special handling for different command types
                if command_type == "schedule":
                    return self._parse_schedule_command(text, match, args)
                elif command_type == "list":
                    return self._parse_list_command(text, match, args)
                elif command_type == "help":
                    return self._parse_help_command(text, match, args)
                elif command_type == "system":
                    return self._parse_system_command(text, match, args)

        # If no command prefix, treat as regular text
        if not text.startswith(self.prefix):
            return {
                "command": None,
                "args": []
            }

        # Generic command with prefix
        parts = text[len(self.prefix):].strip().split(maxsplit=1)
        command = parts[0] if parts else None
        args = parts[1].split() if len(parts) > 1 else []

        return {
            "command": command,
            "args": args
        }

    def _parse_schedule_command(self, text: str, match: re.Match, args: List[str]) -> ParsedCommand:
        """Parse schedule command with special handling."""
        # Look for recurring patterns like "every", "daily", "weekly"
        recurring_patterns = {
            "every": re.compile(r"every\s+(\d+)\s+(minutes?|hours?|days?|weeks?)", re.IGNORECASE),
            "daily": re.compile(r"daily\s+at\s+(\d{1,2}:\d{2})", re.IGNORECASE),
            "weekly": re.compile(r"weekly\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.IGNORECASE),
        }

        metadata = {}
        schedule_text = match.group(1)

        # Check for recurring patterns
        for pattern_name, pattern in recurring_patterns.items():
            recurring_match = pattern.search(schedule_text)
            if recurring_match:
                metadata["recurring"] = pattern_name
                metadata["recurring_details"] = recurring_match.group(0)
                break

        # Extract the actual task content
        task_parts = []
        for part in args:
            if not any(re.search(pattern, part) for pattern in recurring_patterns.values()):
                task_parts.append(part)

        return {
            "command": "schedule",
            "args": task_parts
        }

    def _parse_list_command(self, text: str, match: re.Match, args: List[str]) -> ParsedCommand:
        """Parse list command."""
        return {
            "command": "list",
            "args": args
        }

    def _parse_help_command(self, text: str, match: re.Match, args: List[str]) -> ParsedCommand:
        """Parse help command."""
        return {
            "command": "help",
            "args": args
        }

    def _parse_system_command(self, text: str, match: re.Match, args: List[str]) -> ParsedCommand:
        """Parse system command."""
        return {
            "command": "system",
            "args": args
        }


class CommandHandler:
    """Handler for executing parsed commands."""

    def __init__(self) -> None:
        self.commands: dict[str, Any] = {}
        self.parser = CommandParser()

    def register_command(self, command_name: str, handler: Any) -> None:
        """Register a command handler."""
        self.commands[command_name] = handler

    async def handle(self, text: str) -> Dict[str, Any]:
        """Handle a text message and execute appropriate command."""
        parsed = self.parser.parse(text)

        if parsed.get("command") is None:
            return await self._handle_text_message(parsed)
        elif parsed.get("command") in self.commands:
            handler = self.commands[parsed.get("command")]
            if callable(handler):
                result = await handler(parsed)
                if isinstance(result, dict):
                    return result
            return {"status": "error", "message": "Handler returned invalid response"}
        else:
            return {
                "status": "error",
                "message": f"Unknown command: {parsed.get('command')}",
                "parsed": parsed
            }

    async def _handle_text_message(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Handle regular text messages."""
        return {
            "status": "text",
            "message": parsed.get("raw_text", ""),
            "parsed": parsed
        }