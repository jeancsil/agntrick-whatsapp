# Conversation History for Agntrick WhatsApp

**Date:** 2026-03-19
**Status:** Design
**Author:** Claude + User

---

## Problem Statement

WhatsApp messages are processed independently with no conversation history. When a user asks "can you remember our last conversation?", the agent has no memory of previous interactions.

**Root Cause:** Agents are called with `agent.run(prompt)` using:
- Fixed `thread_id="1"` (no per-user isolation)
- `InMemorySaver()` checkpointer (ephemeral, lost on restart)
- No persistent checkpointer configured

---

## Requirements

1. **Persistent Storage:** History saved to DB forever
2. **Thread-scoped:** Conversations grouped by `(sender_id, agent_name)` pair
3. **Token-aware:** Limit context to ~4000 tokens (configurable)
4. **Backwards Compatible:** Existing code continues to work
5. **Cross-platform:** Benefits all agntrick integrations (WhatsApp, Discord, etc.)
6. **Single Database:** Use `whatsapp.db` for all user data (notes, tasks, conversations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     agntrick-whatsapp                           │
├─────────────────────────────────────────────────────────────────┤
│  WhatsAppRouterAgent                                            │
│  ├── _handle_message()                                          │
│  │   ├── Parse command                                          │
│  │   ├── Generate thread_id = f"{sender_id}:{agent_name}"      │
│  │   ├── Get checkpointer from DB                              │
│  │   └── Call agent.run(prompt, config={thread_id, checkpointer})│
│  └── _send_response()                                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        agntrick                                  │
├─────────────────────────────────────────────────────────────────┤
│  AgentBase                                                       │
│  ├── __init__(checkpointer=SqliteSaver, thread_id="default")    │
│  ├── run(input_data, config={thread_id, checkpointer})          │
│  └── LangGraph stores history via checkpointer                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   whatsapp.db (SQLite)                          │
├─────────────────────────────────────────────────────────────────┤
│  Existing tables:                                               │
│  ├── notes (user notes via /note, /notes)                       │
│  └── scheduled_tasks (reminders via /remind, /schedule)         │
│                                                                 │
│  LangGraph adds:                                                │
│  ├── checkpoints (conversation history per thread)              │
│  └── blobs (message data)                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: agntrick Core Changes

**File:** `src/agntrick/agent.py`

#### Change 1.1: Add `run_with_memory()` method (new, backwards-compatible)

```python
async def run_with_memory(
    self,
    input_data: Union[str, List[BaseMessage]],
    *,
    thread_id: str | None = None,
    checkpointer: Any | None = None,
    max_tokens: int | None = None,
) -> Union[str, BaseMessage]:
    """Run agent with conversation memory support.

    This is a convenience method that runs the agent with explicit
    thread ID and checkpointer for persistent conversation history.

    Args:
        input_data: The input for the agent.
        thread_id: Optional thread ID override for conversation scoping.
        checkpointer: Optional checkpointer for persistent history.
        max_tokens: Optional max tokens for context window (truncates if exceeded).

    Returns:
        The agent's response.
    """
    config = self._default_config()

    if thread_id is not None:
        config["configurable"]["thread_id"] = thread_id

    merged_config = {**config}
    if checkpointer is not None:
        merged_config["configurable"]["checkpointer"] = checkpointer

    # TODO: Implement token truncation if max_tokens is provided
    # This would require fetching checkpoint history and trimming

    return await self.run(input_data, config=merged_config)
```

**Rationale:** New method named `run_with_memory()` for clarity. Doesn't break existing `run()`. Callers can optionally pass thread_id, checkpointer, and max_tokens.

#### Change 1.2: Default to persistent checkpointer (via factory pattern)

Add a new classmethod to create agents with DB-backed checkpointers:

```python
@classmethod
def with_persistent_memory(
    cls,
    db_path: str | Path,
    **kwargs: Any,
) -> "AgentBase":
    """Create an agent with persistent SQLite-backed memory.

    Args:
        db_path: Path to SQLite database for checkpoint storage.
        **kwargs: Additional arguments passed to __init__.

    Returns:
        An agent instance with SqliteSaver checkpointer.
    """
    from agntrick.storage.database import Database

    db = Database(db_path)
    kwargs["checkpointer"] = db.get_checkpointer(is_async=True)
    return cls(**kwargs)
```

**Rationale:** Factory method creates agents with persistent memory. Existing `__init__` behavior unchanged.

---

### Phase 2: agntrick-whatsapp Router Changes

**File:** `src/agntrick_whatsapp/router.py`

#### Change 2.1: Add ConversationManager service

New file: `src/agntrick_whatsapp/conversation.py`

```python
"""Conversation history management for WhatsApp integration."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation threading and history for WhatsApp.

    Provides thread ID generation and checkpointer access for
    persistent conversation history across agents.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the conversation manager.

        Args:
            db_path: Path to the SQLite database for storage.
        """
        from agntrick.storage.database import Database

        self._db = Database(db_path)
        self._async_checkpointer = self._db.get_checkpointer(is_async=True)

    def get_thread_id(self, sender_id: str, agent_name: str) -> str:
        """Generate a thread ID for a sender-agent pair.

        Thread IDs are scoped to both the user (sender_id) and the
        agent they're talking to, ensuring /news conversations are
        separate from /ollama conversations.

        Args:
            sender_id: The WhatsApp sender ID (e.g., "12345@s.whatsapp.net").
            agent_name: The agent name (e.g., "news", "ollama", or "default").

        Returns:
            A thread ID string in format "sender_id:agent_name".
        """
        return f"{sender_id}:{agent_name}"

    @property
    def checkpointer(self) -> Any:
        """Get the async checkpointer for LangGraph.

        Returns:
            A LangGraph AsyncSqliteSaver instance.
        """
        return self._async_checkpointer
```

#### Change 2.2: Wire ConversationManager into router

In `WhatsAppRouterAgent.__init__`:

```python
def __init__(
    self,
    channel: WhatsAppChannel,
    model_name: str | None = None,
    temperature: float = 0.7,
    mcp_servers_override: list[str] | None = None,
    audio_transcriber_config: Any = None,
    agent: Any = None,
    db: Any = None,
    max_conversation_tokens: int = 4000,  # NEW: Configurable token limit
) -> None:
    # ... existing code ...

    self._db = db
    self._note_repo: Any = None
    self._task_repo: Any = None
    self._max_conversation_tokens = max_conversation_tokens  # NEW

    # NEW: Conversation management (uses same DB as notes/tasks)
    if db is not None:
        from agntrick_whatsapp.conversation import ConversationManager

        self._conversation_manager = ConversationManager(db._db_path)
    else:
        self._conversation_manager = None
```

#### Change 2.3: Use thread_id and checkpointer in agent calls

In `_try_registered_agent()`:

```python
async def _try_registered_agent(self, agent_name: str, args: list[str]) -> str | None:
    # ... existing code ...

    agent = self._registered_agents[agent_name]
    prompt = " ".join(args)
    if not prompt:
        return f"Usage: /{agent_name} <your prompt>"

    # NEW: Get thread_id and run with memory
    if self._conversation_manager:
        thread_id = self._conversation_manager.get_thread_id(sender_id, agent_name)
        logger.info(f"Running agent '{agent_name}' with thread_id: {thread_id}")

        result = await agent.run_with_memory(
            prompt,
            thread_id=thread_id,
            checkpointer=self._conversation_manager.checkpointer,
            max_tokens=self._max_conversation_tokens,
        )
    else:
        # Fallback for no conversation manager
        logger.info("Running agent '%s' with prompt: %s", agent_name, prompt[:80])
        result = await agent.run(prompt)

    return str(result)
```

Similar changes for the default agent path in `_handle_message()`.

---

### Phase 3: Configuration

Add conversation config to `WhatsAppRouterConfig`:

```python
class WhatsAppRouterConfig(BaseModel):
    # ... existing fields ...

    # NEW: Conversation settings
    conversation_enabled: bool = Field(default=True, description="Enable conversation history")
    max_conversation_tokens: int = Field(default=4000, description="Max tokens in conversation context")
```

**Note:** Conversation history uses the same `whatsapp.db` as notes/tasks. LangGraph will create `checks` and `blobs` tables automatically.

---

## Data Flow Example

### Before (Current State)

```
User: /news latest news
Router: agent.run("latest news") → [no history] → "Here's the news..."

User: /news remember our last conversation?
Router: agent.run("remember our last conversation?") → [no history] → "I don't recall..."
```

### After (With This Design)

```
User: /news latest news
Router:
  1. Parse: agent_name="news", sender_id="123@lid"
  2. thread_id = "123@lid:news"
  3. agent.run_with_memory("latest news", thread_id="123@lid:news", checkpointer=SqliteSaver)
  4. LangGraph stores exchange in whatsapp.db

User: /news remember our last conversation?
Router:
  1. Parse: agent_name="news", sender_id="123@lid"
  2. thread_id = "123@lid:news" (same as before!)
  3. agent.run_with_memory("remember...", thread_id="123@lid:news", checkpointer=SqliteSaver)
  4. LangGraph loads previous exchange from whatsapp.db
  5. Agent responds: "Yes, you asked about the latest news earlier..."
```

---

## Benefits

1. **Minimal Changes:** Leverages existing LangGraph infrastructure
2. **Backwards Compatible:** Existing code continues to work
3. **Cross-Platform:** All agntrick integrations benefit
4. **Scalable:** SQLite checkpoints, can upgrade to Postgres later
5. **Isolated:** Each user-agent pair gets separate thread
6. **Persistent:** Survives restarts

---

## Testing Strategy

### Unit Tests

- `test_thread_id_generation()` - Verify unique thread IDs per sender-agent pair
- `test_conversation_manager_init()` - Verify checkpointer creation
- `test_agent_run_with_memory()` - Verify thread_id and checkpointer passed correctly
- `test_max_tokens_config()` - Verify token limit is configurable

### Integration Tests

- `test_conversation_persistence_across_restarts()` - Restart router, verify history retained
- `test_agent_isolation()` - Verify /news and /ollama have separate conversations
- `test_user_isolation()` - Verify user A doesn't see user B's conversations

---

## Migration Path

### Step 1: Deploy agntrick changes
- Add `run_with_memory()` and `with_persistent_memory()`
- Release as agntrick v0.5.0

### Step 2: Update agntrick-whatsapp
- Add ConversationManager
- Wire into router with `max_conversation_tokens` config
- Release as agntrick-whatsapp v0.4.0

### Step 3: Verify
- Test with existing agents (/news, /ollama, etc.)
- Verify persistence across restarts
- Confirm whatsapp.db has checks and blobs tables

---

## Decisions Made

1. **Token Limit:** 4000 tokens (configurable via `max_conversation_tokens`)
2. **Cleanup:** Keep history forever (no TTL or /clear for now)
3. **Database:** Use `whatsapp.db` (same file as notes/tasks)
4. **Method Name:** `run_with_memory()` for clarity

## Future Considerations

1. **Token Truncation:** Implement actual token counting and truncation in `run_with_memory()`
2. **Cleanup:** Add `/clear` command or TTL-based cleanup if DB grows too large
3. **Monitoring:** Add metrics for conversation size and DB growth

---

## References

- LangGraph Checkpointers: https://langchain-ai.github.io/langgraph/concepts/persistence/
- SqliteSaver: https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.sqlite.SqliteSaver
