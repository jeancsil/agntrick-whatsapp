# agntrick-toolbox Design

**Date:** 2026-03-21
**Status:** Draft
**Author:** jeancsil

## Overview

A Docker-based MCP server providing a curated CLI tool collection for LLM agents. Single container image with 50-80 curated tools exposed via MCP protocol, with shell fallback for additional commands.

## Goals

- Provide a "kitchen sink" toolbox similar to OpenClaw for agntrick agents
- Zero-friction setup: `docker-compose up -d` and it's ready
- High reliability through curated tool schemas (90% of use cases)
- Escape hatch via shell fallback for edge cases

## Non-Goals

- Sandboxed execution (future enhancement)
- Multi-tenant isolation
- GUI/web interface

## Architecture

```
┌─────────────────────┐
│   agntrick agent    │
│   (agntrick/         │
│   agntrick-whatsapp) │
└─────────┬───────────┘
          │ MCP (SSE/stdio)
          ▼
┌─────────────────────┐         ┌──────────────────┐
│  agntrick-toolbox   │  exec   │   CLI tools      │
│  (Docker container) │────────►│                  │
│                     │         │  Document:       │
│  - FastMCP server   │         │  - pdf2text      │
│  - Python 3.12      │         │  - pandoc        │
│  - Tool schemas     │         │  - textract      │
└─────────────────────┘         │                  │
                                │  Media:          │
                                │  - ffmpeg        │
                                │  - imagemagick   │
                                │  - exiftool      │
                                │                  │
                                │  Data:           │
                                │  - jq            │
                                │  - yq            │
                                │  - csvkit        │
                                │  - sqlite3       │
                                │                  │
                                │  Dev/Utils:      │
                                │  - curl          │
                                │  - wget          │
                                │  - git           │
                                │  - zip/unzip     │
                                │  - rsync         │
                                │                  │
                                │  (~50-80 tools)  │
                                └──────────────────┘
```

## Components

### 1. Container Image

**Base:** `python:3.12-slim-bookworm`

**Pre-installed tool categories:**

| Category | Tools |
|----------|-------|
| Document | pandoc, poppler-utils (pdf2text), textract, calibre (ebook-convert), ocrmypdf |
| Media | ffmpeg, imagemagick, exiftool, sox, mediainfo |
| Data | jq, yq, csvkit, sqlite3, parquet-tools, dasel |
| Dev/Utils | curl, wget, git, zip, unzip, gzip, zstd, rsync, fdupes |
| Compression | zstd, lz4, xz, bzip2 |

**Estimated size:** ~1.5-2GB compressed

### 2. MCP Server

**Framework:** FastMCP (Python)

**Features:**
- Async tool execution
- SSE and stdio transports
- Structured error responses
- Request validation

**Exposed tools:**
- 50-80 curated tools with full JSON schemas
- 1 generic `run_shell` fallback tool

### 3. Tool Definition Format

Each curated tool includes:

```python
{
    "name": "pdf_extract_text",
    "description": "Extract text from a PDF file. Supports page ranges.",
    "input_schema": {
        "type": "object",
        "properties": {
            "input_path": {"type": "string", "description": "Path to PDF file"},
            "pages": {"type": "string", "default": "all", "description": "Page range (e.g., '1-5', 'all')"},
            "output_format": {"type": "string", "enum": ["text", "markdown"], "default": "text"}
        },
        "required": ["input_path"]
    }
}
```

### 4. Shell Fallback

```python
{
    "name": "run_shell",
    "description": "Execute a shell command for tools not in curated set. Use sparingly.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "default": 30, "description": "Timeout in seconds"}
        },
        "required": ["command"]
    }
}
```

## Data Flow

```
1. Agent sends MCP tool request
   └──► toolbox-server receives request

2. Server validates input against tool schema
   └──► Invalid? Return validation error

3. Server executes underlying CLI tool
   └──► Captures stdout, stderr, exit code

4. Server returns structured result
   └──► {success: bool, output: str, error: str|null}
```

## Error Handling

| Error Type | Response |
|------------|----------|
| Tool not found | Error message with similar tool suggestions |
| Invalid input | Schema validation errors with field details |
| Execution timeout | Timeout error with partial output |
| Command failure | Exit code + stderr content |
| Output too large | Truncated output with size warning |

## Security Considerations

### Path Confinement
- All file operations are confined to `/workspace` directory
- Paths outside `/workspace` are rejected with clear error message
- Symlinks are resolved and checked against `/workspace` boundary
- Absolute and relative path traversal (`../`) attempts are blocked

### Shell Fallback Risks
- `run_shell` is enabled by default but can be disabled via `TOOLBOX_SHELL_ENABLED=false`
- Shell commands inherit the same `/workspace` confinement
- No access to host filesystem or Docker socket
- Future: Add command allowlist/blocklist for additional control

### Container Isolation
- Runs as non-root user inside container
- No privileged mode required
- Read-only root filesystem with tmpfs for /tmp
- Network access limited to MCP server port

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TOOLBOX_TIMEOUT_DEFAULT` | `30` | Default execution timeout (seconds) |
| `TOOLBOX_SHELL_ENABLED` | `true` | Enable shell fallback tool |
| `TOOLBOX_LOG_LEVEL` | `INFO` | Logging verbosity |
| `TOOLBOX_MAX_OUTPUT_SIZE` | `1048576` | Max output bytes (1MB) |
| `TOOLBOX_PORT` | `8080` | HTTP server port |

## File Structure

```
agntrick-toolbox/
├── Dockerfile
├── docker-compose.yaml
├── pyproject.toml
├── README.md
├── src/
│   └── agntrick_toolbox/
│       ├── __init__.py
│       ├── server.py          # FastMCP server entry point
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── document.py    # PDF, pandoc, etc.
│       │   ├── media.py       # ffmpeg, imagemagick
│       │   ├── data.py        # jq, csvkit, sqlite
│       │   ├── utils.py       # curl, wget, compression
│       │   └── shell.py       # run_shell fallback
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── definitions.py # Tool schema registry
│       └── config.py          # Settings and env vars
└── tests/
    ├── __init__.py
    ├── test_server.py
    ├── test_tools/
    │   ├── test_document.py
    │   ├── test_media.py
    │   └── test_data.py
    └── conftest.py
```

## Usage

### Running the toolbox

```bash
# Clone and start
git clone https://github.com/jeancsil/agntrick-toolbox.git
cd agntrick-toolbox
docker-compose up -d

# Or with custom config
TOOLBOX_TIMEOUT_DEFAULT=60 docker-compose up -d
```

### docker-compose.yaml

```yaml
version: "3.8"

services:
  toolbox:
    build: .
    image: ghcr.io/jeancsil/agntrick-toolbox:latest
    ports:
      - "${TOOLBOX_PORT:-8080}:8080"
    environment:
      - TOOLBOX_TIMEOUT_DEFAULT=${TOOLBOX_TIMEOUT_DEFAULT:-30}
      - TOOLBOX_SHELL_ENABLED=${TOOLBOX_SHELL_ENABLED:-true}
      - TOOLBOX_LOG_LEVEL=${TOOLBOX_LOG_LEVEL:-INFO}
      - TOOLBOX_MAX_OUTPUT_SIZE=${TOOLBOX_MAX_OUTPUT_SIZE:-1048576}
    volumes:
      # Mount workspace for file operations
      - ${TOOLBOX_WORKSPACE:-./workspace}:/workspace:rw
    restart: unless-stopped
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    # Security: run as non-root
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=100M,mode=1777
```

### Configuring agntrick

```yaml
# .agntrick.yaml
mcp_servers:
  - name: toolbox
    transport: sse
    url: http://localhost:8080/sse
```

### Example tool calls

```python
# Extract text from PDF
await mcp.call_tool("pdf_extract_text", {
    "input_path": "/workspace/document.pdf",
    "pages": "1-5"
})

# Convert markdown to HTML
await mcp.call_tool("pandoc_convert", {
    "input_path": "/workspace/readme.md",
    "from_format": "markdown",
    "to_format": "html"
})

# Run shell command (fallback)
await mcp.call_tool("run_shell", {
    "command": "ls -la /workspace",
    "timeout": 10
})
```

## Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit tests | Each tool schema and execution |
| Integration tests | MCP protocol compliance |
| E2E tests | Full agent → toolbox flow |
| Performance | Benchmark common operations |

## Future Enhancements

- [ ] Sandboxed execution (Firejail/bubblewrap)
- [ ] Tool usage analytics
- [ ] Dynamic tool discovery
- [ ] Multi-language support for error messages
- [ ] Web UI for monitoring

## Success Criteria

- [ ] Single `docker-compose up -d` starts working toolbox
- [ ] All 50-80 curated tools have valid schemas
- [ ] agntrick agent can discover and use tools via MCP
- [ ] Shell fallback works for non-curated commands
- [ ] Error messages are helpful and actionable
