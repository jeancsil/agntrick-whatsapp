"""Test cases for command parsing and execution."""

import pytest
from unittest.mock import Mock, patch

from agntrick_whatsapp.commands import CommandParser, CommandExecutor


class TestCommandParser:
    """Test cases for CommandParser class."""

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        parser = CommandParser()
        result = parser.parse("/hello")
        assert result == {"command": "hello", "args": []}

    def test_parse_command_with_args(self):
        """Test parsing a command with arguments."""
        parser = CommandParser()
        result = parser.parse("/schedule daily 9am")
        assert result == {"command": "schedule", "args": ["daily", "9am"]}

    def test_parse_command_with_kwargs(self):
        """Test parsing a command with keyword arguments."""
        parser = CommandParser()
        result = parser.parse("/task create --name test --priority high")
        assert result == {
            "command": "task",
            "action": "create",
            "kwargs": {"name": "test", "priority": "high"}
        }

    def test_parse_invalid_command(self):
        """Test parsing an invalid command."""
        parser = CommandParser()
        with pytest.raises(ValueError):
            parser.parse("invalid_command")

    def test_parse_empty_command(self):
        """Test parsing an empty command."""
        parser = CommandParser()
        with pytest.raises(ValueError):
            parser.parse("")


class TestCommandExecutor:
    """Test cases for CommandExecutor class."""

    @patch('agntrick_whatsapp.commands.CommandRouter')
    def test_execute_command(self, mock_router):
        """Test executing a command."""
        executor = CommandExecutor()
        executor.execute("/hello")
        mock_router.process_command.assert_called_once_with("hello", [])

    def test_execute_unknown_command(self):
        """Test executing an unknown command."""
        executor = CommandExecutor()
        result = executor.execute("/unknown")
        assert "Unknown command" in result

    def test_execute_command_with_error(self):
        """Test executing a command that raises an error."""
        executor = CommandExecutor()
        with patch('agntrick_whatsapp.commands.CommandRouter.process_command') as mock_process:
            mock_process.side_effect = Exception("Test error")
            result = executor.execute("/hello")
            assert "Error executing command" in result