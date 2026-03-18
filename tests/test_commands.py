"""Test cases for command parsing and execution."""

import pytest

from agntrick_whatsapp.commands import CommandHandler, CommandParser, CommandType, ParsedCommand


class TestCommandParser:
    """Test cases for CommandParser class."""

    def test_parse_simple_command(self):
        """Test parsing a simple command."""
        parser = CommandParser()
        result = parser.parse("/hello")
        assert isinstance(result, ParsedCommand)
        assert result.command == "hello"
        assert result.args == []
        assert result.raw_text == "/hello"
        assert result.command_type == CommandType.COMMAND

    def test_parse_command_with_args(self):
        """Test parsing a command with arguments."""
        parser = CommandParser()
        result = parser.parse("/schedule daily 9am")
        assert isinstance(result, ParsedCommand)
        assert result.command == "schedule"
        assert result.args == ["daily", "9am"]
        assert result.raw_text == "/schedule daily 9am"

    def test_parse_command_with_kwargs(self):
        """Test parsing a command with keyword arguments."""
        parser = CommandParser()
        result = parser.parse("/task create --name test --priority high")
        assert isinstance(result, ParsedCommand)
        assert result.command == "task"
        assert result.args == ["create", "--name", "test", "--priority", "high"]
        assert result.raw_text == "/task create --name test --priority high"

    def test_parse_invalid_command(self):
        """Test parsing an invalid command."""
        parser = CommandParser()
        result = parser.parse("invalid_command")
        assert isinstance(result, ParsedCommand)
        assert result.command is None
        assert result.args == []
        assert result.raw_text == "invalid_command"
        assert result.command_type == CommandType.TEXT

    def test_parse_empty_command(self):
        """Test parsing an empty command."""
        parser = CommandParser()
        result = parser.parse("")
        assert isinstance(result, ParsedCommand)
        assert result.command is None
        assert result.args == []
        assert result.raw_text == ""
        assert result.command_type == CommandType.TEXT

    def test_parse_schedule_command_type(self):
        """Test that schedule commands return SCHEDULE command type."""
        parser = CommandParser()
        result = parser.parse("/schedule daily at 09:00 send report")
        assert isinstance(result, ParsedCommand)
        assert result.command == "schedule"
        assert result.command_type == CommandType.SCHEDULE

    def test_parse_system_command_type(self):
        """Test that system commands return SYSTEM command type."""
        parser = CommandParser()
        result = parser.parse("/system status")
        assert isinstance(result, ParsedCommand)
        assert result.command == "system"
        assert result.command_type == CommandType.SYSTEM

    def test_parse_to_dict(self):
        """Test that ParsedCommand.to_dict() returns the expected dict."""
        parser = CommandParser()
        result = parser.parse("/hello")
        d = result.to_dict()
        assert d["command"] == "hello"
        assert d["args"] == []
        assert d["raw_text"] == "/hello"
        assert d["command_type"] == CommandType.COMMAND.value


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

    @pytest.mark.asyncio
    async def test_handle_command_handler_returns_non_dict(self):
        """Test handling a command whose handler returns a non-dict value."""
        handler = CommandHandler()

        async def bad_handler(parsed):
            return "not a dict"

        handler.register_command("bad", bad_handler)
        result = await handler.handle("/bad")
        assert result["status"] == "error"
        assert "invalid response" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_command_non_callable_handler(self):
        """Test handling a command with a non-callable handler."""
        handler = CommandHandler()
        handler.commands["broken"] = "not a callable"
        result = await handler.handle("/broken")
        assert result["status"] == "error"
        assert "not callable" in result["message"].lower()

    def test_parse_list_command(self):
        """Test parsing a /list command."""
        parser = CommandParser()
        result = parser.parse("/list tasks")
        assert result.command == "list"
        assert result.command_type == CommandType.COMMAND
        assert "tasks" in result.args
