"""Test cases for command parsing and execution."""

import pytest

from agntrick_whatsapp.commands import CommandHandler, CommandParser


class TestCommandParser:
    """Test cases for CommandParser class."""

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        parser = CommandParser()
        result = parser.parse("/hello")
        assert result == {"command": "hello", "args": [], "raw_text": "/hello"}

    def test_parse_command_with_args(self):
        """Test parsing a command with arguments."""
        parser = CommandParser()
        result = parser.parse("/schedule daily 9am")
        assert result == {"command": "schedule", "args": ["daily", "9am"], "raw_text": "/schedule daily 9am"}

    def test_parse_command_with_kwargs(self):
        """Test parsing a command with keyword arguments."""
        parser = CommandParser()
        result = parser.parse("/task create --name test --priority high")
        assert result == {
            "command": "task",
            "args": ["create", "--name", "test", "--priority", "high"],
            "raw_text": "/task create --name test --priority high",
        }

    def test_parse_invalid_command(self):
        """Test parsing an invalid command."""
        parser = CommandParser()
        result = parser.parse("invalid_command")
        assert result == {"command": None, "args": [], "raw_text": "invalid_command"}

    def test_parse_empty_command(self):
        """Test parsing an empty command."""
        parser = CommandParser()
        result = parser.parse("")
        assert result == {"command": None, "args": [], "raw_text": ""}


class TestCommandHandler:
    """Test cases for CommandHandler class."""

    @pytest.mark.asyncio
    async def test_handle_text_message(self):
        """Test handling a regular text message."""
        handler = CommandHandler()
        result = await handler.handle("Hello world")
        assert result["status"] == "text"
        assert "Hello world" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self):
        """Test handling an unknown command."""
        handler = CommandHandler()
        result = await handler.handle("/unknown")
        assert result["status"] == "error"
        assert "Unknown command" in result["message"]

    @pytest.mark.asyncio
    async def test_handle_registered_command(self):
        """Test handling a registered command."""
        handler = CommandHandler()

        async def mock_handler(parsed):
            return {"status": "success", "message": "Command executed"}

        handler.register_command("test", mock_handler)
        result = await handler.handle("/test")
        assert result["status"] == "success"
        assert result["message"] == "Command executed"

    @pytest.mark.asyncio
    async def test_handle_command_with_error(self):
        """Test handling a command that raises an error."""
        handler = CommandHandler()

        async def error_handler(parsed):
            raise ValueError("Test error")

        handler.register_command("error", error_handler)
        result = await handler.handle("/error")
        assert result["status"] == "error"
