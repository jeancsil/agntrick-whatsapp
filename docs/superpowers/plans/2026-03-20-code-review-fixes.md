# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 code review issues: missing checkpointer parameter, inconsistent conversation memory in invoke_agent tool, and race condition in shutdown.

**Architecture:** Add `contextvars` for passing sender_id through async boundaries, add checkpointer parameter to `run_with_memory()` calls, and add shutdown guard before scheduling coroutines.

**Tech Stack:** Python contextvars, asyncio, LangGraph checkpointer

---

## Files to Modify

| File | Purpose |
|------|---------|
| `src/agntrick_whatsapp/router.py` | Add ContextVar for sender_id, pass checkpointer to run_with_memory(), update invoke_agent tool |
| `src/agntrick_whatsapp/channel_bridge.py` | Add shutdown guard before run_coroutine_threadsafe() |
| `tests/test_router.py` | Add tests for context variable flow and conversation persistence |

---

## Task 1: Add checkpointer parameter to run_with_memory() calls (Issue 1)

**Files:**
- Modify: `src/agntrick_whatsapp/router.py:367-371`
- Modify: `src/agntrick_whatsapp/router.py:541-545`

- [ ] **Step 1: Add checkpointer to _handle_message run_with_memory call**

Edit `src/agntrick_whatsapp/router.py` lines 367-371:

```python
# Before:
result = await self._agent.run_with_memory(
    message_text,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
)

# After:
result = await self._agent.run_with_memory(
    message_text,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
    checkpointer=self._conversation_manager.checkpointer,
)
```

- [ ] **Step 2: Add checkpointer to _try_registered_agent run_with_memory call**

Edit `src/agntrick_whatsapp/router.py` lines 541-545:

```python
# Before:
result = await agent.run_with_memory(
    prompt,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
)

# After:
result = await agent.run_with_memory(
    prompt,
    thread_id=thread_id,
    max_tokens=self._max_conversation_tokens,
    checkpointer=self._conversation_manager.checkpointer,
)
```

- [ ] **Step 3: Run mypy to verify type safety**

Run: `uv run mypy src/agntrick_whatsapp/router.py`
Expected: No errors (or only existing errors, no new ones)

- [ ] **Step 4: Commit**

```bash
git add src/agntrick_whatsapp/router.py
git commit -m "$(cat <<'EOF'
fix(router): pass checkpointer to run_with_memory() for conversation persistence

The checkpointer was being created but never passed to LangGraph's
run_with_memory() method, causing conversation history to not be
persisted across messages.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add contextvars for sender_id in invoke_agent tool (Issue 2)

**Files:**
- Modify: `src/agntrick_whatsapp/router.py` (imports, module-level ContextVar, tool implementation)

- [ ] **Step 1: Add contextvars import**

Edit `src/agntrick_whatsapp/router.py` line 8 (after `import asyncio`):

```python
# Before:
import asyncio
import logging

# After:
import asyncio
import contextvars
import logging
```

- [ ] **Step 2: Add module-level ContextVar for sender_id**

Add after line 22 (after `SCHEDULER_INTERVAL_SECONDS = 10`):

```python
# Context variable for passing sender_id through async boundaries
# Used by invoke_agent tool to access conversation memory
_current_sender_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sender_id", default="unknown"
)
```

- [ ] **Step 3: Set context variable in _handle_message before agent call**

Insert new code after line 346 (after `sender_id = self._get_sender_id(incoming)`), before line 362 (`if self._agent:`). Note: Lines 347-361 contain command handling code.

```python
# Insert these two lines after line 359 (after command handling, before the agent check):
# Set sender_id in context for tools that need conversation access
_current_sender_id.set(sender_id)

# The existing code around this location:
# (line 346) sender_id = self._get_sender_id(incoming)
# (lines 347-359) command handling code
# (line 360)
# (line 361) # Process through the LLM agent with conversation memory
# (line 362) if self._agent:
```

- [ ] **Step 4: Update invoke_agent tool to use context variable**

Edit `src/agntrick_whatsapp/router.py` lines 127-131:

```python
# Before:
# For async tool invocation, we don't have sender_id context
# Run without conversation memory
logger.info(f"Tool invoking agent '{agent_name}' with prompt: {prompt[:80]}")
result = await agent.run(prompt)
return str(result)

# After:
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
```

- [ ] **Step 5: Run mypy to verify type safety**

Run: `uv run mypy src/agntrick_whatsapp/router.py`
Expected: No errors (or only existing errors, no new ones)

- [ ] **Step 6: Run ruff to check formatting**

Run: `uv run ruff check src/agntrick_whatsapp/router.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/agntrick_whatsapp/router.py
git commit -m "$(cat <<'EOF'
fix(router): use contextvars for sender_id in invoke_agent tool

The invoke_agent tool was calling agent.run() without conversation
memory because it didn't have access to sender_id context. Now uses
Python's contextvars module to pass sender_id through async boundaries,
enabling consistent conversation history across agent invocations.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add shutdown guard in channel_bridge.py (Issue 3)

**Files:**
- Modify: `src/agntrick_whatsapp/channel_bridge.py` (insert before line 504)

**Note:** The design spec mentions "Add done callback for debugging" but this is optional and not included in this implementation to keep changes minimal.

- [ ] **Step 1: Add shutdown guard before run_coroutine_threadsafe**

Insert the shutdown guard immediately before line 504 (`asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)`):

```python
# Before (lines 495-504):
async def _dispatch() -> None:
    try:
        assert self._message_callback is not None
        await self._message_callback(normalized)
    except Exception as exc:
        logger.error("Error in message callback: %s", exc, exc_info=True)
    finally:
        await self._stop_typing(sender_jid)

asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)

# After:
async def _dispatch() -> None:
    try:
        assert self._message_callback is not None
        await self._message_callback(normalized)
    except Exception as exc:
        logger.error("Error in message callback: %s", exc, exc_info=True)
    finally:
        await self._stop_typing(sender_jid)

# Guard against race condition during shutdown
if self._stop_event.is_set():
    logger.debug("Skipping dispatch - shutdown in progress")
    return

asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)
```

- [ ] **Step 2: Run mypy to verify type safety**

Run: `uv run mypy src/agntrick_whatsapp/channel_bridge.py`
Expected: No errors (or only existing errors, no new ones)

- [ ] **Step 3: Run ruff to check formatting**

Run: `uv run ruff check src/agntrick_whatsapp/channel_bridge.py`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/agntrick_whatsapp/channel_bridge.py
git commit -m "$(cat <<'EOF'
fix(channel_bridge): add shutdown guard before scheduling coroutine

Prevents race condition where messages arriving during shutdown could
cause asyncio.run_coroutine_threadsafe() to reference a closed/destroyed
event loop. Now checks _stop_event before scheduling new dispatches.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add unit tests for context variable flow

**Files:**
- Modify: `tests/test_router.py` (add at end of `TestRouterLifecycle` class, after line 619)

**Prerequisite:** Task 2 must be completed first (the `_current_sender_id` ContextVar must exist in router.py).

- [ ] **Step 1: Write test for context variable propagation**

Add to `tests/test_router.py` at the end of the `TestRouterLifecycle` class (after the `test_stop_handles_shutdown_error` method, around line 619):

```python
async def test_context_var_sender_id_propagates(self) -> None:
    """Test that sender_id is set in context variable during message handling."""
    from unittest.mock import AsyncMock, MagicMock, patch
    import contextvars

    channel = MockWhatsAppChannel()
    mock_agent = MagicMock()

    # Capture the context variable value when agent is called
    captured_sender_id: list[str] = []

    async def capture_run(prompt: str) -> str:
        # Import the context variable from router module
        from agntrick_whatsapp.router import _current_sender_id
        captured_sender_id.append(_current_sender_id.get())
        return "Response"

    mock_agent.run = capture_run
    router = WhatsAppRouterAgent(channel, agent=mock_agent)

    await router._handle_message({"sender_id": "test_sender_123", "text": "hello"})

    assert captured_sender_id == ["test_sender_123"]
```

- [ ] **Step 2: Run the new test to verify it passes**

Run: `uv run pytest tests/test_router.py::TestRouterLifecycle::test_context_var_sender_id_propagates -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_router.py
git commit -m "$(cat <<'EOF'
test(router): add test for sender_id context variable propagation

Verifies that the _current_sender_id ContextVar is correctly set
during message handling so that tools can access conversation memory.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Run full test suite and verify all fixes

**Files:**
- None (verification only)

- [ ] **Step 1: Run make check**

Run: `make check`
Expected: All linting passes (mypy + ruff)

- [ ] **Step 2: Run make test**

Run: `make test`
Expected: All tests pass

- [ ] **Step 3: Review git log to verify commits**

Run: `git log --oneline -5`
Expected: See 4 new commits for the fixes

---

## Summary

| Issue | Fix | Files Modified |
|-------|-----|----------------|
| Missing checkpointer | Pass checkpointer to run_with_memory() | router.py (2 locations) |
| Inconsistent invoke_agent memory | Use ContextVar for sender_id | router.py (imports, module, tool) |
| Shutdown race condition | Add _stop_event guard | channel_bridge.py |

**Out of Scope:** Token truncation (max_conversation_tokens) - belongs in agntrick core package.
