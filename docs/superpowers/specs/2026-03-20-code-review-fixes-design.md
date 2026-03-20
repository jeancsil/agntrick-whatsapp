# Code Review Fixes Design

**Date:** 2026-03-20
**Status:** Approved
**Author:** Claude + User
**Related PR:** #2

---

## Problem Statement

Code review of PR #2 identified 4 issues that need to be fixed:

1. **Missing `checkpointer` parameter** - Conversation history not persisted
2. **Inconsistent conversation memory** - `invoke_agent` tool bypasses memory
3. **Race condition in shutdown** - Messages during shutdown could crash
4. **Unused `max_conversation_tokens`** - Parameter passed but not implemented

---

## Design Decisions

### Issue 1: Missing `checkpointer` parameter

**Location:** `src/agntrick_whatsapp/router.py` lines 367-371 and 541-545

**Fix:** Add `checkpointer=self._conversation_manager.checkpointer` to both `run_with_memory()` calls.

**Rationale:** The `ConversationManager` already provides a `checkpointer` property (see `conversation.py` line 66). Without passing it, LangGraph cannot persist conversation history - the entire feature is broken.

**Code change:**
```python
# Before (line 367-371)
result = await self._agent.run_with_memory(
    message_text,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
)

# After
result = await self._agent.run_with_memory(
    message_text,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
    checkpointer=self._conversation_manager.checkpointer,
)
```

Same change for line 541-545 in `_try_registered_agent()`.

---

### Issue 2: Inconsistent conversation memory (invoke_agent tool)

**Location:** `src/agntrick_whatsapp/router.py` lines 127-131

**Problem:** The `invoke_agent` tool calls `agent.run(prompt)` without conversation memory because it doesn't have access to `sender_id` context.

**Fix:** Use `contextvars.ContextVar` to pass `sender_id` through async boundaries.

**Rationale:** Python's `contextvars` module is designed for passing request-scoped data through async code without explicit parameters. It's used by asyncio, aiohttp, and other async frameworks.

**Code changes:**

```python
# At module level (after imports)
import contextvars
_current_sender_id: contextvars.ContextVar[str] = contextvars.ContextVar('sender_id', default='unknown')

# In _handle_message(), before calling agent (line ~362)
_current_sender_id.set(sender_id)

# In invoke_agent tool (line ~130)
sender_id = _current_sender_id.get()
if self._conversation_manager and sender_id != 'unknown':
    thread_id = self._conversation_manager.get_thread_id(sender_id, agent_name)
    result = await agent.run_with_memory(
        prompt,
        thread_id=thread_id,
        max_tokens=self._max_conversation_tokens,
        checkpointer=self._conversation_manager.checkpointer,
    )
else:
    result = await agent.run(prompt)
```

---

### Issue 3: Race condition in message processing during shutdown

**Location:** `src/agntrick_whatsapp/channel_bridge.py` line 504

**Problem:** `asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)` could reference a closed/destroyed loop if `shutdown()` completes before the callback fires.

**Fix:** Add shutdown guard before scheduling coroutine.

**Rationale:** Check `_stop_event` before scheduling to prevent new dispatches during shutdown. This is the simplest and most robust solution without complex tracking.

**Code changes:**

```python
# Before line 504
if self._stop_event.is_set():
    logger.debug("Skipping dispatch - shutdown in progress")
    return

# After line 504, add callback for debugging
future = asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)
future.add_done_callback(
    lambda f: logger.debug("Dispatch completed") if not f.exception() else None
)
```

---

### Issue 4: Unused `max_conversation_tokens` parameter

**Location:** `src/agntrick_whatsapp/router.py` lines 98-99, 370-371, 544-545

**Problem:** Parameter is passed to `run_with_memory()` but the underlying implementation ignores it.

**Decision:** **Keep as-is.**

**Rationale:** The design spec (`2026-03-19-conversation-history-design.md`) explicitly marks token truncation as "Future Consideration". The parameter is correctly passed - implementation needs to happen in the agntrick core package's `run_with_memory()` method, which is out of scope for this repo.

---

## Files to Modify

1. **`src/agntrick_whatsapp/router.py`** - Issues 1 & 2
   - Add `contextvars` import
   - Add `_current_sender_id` ContextVar
   - Set context before agent calls
   - Add `checkpointer` parameter to both `run_with_memory()` calls
   - Update `invoke_agent` tool to use context

2. **`src/agntrick_whatsapp/channel_bridge.py`** - Issue 3
   - Add shutdown guard before `run_coroutine_threadsafe()`
   - Add done callback for debugging

---

## Testing Strategy

1. **Unit tests** for context variable flow
2. **Integration tests** for conversation persistence
3. **Manual testing** for shutdown race condition (hard to unit test)

---

## Out of Scope

- Token truncation implementation (belongs in agntrick core package)
- New features beyond fixing the identified bugs
