"""WhatsAppRouterAgent for routing messages to appropriate agents."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .base import BaseWhatsAppMessage, TextMessage, WhatsAppMessageStatus
from .channel import WhatsAppChannel
from .commands import CommandHandler, CommandParser, ParsedCommand
from .config import WhatsAppRouterConfig


class WhatsAppRouterAgent:
    """Agent that routes WhatsApp messages to appropriate handlers."""

    def __init__(self, config: WhatsAppRouterConfig) -> None:
        self.config = config
        self.channel = WhatsAppChannel(
            config.whatsapp.access_token,
            config.whatsapp.phone_number_id
        )
        self.command_handler = CommandHandler()
        self.message_history: List[Dict[str, Any]] = []
        self.agent_registry: Dict[str, Any] = {}
        self.conversations: Dict[str, Dict[str, Any]] = {}

        # Initialize with default handlers
        self._register_default_handlers()

    def register_agent(self, name: str, agent_class) -> None:
        """Register an agent with the router."""
        self.agent_registry[name] = agent_class
        # Register the agent's commands
        if hasattr(agent_class, 'commands'):
            for command in agent_class.commands:
                handler = getattr(agent_class, 'handle', None)
                if handler:
                    self.command_handler.register_command(command, handler)

    async def process_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming message and route it appropriately."""
        try:
            # Parse the incoming message
            message = await self.channel.receive_message(message_data)
            if not message:
                return {"status": "error", "message": "Invalid message data"}

            # Store in message history
            self._add_to_history(message, "received")

            # Parse as command
            parser = CommandParser()
            parsed = parser.parse(message.text if hasattr(message, 'text') else "")

            # Handle commands
            if parsed.command_type.value == "command" and parsed.command:
                result = await self.command_handler.handle(message.text)
                if result.get("status") == "error":
                    return await self._send_error_response(message, result["message"])
                else:
                    # Send response back
                    await self.channel.send_message(message.from_number, result.get("message", ""))
                    return {"status": "success", "message": "Command processed"}

            # Route to appropriate agent
            agent_name = self._determine_agent(message, parsed)

            if agent_name in self.agent_registry:
                agent = self.agent_registry[agent_name]
                # Update conversation context
                self._update_conversation(message.from_number, agent_name, parsed)

                # Process with agent
                result = await agent.process_message(
                    message,
                    self.conversations.get(message.from_number, {})
                )

                # Send response
                if result and "response" in result:
                    await self.channel.send_message(message.from_number, result["response"])

                return {
                    "status": "success",
                    "agent": agent_name,
                    "message": "Message routed to agent"
                }
            else:
                # No suitable agent found
                response = "I'm not sure how to handle this message. Try using a command like /help for assistance."
                await self.channel.send_message(message.from_number, response)
                return {"status": "handled", "message": "Default response sent"}

        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            print(error_message)

            # Send error response if possible
            if message:
                await self._send_error_response(message, "Sorry, I encountered an error processing your message.")

            return {"status": "error", "message": error_message}

    def _register_default_handlers(self) -> None:
        """Register default command handlers."""
        async def handle_help(parsed: ParsedCommand) -> Dict[str, Any]:
            """Handle help command."""
            help_text = """
Available commands:
/schedule <task> - Schedule a task
/list [type] - List items
/system <command> - System commands
/help [command] - Show help for a specific command
            """
            return {"message": help_text.strip()}

        self.command_handler.register_command("help", handle_help)

        async def handle_list(parsed: ParsedCommand) -> Dict[str, Any]:
            """Handle list command."""
            return {"message": "List functionality not yet implemented"}

        self.command_handler.register_command("list", handle_list)

        async def handle_system(parsed: ParsedCommand) -> Dict[str, Any]:
            """Handle system commands."""
            if not parsed.args:
                return {"message": "Usage: /system <command>"}

            command = parsed.args[0]
            if command == "status":
                return {"message": "WhatsAppRouterAgent is running"}
            elif command == "version":
                return {"message": "Agntrick WhatsApp v0.1.0"}
            else:
                return {"message": f"Unknown system command: {command}"}

        self.command_handler.register_command("system", handle_system)

    def _determine_agent(self, message: BaseWhatsAppMessage, parsed: ParsedCommand) -> str:
        """Determine which agent should handle the message."""
        # Check for explicit agent designation in commands
        if parsed.command_type.value == "command" and parsed.command:
            # Look for agent-specific commands
            for agent_name in self.config.agents:
                if agent_name.name.lower() == parsed.command.lower():
                    return agent_name.name

        # Use default agent if configured
        if self.config.default_agent:
            return self.config.default_agent

        # Fallback to a default agent
        return "default"

    def _update_conversation(self, phone_number: str, agent_name: str, parsed: ParsedCommand) -> None:
        """Update conversation context for a phone number."""
        if phone_number not in self.conversations:
            self.conversations[phone_number] = {
                "current_agent": agent_name,
                "history": [],
                "started_at": datetime.now().isoformat()
            }

        # Update current agent
        self.conversations[phone_number]["current_agent"] = agent_name

        # Add to history
        self.conversations[phone_number]["history"].append({
            "timestamp": datetime.now().isoformat(),
            "message": parsed.raw_text,
            "type": parsed.command_type.value
        })

    def _add_to_history(self, message: BaseWhatsAppMessage, direction: str) -> None:
        """Add message to history."""
        history_entry = {
            "id": message.message_id,
            "timestamp": message.timestamp.isoformat(),
            "direction": direction,
            "from": message.from_number,
            "to": message.to_number,
            "type": getattr(message, 'message_type', 'unknown')
        }

        if hasattr(message, 'text'):
            history_entry["text"] = message.text

        self.message_history.append(history_entry)

        # Enforce history limit
        if len(self.message_history) > self.config.message_history_limit:
            self.message_history = self.message_history[-self.config.message_history_limit:]

    async def _send_error_response(self, message: BaseWhatsAppMessage, error_msg: str) -> None:
        """Send error response to user."""
        await self.channel.send_message(message.from_number, error_msg)