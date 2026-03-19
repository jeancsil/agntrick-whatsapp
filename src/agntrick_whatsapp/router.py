"""WhatsAppRouterAgent for routing messages to appropriate agents.

This version supports both:
- Business API mode (WhatsApp Business API with access_token)
- Bridge mode (whatsmeow/QR Code with storage_path, allowed_contact)
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List

from .base import BaseWhatsAppMessage
from .channel import WhatsAppChannel
from .commands import CommandParser

if TYPE_CHECKING:
    from .config import WhatsAppRouterConfig

logger = logging.getLogger(__name__)

# Constants
SCHEDULER_INTERVAL_SECONDS = 10


# System prompts
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant communicating through WhatsApp.
Be concise and friendly in your responses.
Avoid overly long explanations.
Use emojis occasionally to be more conversational.
If you need to show code or data, use formatted text blocks.
Focus on being helpful and direct.
"""

# Router initialization now accepts a Channel object directly
# The channel can be either Business API or Bridge implementation
# and will provide the appropriate methods (send, listen, shutdown, initialize)


class WhatsAppRouterAgent:
    """Agent that routes WhatsApp messages to appropriate handlers.

    Args:
        channel: The WhatsAppChannel instance to use (can be Business API or Bridge).
        model_name: Optional name of LLM model to use.
        temperature: The temperature for LLM responses (default: 0.7).
        mcp_servers_override: Optional override for MCP servers.
        audio_transcriber_config: Optional audio transcription config.
        agent: Optional pre-built agent instance to use for LLM responses.
        db: Optional Database instance for storage operations. If None, the
            default database is used lazily on first storage access.
    """

    def __init__(
        self,
        channel: WhatsAppChannel,
        model_name: str | None = None,
        temperature: float = 0.7,
        mcp_servers_override: list[str] | None = None,
        audio_transcriber_config: Any = None,
        agent: Any = None,
        db: Any = None,
    ) -> None:
        self.channel = channel
        self._model_name = model_name
        self._temperature = temperature
        self._running = False
        self._listen_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._mcp_servers_override = mcp_servers_override
        self._audio_transcriber_config = audio_transcriber_config
        self._agent = agent
        self._config: "WhatsAppRouterConfig | None" = None
        self._db = db
        self._note_repo: Any = None
        self._task_repo: Any = None

        # Message history
        self.message_history: List[Dict[str, Any]] = []
        self.conversations: Dict[str, Dict[str, Any]] = {}

        # Command parser
        self._command_parser = CommandParser()

        logger.info(f"WhatsAppRouterAgent initialized with channel type: {type(channel).__name__}")

    @classmethod
    def from_config(cls, channel: "WhatsAppChannel", config: "WhatsAppRouterConfig") -> "WhatsAppRouterAgent":
        """Construct a WhatsAppRouterAgent from a WhatsAppRouterConfig.

        Args:
            channel: The WhatsAppChannel instance to use.
            config: A WhatsAppRouterConfig instance.

        Returns:
            A configured WhatsAppRouterAgent instance.
        """
        instance = cls(channel=channel)
        instance._config = config
        if config.debug_mode:
            logging.getLogger("agntrick_whatsapp").setLevel(logging.DEBUG)
        return instance

    async def start(self) -> None:
        """Start WhatsApp router agent."""
        if self._running:
            logger.warning("Agent is already running")
            return

        logger.info("Starting WhatsApp router agent...")
        self._running = True
        try:
            # Initialize channel (works for both implementations)
            if hasattr(self.channel, "initialize"):
                await self.channel.initialize()

            # Set up MCP servers
            self._mcp_servers = self._mcp_servers_override or ["fetch"]

            # Initialize a generic agent if one was not injected
            if self._agent is None:
                # Import lazily to avoid circular dependencies if agntrick is linked
                from agntrick.agent import AgentBase  # type: ignore[import-untyped]

                class DefaultRouterAgent(AgentBase):
                    @property
                    def system_prompt(self) -> str:
                        return DEFAULT_SYSTEM_PROMPT

                    def local_tools(self) -> list:
                        return []

                self._agent = DefaultRouterAgent(
                    model_name=self._model_name,
                    temperature=self._temperature,
                )

            # Start listening for messages in a supervised background task
            self._listen_task = asyncio.create_task(self.channel.listen(self._handle_message))

        except Exception as e:
            logger.error(f"Failed to start WhatsApp router agent: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop WhatsApp router agent."""
        if not self._running:
            return

        logger.info("Stopping WhatsApp router agent...")
        self._running = False

        # Signal shutdown to all components
        self._shutdown_event.set()

        # Cancel listen task if it exists
        if hasattr(self, "_listen_task") and self._listen_task is not None:
            self._listen_task.cancel()

        # Shut down channel
        try:
            if hasattr(self.channel, "shutdown"):
                await self.channel.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        logger.info("WhatsApp router agent stopped")

    async def _handle_message(self, incoming: Any) -> None:
        """Handle an incoming message from the channel.

        The incoming message format depends on channel implementation:
        - Business API: Dict with 'entry', 'changes', etc.
        - Bridge: BaseWhatsAppMessage with text, sender_id, etc.
        """
        logger.info(f"Processing message: {incoming}")

        try:
            message_text = None
            # Extract text (handling dict or object based on channel format)
            if isinstance(incoming, dict) and "text" in incoming:
                message_text = incoming.get("text", "")
            elif hasattr(incoming, "text") and incoming.text:
                message_text = incoming.text

            if not message_text:
                return

            # Check for commands using the stored command parser
            command = self._command_parser.parse(message_text)
            logger.info(f"Parsed command: {command}")

            # Handle built-in commands; unrecognised slash-commands fall
            # through to the LLM agent so prefixes like /ollama are
            # forwarded as regular prompts.
            if command.command:
                sender_id = self._get_sender_id(incoming)
                response = await self._handle_command(command, sender_id)
                if response is not None:
                    await self._send_response(incoming, response)
                    return

            # Process through the LLM agent
            if self._agent:
                result = await self._agent.run(message_text)
                await self._send_response(incoming, str(result))
            else:
                response = f"Received (No LLM Agent): {message_text}"
                await self._send_response(incoming, response)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

            try:
                # Send error response if possible
                if isinstance(incoming, dict) and "sender_id" in incoming:
                    await self._send_response(incoming, "Sorry, I encountered an error processing your message.")
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")

    async def _send_response(self, incoming: Any, response: str) -> None:
        """Send a response message through the channel.

        The incoming object format varies by channel type:
        - Bridge: Has sender_id, can be dict with text
        - Business API: Has from_number, to_number

        We normalize to get the recipient number and text.
        """
        # Get recipient based on incoming format
        if isinstance(incoming, dict):
            recipient_id = incoming.get("sender_id", "")
            text = response
        elif isinstance(incoming, BaseWhatsAppMessage):
            recipient_id = incoming.to_number
            text = response
        else:
            logger.warning(f"Unknown incoming format: {type(incoming)}")
            return

        # Send through the channel
        await self.channel.send_message(recipient_id, text)
        logger.info(f"Response sent to {recipient_id}")

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _get_repos(self) -> tuple[Any, Any]:
        """Get or create note and task repositories.

        Returns:
            A tuple of (WhatsAppNoteRepository, TaskRepository).
        """
        if self._note_repo is None or self._task_repo is None:
            from agntrick_whatsapp.storage import (
                TaskRepository,
                WhatsAppNoteRepository,
                get_default_db,
            )

            db = self._db or get_default_db()
            self._note_repo = WhatsAppNoteRepository(db)
            self._task_repo = TaskRepository(db)
        return self._note_repo, self._task_repo

    def _get_sender_id(self, incoming: Any) -> str:
        """Extract sender ID from an incoming message.

        Args:
            incoming: The incoming message object (dict or BaseWhatsAppMessage).

        Returns:
            The sender ID string, or "unknown" if it cannot be determined.
        """
        if isinstance(incoming, dict):
            return str(incoming.get("sender_id", "unknown"))
        if hasattr(incoming, "sender_id"):
            return str(incoming.sender_id)
        return "unknown"

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def _handle_command(self, command: Any, sender_id: str) -> str | None:
        """Handle a parsed command and return a response string.

        Args:
            command: ParsedCommand with .command and .args attributes.
            sender_id: The sender's ID for scoping storage operations.

        Returns:
            Response text for built-in commands, or ``None`` if the command
            is not recognised (so the caller can fall through to the LLM).
        """
        cmd = command.command
        args = command.args

        if cmd == "note":
            return await self._cmd_note(args, sender_id)
        elif cmd == "notes":
            return await self._cmd_notes(sender_id)
        elif cmd == "remind":
            return await self._cmd_remind(args, sender_id)
        elif cmd == "schedule":
            return await self._cmd_schedule(args, sender_id)
        elif cmd == "help":
            return self._cmd_help()
        else:
            logger.info("Unrecognised command /%s — forwarding to LLM agent", cmd)
            return None

    async def _cmd_note(self, args: list[str], sender_id: str) -> str:
        """Save a note for the sender.

        Args:
            args: Tokenised arguments; joined to form the note content.
            sender_id: The sender's ID used as context for the note.

        Returns:
            Confirmation message or usage hint if no content was provided.
        """
        if not args:
            return "Usage: /note <content>"
        content = " ".join(args)
        note_repo, _ = self._get_repos()
        from agntrick_whatsapp.storage import Note

        note = Note(content=content, context_id=sender_id)
        note_repo.save(note)
        return f"Note saved: {content}"

    async def _cmd_notes(self, sender_id: str) -> str:
        """List all notes saved by the sender.

        Args:
            sender_id: The sender's ID used to filter notes.

        Returns:
            Numbered list of notes or a message indicating no notes exist.
        """
        note_repo, _ = self._get_repos()
        notes = note_repo.list_by_context(sender_id)
        if not notes:
            return "No notes found."
        lines = [f"{i + 1}. {note.content}" for i, note in enumerate(notes)]
        return "Your notes:\n" + "\n".join(lines)

    async def _cmd_remind(self, args: list[str], sender_id: str) -> str:
        """Set a one-off or recurring reminder.

        Args:
            args: Tokenised arguments where the first token is the time
                expression and the rest form the reminder message.
            sender_id: The sender's ID used as context for the task.

        Returns:
            Confirmation message with parsed datetime, or an error string
            if the time expression cannot be parsed.
        """
        if len(args) < 2:
            return "Usage: /remind <time> <message>\nExample: /remind 'in 30 minutes' call doctor"
        time_str = args[0]
        message = " ".join(args[1:])
        try:
            from agntrick_whatsapp.storage import ScheduledTask, TaskType, parse_natural_time

            parsed_dt, cron_expr = parse_natural_time(time_str)
            task = ScheduledTask(
                action_type=TaskType.SEND_MESSAGE,
                action_prompt=message,
                context_id=sender_id,
                execute_at=parsed_dt.timestamp(),
                cron_expression=cron_expr,
            )
            _, task_repo = self._get_repos()
            task_repo.save(task)
            return f"Reminder set for {parsed_dt.strftime('%Y-%m-%d %H:%M')}: {message}"
        except ValueError as e:
            return f"Could not parse time '{time_str}': {e}"

    async def _cmd_schedule(self, args: list[str], sender_id: str) -> str:
        """Schedule a recurring message using a cron expression.

        Args:
            args: Tokenised arguments where the first token is the cron
                expression and the rest form the recurring message.
            sender_id: The sender's ID used as context for the task.

        Returns:
            Confirmation message, or an error string if the cron expression
            is invalid.
        """
        if len(args) < 2:
            return "Usage: /schedule <cron_expression> <message>\nExample: /schedule '0 9 * * *' Good morning!"
        cron_expr = args[0]
        message = " ".join(args[1:])
        try:
            from agntrick_whatsapp.storage import ScheduledTask, TaskType, calculate_next_run

            next_run = calculate_next_run(cron_expr)
            task = ScheduledTask(
                action_type=TaskType.SEND_MESSAGE,
                action_prompt=message,
                context_id=sender_id,
                execute_at=next_run.timestamp(),
                cron_expression=cron_expr,
            )
            _, task_repo = self._get_repos()
            task_repo.save(task)
            return f"Scheduled: '{message}' (cron: {cron_expr})"
        except ValueError as e:
            return f"Invalid cron expression '{cron_expr}': {e}"

    def _cmd_help(self) -> str:
        """Return the help text listing all available commands.

        Returns:
            A multi-line help string.
        """
        return (
            "Available commands:\n"
            "/note <content> - Save a note\n"
            "/notes - List your notes\n"
            "/remind <time> <message> - Set a reminder "
            "(e.g., /remind 'in 30 minutes' call doctor)\n"
            "/schedule <cron> <message> - Schedule recurring message "
            "(e.g., /schedule '0 9 * * *' Good morning)\n"
            "/help - Show this help"
        )
