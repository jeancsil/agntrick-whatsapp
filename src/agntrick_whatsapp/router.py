"""WhatsAppRouterAgent for routing messages to appropriate agents.

This version supports both:
- Business API mode (WhatsApp Business API with access_token)
- Bridge mode (whatsmeow/QR Code with storage_path, allowed_contact)
"""

import asyncio
import contextvars
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

# Context variable for passing sender_id through async boundaries
# Used by invoke_agent tool to access conversation memory
_current_sender_id: contextvars.ContextVar[str] = contextvars.ContextVar("sender_id", default="unknown")

# Default agent configuration
DEFAULT_AGENT_NAME = "Aria"

# MCP servers for default agent: web-forager (primary: search + fetch), fetch (backup)
DEFAULT_MCP_SERVERS = ["web-forager", "fetch"]

# System prompts
DEFAULT_SYSTEM_PROMPT = f"""You are {DEFAULT_AGENT_NAME}, a helpful AI assistant on WhatsApp.

## Your Capabilities
- Conversational chat and Q&A
- Web search via DuckDuckGo
- Fetch and read web pages
- **Invoke specialized agents** for specific tasks (use the invoke_agent tool)
- General knowledge and helpful responses

## Your Personality
- Concise and friendly (WhatsApp is mobile-first)
- Occasional emojis are fine 🌟
- Answer directly, don't over-explain
- Use minimal formatting

## Invoking Specialized Agents
You have the `invoke_agent` tool which allows you to directly delegate tasks to specialized agents:

| For this... | Use this agent |
|-------------|----------------|
| Coding, debugging, code review | developer |
| News & current events monitoring | news |
| Learning topics in depth | learning |
| YouTube video operations | youtube |
| GitHub PR reviews | github-pr-reviewer |
| Local LLM (privacy/offline) | ollama |
| Flight searches | kiwi |

**IMPORTANT:** You CAN invoke these agents directly using the
`invoke_agent` tool. Don't just suggest them — actually use the tool
when the user asks for something a specialist can handle.

Example: If user asks "Can you review these PRs?", use `invoke_agent`
with agent_name="github-pr-reviewer" and the prompt containing the PR URLs.

## Important
- You are {DEFAULT_AGENT_NAME} - the user can call you this
- Don't make up capabilities you don't have
- When uncertain, offering to search or fetch is helpful
- PROACTIVELY use invoke_agent when it makes sense — don't make the user
  type slash commands
"""

# Router initialization now accepts a Channel object directly
# The channel can be either Business API or Bridge implementation
# and will provide the appropriate methods (send, listen, shutdown, initialize)


def _make_invoke_agent_tool(router: "WhatsAppRouterAgent") -> Any:
    """Create a tool that allows the default agent to invoke other registered agents.

    Args:
        router: The WhatsAppRouterAgent instance with access to registered agents.

    Returns:
        A tool function that can be called by the LLM to delegate to specialized agents.
    """
    from agntrick.registry import AgentRegistry  # type: ignore[import-untyped]

    async def invoke_agent(agent_name: str, prompt: str) -> str:
        """Invoke a specialized agent to handle a specific task.

        Available agents: github-pr-reviewer, news, ollama, developer, learning, youtube, kiwi, etc.

        Args:
            agent_name: The name of the agent to invoke (e.g., "github-pr-reviewer", "news", "ollama").
            prompt: The prompt/task to send to the agent.

        Returns:
            The agent's response as a string.
        """
        try:
            AgentRegistry.discover_agents()
            available = AgentRegistry.list_agents()

            if agent_name not in available:
                # Try direct import as fallback
                agent_cls = router._try_direct_import(agent_name)
                if agent_cls is None:
                    return f"Error: Agent '{agent_name}' not found. Available agents: {', '.join(available)}"

            # Instantiate agent if not cached
            if agent_name not in router._registered_agents:
                if agent_name in available:
                    agent_cls = AgentRegistry.get(agent_name)
                else:
                    agent_cls = router._try_direct_import(agent_name)

                if agent_cls is None:
                    return f"Error: Could not instantiate agent '{agent_name}'"

                router._registered_agents[agent_name] = agent_cls()

            agent = router._registered_agents[agent_name]

            # Get sender_id from context for conversation memory
            sender_id = _current_sender_id.get()
            logger.info(f"Tool invoking agent '{agent_name}' with prompt: {prompt[:80]} (sender: {sender_id})")

            # Use conversation memory if available and sender_id is known
            if router._conversation_manager and sender_id != "unknown":
                thread_id = router._conversation_manager.get_thread_id(sender_id, agent_name)
                result = await agent.run_with_memory(
                    prompt,
                    thread_id=thread_id,
                    max_tokens=router._max_conversation_tokens,
                    checkpointer=router._conversation_manager.checkpointer,
                )
            else:
                result = await agent.run(prompt)
            return str(result)

        except Exception as exc:
            logger.error(f"Error in invoke_agent tool: {exc}", exc_info=True)
            return f"Error invoking agent '{agent_name}': {exc}"

    # Set tool metadata for the LLM
    invoke_agent.description = (  # type: ignore[attr-defined]
        "Invoke a specialized agent to handle specific tasks. "
        "Use this when the user requests capabilities that are better handled by specialist agents. "
        "Available agents include: github-pr-reviewer (PR reviews), news (current events), "
        "ollama (local LLM), developer (coding), learning (deep learning), youtube (video ops), kiwi (flights)."
    )

    return invoke_agent


def _inject_invoke_agent_tool(agent: Any, router: "WhatsAppRouterAgent") -> None:
    """Inject the invoke_agent tool into a pre-existing agent instance.

    Wraps the agent's local_tools method to include the invoke_agent tool.

    Args:
        agent: The agent instance to modify.
        router: The WhatsAppRouterAgent instance with access to registered agents.
    """
    original_local_tools = agent.local_tools
    invoke_tool = _make_invoke_agent_tool(router)

    def wrapped_local_tools() -> list:  # type: ignore[misc]
        original_tools = original_local_tools() if callable(original_local_tools) else original_local_tools
        if isinstance(original_tools, list):
            return original_tools + [invoke_tool]
        return [invoke_tool]

    agent.local_tools = wrapped_local_tools


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
        max_conversation_tokens: int = 4000,
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
        self._max_conversation_tokens = max_conversation_tokens

        # Message history
        self.message_history: List[Dict[str, Any]] = []
        self.conversations: Dict[str, Dict[str, Any]] = {}

        # Cache for lazily-instantiated registered agents (e.g. /ollama)
        self._registered_agents: Dict[str, Any] = {}

        # Command parser
        self._command_parser = CommandParser()

        # Conversation management (uses same DB as notes/tasks)
        self._conversation_manager: Any = None
        if db is not None:
            from .conversation import ConversationManager

            self._conversation_manager = ConversationManager(db._db_path)

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

            # Set up MCP servers (use override if provided, otherwise use defaults)
            self._mcp_servers = self._mcp_servers_override or DEFAULT_MCP_SERVERS

            # Initialize a generic agent if one was not injected
            if self._agent is None:
                # Import lazily to avoid circular dependencies if agntrick is linked
                from agntrick.agent import AgentBase  # type: ignore[import-untyped]
                from agntrick.mcp.provider import MCPProvider  # type: ignore[import-untyped]

                # Create MCP provider with web-forager (primary) and fetch (backup)
                mcp_provider = MCPProvider(server_names=self._mcp_servers)

                # Capture router for tool access
                router_instance = self

                class DefaultRouterAgent(AgentBase):
                    @property
                    def system_prompt(self) -> str:
                        return DEFAULT_SYSTEM_PROMPT

                    def local_tools(self) -> list:
                        """Return tools that allow invoking other registered agents."""
                        return [
                            _make_invoke_agent_tool(router_instance),
                        ]

                self._agent = DefaultRouterAgent(
                    model_name=self._model_name,
                    temperature=self._temperature,
                    mcp_provider=mcp_provider,
                )
            else:
                # Inject invoke_agent tool into custom-provided agent
                _inject_invoke_agent_tool(self._agent, self)

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

            # Extract sender_id early for conversation threading
            sender_id = self._get_sender_id(incoming)

            # Check for commands using the stored command parser
            command = self._command_parser.parse(message_text)
            logger.info(f"Parsed command: {command}")

            # Handle built-in commands; unrecognised slash-commands fall
            # through to the LLM agent so prefixes like /ollama are
            # forwarded as regular prompts.
            if command.command:
                response = await self._handle_command(command, sender_id)
                if response is not None:
                    await self._send_response(incoming, response)
                    return

            # Set sender_id in context for tools that need conversation access
            _current_sender_id.set(sender_id)

            # Process through the LLM agent with conversation memory
            if self._agent:
                if self._conversation_manager:
                    thread_id = self._conversation_manager.get_thread_id(sender_id, "default")
                    logger.info(f"Running default agent with thread_id: {thread_id}")

                    result = await self._agent.run_with_memory(
                        message_text,
                        thread_id=thread_id,
                        max_tokens=self._max_conversation_tokens,
                        checkpointer=self._conversation_manager.checkpointer,
                    )
                else:
                    logger.info("Running default agent with prompt: %s", message_text[:80])
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

        Built-in commands (note, notes, remind, schedule, help) are handled
        directly.  If the command name matches a registered agent in the
        ``AgentRegistry`` (e.g. ``/ollama``), the prompt is forwarded to
        that agent.  Otherwise ``None`` is returned so the caller can fall
        through to the default LLM agent.

        Args:
            command: ParsedCommand with .command and .args attributes.
            sender_id: The sender's ID for scoping storage operations.

        Returns:
            Response text, or ``None`` if the command is not recognised.
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

        # Check if the command maps to a registered agent (e.g. /ollama)
        result = await self._try_registered_agent(cmd, args, sender_id)
        if result is not None:
            return result

        logger.info("Unrecognised command /%s — forwarding to default LLM agent", cmd)
        return None

    async def _try_registered_agent(self, agent_name: str, args: list[str], sender_id: str) -> str | None:
        """Try to dispatch a command to a registered agent.

        Looks up ``agent_name`` in the ``AgentRegistry``.  If found,
        instantiates (and caches) the agent and runs the prompt.

        Args:
            agent_name: The agent name to look up (e.g. ``"ollama"``).
            args: The remaining arguments to join into a prompt.
            sender_id: The sender's ID for conversation threading.

        Returns:
            The agent's response string, or ``None`` if no matching agent.
        """
        try:
            from agntrick.registry import AgentRegistry  # type: ignore[import-untyped]

            AgentRegistry.discover_agents()
            available = AgentRegistry.list_agents()
            logger.info("Registry contains agents: %s", available)

            agent_cls = AgentRegistry.get(agent_name)

            if agent_cls is None:
                agent_cls = self._try_direct_import(agent_name)

            if agent_cls is None:
                logger.info("Agent '%s' not found in registry or by direct import", agent_name)
                return None

            logger.info("Routing to registered agent: %s (%s)", agent_name, agent_cls.__name__)

            if agent_name not in self._registered_agents:
                logger.info("Instantiating agent '%s' …", agent_name)
                self._registered_agents[agent_name] = agent_cls()
                logger.info("Agent '%s' instantiated OK", agent_name)

            agent = self._registered_agents[agent_name]
            prompt = " ".join(args)
            if not prompt:
                return f"Usage: /{agent_name} <your prompt>"

            # Use conversation memory if available
            if self._conversation_manager:
                thread_id = self._conversation_manager.get_thread_id(sender_id, agent_name)
                logger.info(f"Running agent '{agent_name}' with thread_id: {thread_id}")

                result = await agent.run_with_memory(
                    prompt,
                    thread_id=thread_id,
                    max_tokens=self._max_conversation_tokens,
                    checkpointer=self._conversation_manager.checkpointer,
                )
            else:
                # Fallback for no conversation manager
                logger.info("Running agent '%s' with prompt: %s", agent_name, prompt[:80])
                result = await agent.run(prompt)

            return str(result)
        except Exception as exc:
            logger.error("Error running registered agent '%s': %s", agent_name, exc, exc_info=True)
            return f"Error from /{agent_name}: {exc}"

    @staticmethod
    def _try_direct_import(agent_name: str) -> type | None:
        """Attempt to import an agent class directly by module name.

        Fallback when ``AgentRegistry.discover_agents()`` silently fails
        to import a module (its internal ``try/except`` swallows errors).

        Args:
            agent_name: The agent name, e.g. ``"ollama"``.

        Returns:
            The agent class, or ``None`` if import fails.
        """
        import importlib

        module_path = f"agntrick.agents.{agent_name}"
        try:
            mod = importlib.import_module(module_path)
            logger.info("Direct import of %s succeeded", module_path)
        except Exception as exc:
            logger.error("Direct import of %s FAILED: %s", module_path, exc, exc_info=True)
            return None

        class_map = {
            name: obj
            for name, obj in vars(mod).items()
            if isinstance(obj, type) and name.lower().startswith(agent_name)
        }
        if class_map:
            cls = next(iter(class_map.values()))
            logger.info("Found agent class via direct import: %s", cls.__name__)
            return cls  # type: ignore[return-value]

        logger.warning("Module %s imported but no agent class found", module_path)
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
        lines = [
            "Available commands:",
            "/note <content> - Save a note",
            "/notes - List your notes",
            "/remind <time> <message> - Set a reminder (e.g., /remind 'in 30 minutes' call doctor)",
            "/schedule <cron> <message> - Schedule recurring message (e.g., /schedule '0 9 * * *' Good morning)",
            "/help - Show this help",
        ]

        try:
            from agntrick.registry import AgentRegistry  # type: ignore[import-untyped]

            AgentRegistry.discover_agents()
            agents = AgentRegistry.list_agents()
            if agents:
                lines.append("\nAgent commands:")
                for name in sorted(agents):
                    lines.append(f"/{name} <prompt> - Route to {name} agent")
        except Exception:
            pass

        return "\n".join(lines)
