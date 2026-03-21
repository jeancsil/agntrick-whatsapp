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

**Pre-installed tool categories (60 curated tools):**

### Document Processing (12 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| pandoc | `pandoc` | Universal document converter (markdown, HTML, PDF, DOCX, etc.) |
| poppler-utils | `poppler-utils` | PDF text extraction (`pdftotext`, `pdfinfo`, `pdfimages`) |
| ghostscript | `ghostscript` | PDF manipulation, merging, compression |
| calibre | `calibre` | E-book conversion (`ebook-convert`) |
| tesseract-ocr | `tesseract-ocr` | OCR for images and scanned PDFs |
| ocrmypdf | `ocrmypdf` | Add OCR layer to PDFs |
| marker | Python pip | Fast PDF to markdown with layout preservation |
| ripgrep | `ripgrep` | Fast text search in documents |
| fzf | `fzf` | Fuzzy finder for interactive selection |
| bat | `bat` | Cat with syntax highlighting |
| pup | `pup` | HTML parsing and extraction |
| glow | `glow` | Markdown renderer for terminal |

### Media Processing (8 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| ffmpeg | `ffmpeg` | Audio/video conversion, trimming, merging |
| imagemagick | `imagemagick` | Image conversion, resize, crop, composite |
| exiftool | `libimage-exiftool-perl` | Read/write metadata (EXIF, IPTC, XMP) |
| sox | `sox` | Audio conversion and basic effects |
| mediainfo | `mediainfo` | Media file metadata inspection |
| optipng | `optipng` | PNG optimization |
| jpegoptim | `jpegoptim` | JPEG optimization |
| gifsicle | `gifsicle` | GIF manipulation and optimization |

### Data Processing (10 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| jq | `jq` | JSON processor and query |
| yq | `yq` | YAML/TOML/JSON/XML processor |
| csvkit | `csvkit` | CSV utilities (`csvcut`, `csvgrep`, `csvjson`) |
| sqlite3 | `sqlite3` | SQLite database CLI |
| dasel | `dasel` | Universal data selector (JSON/YAML/TOML/XML/CSV) |
| visidata | `visidata` | Interactive data exploration (all formats) |
| xsv | `xsv` | Fast CSV toolkit |
| duckdb | `duckdb` | In-process SQL analytics database |
| q | `python3-q` | Run SQL directly on CSV/TSV files |
| gron | `gron` | Make JSON greppable |

### Dev/Utils (14 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| curl | `curl` | HTTP client for API testing |
| wget | `wget` | File downloader with resume support |
| git | `git` | Version control operations |
| rsync | `rsync` | Efficient file synchronization |
| zip/unzip | `zip`, `unzip` | ZIP archive handling |
| tar | `tar` | Tape archive handling |
| zstd | `zstd` | Fast compression (Facebook's algorithm) |
| fd | `fd-find` | Modern find alternative |
| sdiff | `diffutils` | Side-by-side file comparison |
| entr | `entr` | Run commands on file changes |
| httpie | `httpie` | Human-friendly HTTP client |
| parallel | `parallel` | Execute jobs in parallel |
| tmux | `tmux` | Terminal multiplexer |
| jq | `jq` | JSON processing (also in Data) |

### Network Utilities (8 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| ssh | `openssh-client` | Secure shell client |
| scp | `openssh-client` | Secure file copy |
| openssl | `openssl` | SSL/TLS toolkit, certificate operations |
| netcat | `netcat-openbsd` | TCP/UDP networking utility |
| ngrok | Download binary | Tunnel localhost to public URL |
| httpie | `httpie` | HTTP client with JSON support |
| nmap | `nmap` | Network scanner and discovery |
| curl | `curl` | HTTP client (also in Dev) |

### Search & Research (8 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| ripgrep | `ripgrep` | Fast regex search (recursive) |
| fd | `fd-find` | Fast file finder |
| fzf | `fzf` | Fuzzy finder for interactive search |
| fselect | `fselect` | SQL-like file search |
| locate | `mlocate` | Indexed file search |
| ag | `silversearcher-ag` | Code search (ack alternative) |
| ugrep | `ugrep` | Ultra-fast grep with more features |
| ast-grep | Download binary | AST-based code search |

### Communication (4 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| msmtp | `msmtp` | SMTP client for sending email |
| offlineimap | `offlineimap` | IMAP email sync |
| notmuch | `notmuch` | Email indexer and search |
| urlscan | `urlscan` | Extract URLs from text/email |

### Calendar (3 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| calcurse | `calcurse` | Terminal calendar and todo |
| khal | `khal` | CalDAV calendar CLI |
| remind | `remind` | Sophisticated calendar reminder |

### Notes & Tasks (3 tools)
| Tool | Package | Purpose |
|------|---------|---------|
| nb | `nb` | Note-taking and knowledge base |
| taskwarrior | `taskwarrior` | Task management |
| jrnl | `jrnl` | Journal/note-taking |

**Estimated size:** ~2-2.5GB compressed

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

Each curated tool includes a FastMCP-decorated function with full schema:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agntrick-toolbox")

@mcp.tool()
async def pdf_extract_text(
    input_path: str,
    pages: str = "all",
    output_format: str = "text"
) -> str:
    """Extract text from a PDF file.

    Args:
        input_path: Path to PDF file (must be within /workspace)
        pages: Page range (e.g., '1-5', '1,3,5', 'all')
        output_format: Output format - 'text' or 'markdown'

    Returns:
        Extracted text content or error message

    Raises:
        ValueError: If input_path is outside /workspace
    """
    # Validate path is within /workspace
    validated_path = validate_workspace_path(input_path)

    # Build pdftotext command
    cmd = ["pdftotext", "-layout"]
    if pages != "all":
        # Parse page range and add flags
        first, last = parse_page_range(pages)
        cmd.extend(["-f", str(first), "-l", str(last)])
    cmd.append(validated_path)
    cmd.append("-")  # Output to stdout

    result = await run_command(cmd)
    return result.stdout
```

**Tool Schema Registry Pattern:**

```python
# src/agntrick_toolbox/schemas/definitions.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class ToolDefinition:
    name: str
    description: str
    underlying_command: str
    category: Literal["document", "media", "data", "utils", "network", "search", "comm", "calendar", "notes"]
    example_usage: str
    common_errors: dict[str, str]

TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "pdf_extract_text": ToolDefinition(
        name="pdf_extract_text",
        description="Extract text from PDF files with page range support",
        underlying_command="pdftotext",
        category="document",
        example_usage="pdf_extract_text('/workspace/report.pdf', pages='1-10')",
        common_errors={
            "Command not found": "poppler-utils not installed",
            "Syntax Warning": "PDF may be corrupted, text extraction partial",
        }
    ),
    # ... more tools
}
```
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
- [ ] All 60 curated tools have valid schemas and working implementations
- [ ] agntrick agent can discover and use tools via MCP
- [ ] Shell fallback works for non-curated commands
- [ ] Error messages are helpful and actionable
- [ ] Path confinement prevents access outside /workspace
- [ ] Health check endpoint responds correctly

---

## Implementation Guide

This section provides step-by-step instructions for implementing agntrick-toolbox.

### Phase 1: Project Setup

**Step 1.1: Create project structure**

```bash
mkdir -p agntrick-toolbox/{src/agntrick_toolbox/{tools,schemas},tests/test_tools}
cd agntrick-toolbox
```

**Step 1.2: Initialize pyproject.toml**

```toml
[project]
name = "agntrick-toolbox"
version = "0.1.0"
description = "Docker-based MCP server providing curated CLI tools for LLM agents"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=0.1.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
]

[project.scripts]
toolbox-server = "agntrick_toolbox.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 1.3: Create config module**

```python
# src/agntrick_toolbox/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    toolbox_timeout_default: int = 30
    toolbox_shell_enabled: bool = True
    toolbox_log_level: str = "INFO"
    toolbox_max_output_size: int = 1048576  # 1MB
    toolbox_port: int = 8080
    toolbox_workspace: str = "/workspace"

    class Config:
        env_prefix = ""
        env_file = ".env"

settings = Settings()
```

### Phase 2: Core Infrastructure

**Step 2.1: Create path validation module**

```python
# src/agntrick_toolbox/path_utils.py
import os
from pathlib import Path
from .config import settings

class PathValidationError(ValueError):
    """Raised when a path is outside the workspace."""

def validate_workspace_path(input_path: str) -> Path:
    """Validate that a path is within the workspace directory.

    Args:
        input_path: User-provided path (absolute or relative)

    Returns:
        Resolved absolute Path within workspace

    Raises:
        PathValidationError: If path escapes workspace
    """
    workspace = Path(settings.toolbox_workspace).resolve()
    target = (workspace / input_path).resolve() if not os.path.isabs(input_path) else Path(input_path).resolve()

    # Check if target is within workspace (handles symlinks)
    try:
        target.relative_to(workspace)
    except ValueError:
        raise PathValidationError(
            f"Path '{input_path}' is outside workspace '{workspace}'. "
            "All file operations must be within /workspace."
        )

    return target
```

**Step 2.2: Create command execution module**

```python
# src/agntrick_toolbox/executor.py
import asyncio
from dataclasses import dataclass
from typing import Any
from .config import settings

@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False

async def run_command(
    cmd: list[str],
    timeout: int | None = None,
    input_data: str | None = None,
) -> CommandResult:
    """Execute a shell command with timeout and output limits.

    Args:
        cmd: Command and arguments as list
        timeout: Timeout in seconds (default from settings)
        input_data: Optional stdin input

    Returns:
        CommandResult with stdout, stderr, and status
    """
    timeout = timeout or settings.toolbox_timeout_default

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input_data.encode() if input_data else None),
            timeout=timeout
        )

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # Truncate if too large
        truncated = len(stdout_str) > settings.toolbox_max_output_size
        if truncated:
            stdout_str = stdout_str[:settings.toolbox_max_output_size] + "\n... [output truncated]"

        return CommandResult(
            success=process.returncode == 0,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=process.returncode or 0,
            truncated=truncated,
        )

    except asyncio.TimeoutError:
        return CommandResult(
            success=False,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
            exit_code=-1,
        )
    except FileNotFoundError:
        return CommandResult(
            success=False,
            stdout="",
            stderr=f"Command not found: {cmd[0]}",
            exit_code=-1,
        )
```

### Phase 3: Tool Implementations

**Step 3.1: Create tool modules by category**

Each tool module follows this pattern:

```python
# src/agntrick_toolbox/tools/document.py
from mcp.server.fastmcp import FastMCP
from ..config import settings
from ..executor import run_command
from ..path_utils import validate_workspace_path, PathValidationError

def register_document_tools(mcp: FastMCP) -> None:
    """Register all document processing tools."""

    @mcp.tool()
    async def pdf_extract_text(
        input_path: str,
        pages: str = "all",
        layout: bool = True
    ) -> str:
        """Extract text from a PDF file.

        Args:
            input_path: Path to PDF file within workspace
            pages: Page range (e.g., '1-5', '1,3,5', 'all')
            layout: Preserve original layout

        Returns:
            Extracted text content or error message
        """
        try:
            validated = validate_workspace_path(input_path)
        except PathValidationError as e:
            return f"Error: {e}"

        cmd = ["pdftotext"]
        if layout:
            cmd.append("-layout")
        if pages != "all":
            if "-" in pages:
                first, last = pages.split("-", 1)
                cmd.extend(["-f", first.strip(), "-l", last.strip()])
            else:
                cmd.extend(["-f", pages, "-l", pages])
        cmd.extend([str(validated), "-"])

        result = await run_command(cmd)
        if not result.success:
            return f"Error: {result.stderr}"
        return result.stdout

    @mcp.tool()
    async def pandoc_convert(
        input_path: str,
        output_path: str,
        from_format: str = "markdown",
        to_format: str = "html",
    ) -> str:
        """Convert documents between formats using pandoc.

        Args:
            input_path: Source file path within workspace
            output_path: Destination file path within workspace
            from_format: Input format (markdown, html, docx, pdf, etc.)
            to_format: Output format

        Returns:
            Success message or error
        """
        try:
            in_path = validate_workspace_path(input_path)
            out_path = validate_workspace_path(output_path)
        except PathValidationError as e:
            return f"Error: {e}"

        cmd = [
            "pandoc",
            str(in_path),
            "-f", from_format,
            "-t", to_format,
            "-o", str(out_path)
        ]

        result = await run_command(cmd)
        if not result.success:
            return f"Error: {result.stderr}"
        return f"Successfully converted {input_path} to {output_path}"
```

**Step 3.2: Create shell fallback tool**

```python
# src/agntrick_toolbox/tools/shell.py
from mcp.server.fastmcp import FastMCP
from ..config import settings
from ..executor import run_command
from ..path_utils import validate_workspace_path, PathValidationError

def register_shell_tool(mcp: FastMCP) -> None:
    """Register shell fallback tool if enabled."""

    if not settings.toolbox_shell_enabled:
        return

    @mcp.tool()
    async def run_shell(
        command: str,
        timeout: int = 30,
    ) -> str:
        """Execute a shell command for tools not in curated set.

        Use sparingly - prefer curated tools when available.
        Commands are confined to /workspace directory.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds (max 300)

        Returns:
            Command output or error message
        """
        # Basic command validation
        dangerous = ["rm -rf /", "sudo", "chmod 777", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Potentially dangerous command blocked"

        # Cap timeout
        timeout = min(timeout, 300)

        # Execute in workspace directory
        import os
        os.chdir(settings.toolbox_workspace)

        result = await run_command(["sh", "-c", command], timeout=timeout)

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.truncated:
            output += "\n[output truncated due to size limit]"

        return output
```

### Phase 4: Dockerfile

```dockerfile
# Dockerfile
FROM python:3.12-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Document tools
    pandoc \
    poppler-utils \
    ghostscript \
    calibre \
    tesseract-ocr \
    ocrmypdf \
    ripgrep \
    fzf \
    bat \
    pup \
    # Media tools
    ffmpeg \
    imagemagick \
    libimage-exiftool-perl \
    sox \
    mediainfo \
    optipng \
    jpegoptim \
    gifsicle \
    # Data tools
    jq \
    yq \
    csvkit \
    sqlite3 \
    dasel \
    visidata \
    xsv \
    duckdb \
    # Dev/Utils
    curl \
    wget \
    git \
    rsync \
    zip \
    unzip \
    tar \
    zstd \
    fd-find \
    diffutils \
    entr \
    httpie \
    parallel \
    tmux \
    # Network
    openssh-client \
    openssl \
    netcat-openbsd \
    nmap \
    # Search
    silversearcher-ag \
    ugrep \
    mlocate \
    # Communication
    msmtp \
    offlineimap \
    notmuch \
    urlscan \
    # Calendar/Notes
    calcurse \
    khal \
    remind \
    taskwarrior \
    # Build tools for Python packages
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python package
WORKDIR /app
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 toolbox && \
    mkdir -p /workspace && \
    chown toolbox:toolbox /workspace

USER toolbox
WORKDIR /workspace

# Read-only root with tmpfs
# (Set in docker-compose, not here)

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["toolbox-server"]
```

### Phase 5: Server Entry Point

```python
# src/agntrick_toolbox/server.py
import asyncio
import logging
from mcp.server.fastmcp import FastMCP

from .config import settings
from .tools.document import register_document_tools
from .tools.media import register_media_tools
from .tools.data import register_data_tools
from .tools.utils import register_utils_tools
from .tools.network import register_network_tools
from .tools.search import register_search_tools
from .tools.shell import register_shell_tool

logging.basicConfig(level=getattr(logging, settings.toolbox_log_level))
logger = logging.getLogger(__name__)

mcp = FastMCP("agntrick-toolbox")

# Register all tools
register_document_tools(mcp)
register_media_tools(mcp)
register_data_tools(mcp)
register_utils_tools(mcp)
register_network_tools(mcp)
register_search_tools(mcp)
register_shell_tool(mcp)

@mcp.tool()
async def health_check() -> str:
    """Check if the toolbox server is healthy."""
    return "OK"

def main() -> None:
    """Start the MCP server."""
    logger.info(f"Starting agntrick-toolbox on port {settings.toolbox_port}")
    mcp.run(transport="sse")

if __name__ == "__main__":
    main()
```

### Phase 6: Testing

**Test structure:**

```python
# tests/conftest.py
import pytest
from agntrick_toolbox.config import Settings

@pytest.fixture
def test_settings(tmp_path):
    """Provide test settings with temporary workspace."""
    return Settings(
        toolbox_workspace=str(tmp_path),
        toolbox_timeout_default=5,
    )

# tests/test_tools/test_document.py
import pytest
from pathlib import Path
from agntrick_toolbox.tools.document import pdf_extract_text
from agntrick_toolbox.path_utils import PathValidationError

class TestPdfExtractText:
    async def test_rejects_path_outside_workspace(self, tmp_path):
        """Must reject paths outside workspace."""
        with pytest.raises(PathValidationError):
            validate_workspace_path("/etc/passwd")

    async def test_extracts_text_from_pdf(self, tmp_path):
        """Should extract text from a valid PDF."""
        # Create a simple test PDF
        # ... test implementation

    async def test_handles_page_ranges(self, tmp_path):
        """Should correctly parse page range arguments."""
        # ... test implementation
```

### Phase 7: Build and Deploy

```bash
# Build the image
docker build -t agntrick-toolbox:latest .

# Test locally
docker-compose up -d

# Verify health
curl http://localhost:8080/health

# Test a tool via MCP
# (Use agntrick agent to verify tool discovery)
```

---

## Tool Implementation Checklist

For each of the 60 tools, implement following this pattern:

- [ ] Create FastMCP `@mcp.tool()` decorated function
- [ ] Validate all path inputs with `validate_workspace_path()`
- [ ] Use `run_command()` for subprocess execution
- [ ] Return error strings (never raise exceptions)
- [ ] Add comprehensive docstring with args and returns
- [ ] Add unit tests for success and error cases
- [ ] Document common errors in TOOL_REGISTRY

### Priority Order

**Phase A (Core - 12 tools):**
1. pdf_extract_text, pandoc_convert, jq_query, yq_query
2. ffmpeg_convert, imagemagick_convert, curl_fetch, wget_download
3. ripgrep_search, fd_find, git_status, run_shell

**Phase B (Document - 8 tools):**
4. ghostscript_merge, calibre_convert, tesseract_ocr
5. ocrmypdf_add_ocr, marker_pdf_to_md, bat_view, glow_render

**Phase C (Data - 10 tools):**
6. csvkit_operations, sqlite_query, dasel_select
7. visidata_explore, xsv_operations, duckdb_query, gron_flatten

**Phase D (Remaining - 30 tools):**
8. Media tools (optipng, jpegoptim, exiftool, etc.)
9. Network tools (ssh, scp, openssl, etc.)
10. Search tools (fselect, ag, ugrep, etc.)
11. Communication/Calendar/Notes tools
