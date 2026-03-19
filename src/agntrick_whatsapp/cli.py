"""CLI runner for agntrick-whatsapp.

Provides a ``agntrick-whatsapp`` command that starts a WhatsApp agent with
zero required code changes — all configuration comes from YAML files,
environment variables, or CLI flags.

Usage examples::

    # Start with defaults (bridge mode, all paths auto-detected)
    agntrick-whatsapp start --allowed-contact "+34666666666"

    # Start with a specific model
    agntrick-whatsapp start --model gpt-4o-mini --allowed-contact "+34666666666"

    # Show resolved configuration
    agntrick-whatsapp config

    # Generate a starter config file
    agntrick-whatsapp init
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agntrick_whatsapp import __version__
from agntrick_whatsapp.runner_config import (
    WhatsAppRunnerSettings,
    load_settings,
)

app = typer.Typer(
    name="agntrick-whatsapp",
    help="WhatsApp agent runner — start a fully-configured WhatsApp agent from the command line.",
    add_completion=True,
    no_args_is_help=True,
)
console = Console()
logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    """Set up root logging with the given level."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
        force=True,
    )


def _display_settings(settings: WhatsAppRunnerSettings) -> None:
    """Print a rich table summarising the resolved settings."""
    table = Table(title="Resolved Configuration", show_lines=True)
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("mode", settings.mode)
    table.add_row("storage_path", str(settings.storage_path))
    table.add_row("allowed_contact", settings.allowed_contact or "(accept all)")
    table.add_row("typing_indicators", str(settings.typing_indicators))
    table.add_row("min_typing_duration", f"{settings.min_typing_duration}s")
    table.add_row("dedup_window", f"{settings.dedup_window}s")

    if settings.mode == "api":
        table.add_row("access_token", f"{settings.access_token[:6]}***" if settings.access_token else "(unset)")
        table.add_row("phone_number_id", settings.phone_number_id or "(unset)")

    table.add_row("model_name", settings.model_name or "(auto)")
    table.add_row("temperature", str(settings.temperature))
    table.add_row("mcp_servers", ", ".join(settings.mcp_servers) if settings.mcp_servers else "(default)")
    table.add_row("db_path", str(settings.db_path))
    table.add_row("log_level", settings.log_level)
    table.add_row("debug", str(settings.debug))

    console.print(table)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def start(
    allowed_contact: Optional[str] = typer.Option(None, "--allowed-contact", "-c", help="Phone number to accept."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model name."),
    temperature: Optional[float] = typer.Option(None, "--temperature", "-T", help="LLM temperature."),
    storage_path: Optional[Path] = typer.Option(None, "--storage-path", help="Neonize session storage directory."),
    db_path: Optional[Path] = typer.Option(None, "--db-path", help="SQLite database path for notes/tasks."),
    mode: Optional[str] = typer.Option(None, "--mode", help="Channel mode: bridge or api."),
    debug: Optional[bool] = typer.Option(None, "--debug/--no-debug", help="Enable debug logging."),
    access_token: Optional[str] = typer.Option(None, "--access-token", help="Business API access token."),
    phone_number_id: Optional[str] = typer.Option(None, "--phone-number-id", help="Business API phone number ID."),
    mcp_servers: Optional[str] = typer.Option(None, "--mcp-servers", help="Comma-separated MCP server names."),
    system_prompt: Optional[str] = typer.Option(None, "--system-prompt", help="Override default system prompt."),
) -> None:
    """Start the WhatsApp agent."""
    cli_args: dict[str, object] = dict(
        allowed_contact=allowed_contact,
        model_name=model,
        temperature=temperature,
        storage_path=storage_path,
        db_path=db_path,
        mode=mode,
        debug=debug,
        access_token=access_token,
        phone_number_id=phone_number_id,
        system_prompt=system_prompt,
    )
    if mcp_servers is not None:
        cli_args["mcp_servers"] = [s.strip() for s in mcp_servers.split(",") if s.strip()]

    try:
        settings = load_settings(**cli_args)
    except Exception as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _configure_logging(settings.log_level)

    console.print(
        Panel(
            f"[bold]agntrick-whatsapp[/bold] v{__version__}\n"
            f"Mode: [cyan]{settings.mode}[/cyan]  "
            f"Model: [cyan]{settings.model_name or 'auto'}[/cyan]  "
            f"Contact: [cyan]{settings.allowed_contact or 'any'}[/cyan]",
            title="Starting WhatsApp Agent",
            border_style="blue",
        )
    )

    if settings.debug:
        _display_settings(settings)

    try:
        asyncio.run(_run_agent(settings))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted — shutting down.[/yellow]")
    except Exception as exc:
        console.print(f"[bold red]Fatal error:[/bold red] {exc}")
        if settings.debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from exc


@app.command(name="config")
def show_config(
    debug: bool = typer.Option(False, "--debug/--no-debug", help="Show debug-level config."),
) -> None:
    """Display the resolved configuration (from YAML + env vars)."""
    try:
        settings = load_settings(debug=debug if debug else None)
    except Exception as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _display_settings(settings)


@app.command()
def init(
    output: Path = typer.Option(
        Path(".agntrick.yaml"),
        "--output",
        "-o",
        help="Output path for the generated config file.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file."),
) -> None:
    """Generate a starter ``.agntrick.yaml`` with a ``whatsapp:`` section."""
    if output.exists() and not force:
        console.print(
            f"[yellow]File already exists:[/yellow] {output}\n"
            "Use [bold]--force[/bold] to overwrite, or edit the existing file."
        )
        raise typer.Exit(code=1)

    template = _config_template()

    if output.exists():
        _merge_whatsapp_section(output, template)
        console.print(f"[green]Merged 'whatsapp:' section into {output}[/green]")
    else:
        output.write_text(template)
        console.print(f"[green]Created {output}[/green]")

    console.print("[dim]Edit the file and run [bold]agntrick-whatsapp start[/bold] to begin.[/dim]")


@app.command()
def version() -> None:
    """Show the package version."""
    console.print(f"agntrick-whatsapp {__version__}")


# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------


async def _run_agent(settings: WhatsAppRunnerSettings) -> None:
    """Build the channel, router, and run until interrupted."""
    from agntrick_whatsapp.channel import WhatsAppChannel
    from agntrick_whatsapp.router import WhatsAppRouterAgent
    from agntrick_whatsapp.storage import Database, get_default_db

    # Ensure data directories exist
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Build channel
    if settings.mode == "bridge":
        channel = WhatsAppChannel(
            storage_path=str(settings.storage_path),
            allowed_contact=settings.allowed_contact,
            log_filtered_messages=settings.log_filtered_messages,
            poll_interval=settings.poll_interval,
            typing_indicators=settings.typing_indicators,
            min_typing_duration=settings.min_typing_duration,
            dedup_window=settings.dedup_window,
        )
    elif settings.mode == "api":
        channel = WhatsAppChannel(
            access_token=settings.access_token,
            phone_number_id=settings.phone_number_id,
        )
    else:
        console.print(f"[bold red]Unknown mode:[/bold red] {settings.mode}")
        return

    # Build DB
    db: Database | None = None
    if settings.db_path != WhatsAppRunnerSettings.model_fields["db_path"].default:
        db = Database(settings.db_path)

    # Build custom agent if system prompt override is provided
    agent = None
    if settings.system_prompt:
        from agntrick.agent import AgentBase  # type: ignore[import-untyped]

        prompt_text = settings.system_prompt

        class CustomPromptAgent(AgentBase):
            @property
            def system_prompt(self) -> str:
                return prompt_text

            def local_tools(self) -> list:  # type: ignore[type-arg]
                return []

        agent = CustomPromptAgent(
            model_name=settings.model_name,
            temperature=settings.temperature,
        )

    # Build router
    router = WhatsAppRouterAgent(
        channel=channel,
        model_name=settings.model_name,
        temperature=settings.temperature,
        mcp_servers_override=settings.mcp_servers,
        agent=agent,
        db=db,
    )

    # Graceful shutdown on SIGTERM / SIGINT
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Start
    await router.start()
    console.print("[bold green]Agent is running.[/bold green] Press Ctrl+C to stop.")

    # Wait until shutdown signal
    await stop_event.wait()

    console.print("[yellow]Shutting down...[/yellow]")
    await router.stop()
    console.print("[green]Shutdown complete.[/green]")


# ---------------------------------------------------------------------------
# Config template helpers
# ---------------------------------------------------------------------------

_TEMPLATE = """\
# agntrick-whatsapp configuration
# Documentation: https://github.com/jeancsil/agntrick-whatsapp#readme
#
# This file is read automatically from:
#   1. ./.agntrick.yaml  (current directory)
#   2. ~/.agntrick.yaml  (home directory)
#
# You can also point to a custom file with:
#   export AGNTRICK_WA_CONFIG=/path/to/config.yaml
#
# Every setting can be overridden with an environment variable:
#   AGNTRICK_WA_<SETTING_NAME>  (e.g. AGNTRICK_WA_ALLOWED_CONTACT="+34666666666")

whatsapp:
  # Channel mode: "bridge" (QR code login) or "api" (Business API)
  mode: bridge

  # --- Bridge mode settings ---
  # storage_path: ~/.local/share/agntrick-whatsapp/session
  allowed_contact: ""          # e.g. "+34666666666" — leave empty to accept all
  typing_indicators: true
  min_typing_duration: 2.0     # seconds
  dedup_window: 10.0           # seconds

  # --- Business API settings (only used when mode=api) ---
  # access_token: "EAA..."
  # phone_number_id: "123456789"

  # --- Agent settings ---
  # model_name: gpt-4o-mini    # auto-detected if not set
  temperature: 0.7
  # mcp_servers:
  #   - fetch
  # system_prompt: "You are a helpful assistant."

  # --- Storage ---
  # db_path: ~/.local/share/agntrick-whatsapp/whatsapp.db

  # --- Logging ---
  log_level: INFO
  debug: false
"""


def _config_template() -> str:
    return _TEMPLATE


def _merge_whatsapp_section(path: Path, template: str) -> None:
    """Append the whatsapp section to an existing YAML file if missing."""
    import yaml

    existing = yaml.safe_load(path.read_text()) or {}
    if "whatsapp" in existing:
        console.print("[yellow]'whatsapp:' section already exists — overwriting.[/yellow]")

    # Simply overwrite — YAML round-tripping without losing comments is fragile;
    # appending the template block is the safest approach.
    content = path.read_text()
    if "whatsapp:" not in content:
        # Extract just the whatsapp: block from the template
        lines = template.split("\n")
        wa_start = next(i for i, line in enumerate(lines) if line.startswith("whatsapp:"))
        wa_block = "\n".join(lines[wa_start:])
        content = content.rstrip() + "\n\n" + wa_block + "\n"
        path.write_text(content)
    else:
        path.write_text(template)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
