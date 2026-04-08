"""DaenaBot CLI - connect your computer to Daena cloud.

Usage:
    daena-bot connect          Connect to your Daena account
    daena-bot start            Start the bridge daemon
    daena-bot status           Check connection status
    daena-bot install-tools    Install optional tools (browser, desktop)
"""

from __future__ import annotations

import asyncio
import sys
import webbrowser

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from daena_bot.config import BotConfig, load_config

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="daena-bot")
def main() -> None:
    """DaenaBot - Give Daena hands on your computer."""
    pass


@main.command()
@click.option("--server", default=None, help="Daena server URL")
def connect(server: str | None) -> None:
    """Connect DaenaBot to your Daena cloud account."""
    config = load_config()

    if server:
        config.server_url = server

    console.print(Panel.fit(
        "[bold]DaenaBot Setup[/bold]\n\n"
        "This will connect your computer to your Daena account.\n"
        "Daena will be able to access files, run commands, and\n"
        "control your desktop (with your permission).",
        border_style="green",
    ))

    # Open browser for authentication
    auth_url = f"{config.server_url}/auth/bot-connect"
    console.print(f"\n[cyan]Opening browser for authentication...[/cyan]")
    console.print(f"[dim]{auth_url}[/dim]\n")

    webbrowser.open(auth_url)

    # Wait for user to paste the token
    console.print(
        "After logging in, copy the connection token and paste it here.\n"
    )
    token = click.prompt("Connection token", hide_input=True)

    if not token or len(token) < 10:
        console.print("[red]Invalid token. Please try again.[/red]")
        sys.exit(1)

    config.auth_token = token.strip()
    config.save()

    console.print("\n[bold green]Connected![/bold green]")
    console.print("Run [cyan]daena-bot start[/cyan] to begin.\n")


@main.command()
@click.option("--token", default=None, help="Auth token (skip browser login)")
@click.option("--auto-approve", is_flag=True, help="Auto-approve all tool calls")
def start(token: str | None, auto_approve: bool) -> None:
    """Start the DaenaBot bridge daemon."""
    config = load_config()

    if token:
        config.auth_token = token.strip()
        config.save()

    if auto_approve:
        config.auto_approve = True

    if not config.auth_token:
        console.print(
            "[red]Not connected. Run [cyan]daena-bot connect[/cyan] first.[/red]"
        )
        sys.exit(1)

    from daena_bot.bridge import DaenaBridge

    bridge = DaenaBridge(config)

    try:
        asyncio.run(bridge.connect())
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down...[/dim]")


@main.command()
def status() -> None:
    """Check DaenaBot connection status."""
    config = load_config()

    table = Table(title="DaenaBot Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Server", config.server_url)
    table.add_row("Connected", "[green]Yes[/green]" if config.auth_token else "[red]No[/red]")
    table.add_row("Auto-approve", "Yes" if config.auto_approve else "No")
    table.add_row("Version", config.version)

    # Check capabilities
    from daena_bot.executor import ToolExecutor
    executor = ToolExecutor(config)
    caps = executor.list_capabilities()
    table.add_row("Capabilities", ", ".join(caps))

    console.print(table)


@main.command(name="install-tools")
@click.argument("tool", required=False)
def install_tools(tool: str | None) -> None:
    """Install optional tools for extended capabilities.

    Available tools: browser, desktop, all
    """
    import subprocess

    tools_map = {
        "browser": ["playwright"],
        "desktop": ["pyautogui"],
        "all": ["playwright", "pyautogui"],
    }

    if tool is None:
        console.print("Available tools:")
        console.print("  [cyan]browser[/cyan]  - Web automation (Playwright)")
        console.print("  [cyan]desktop[/cyan]  - Desktop control (mouse, keyboard, screenshots)")
        console.print("  [cyan]all[/cyan]      - Install everything")
        console.print("\nUsage: daena-bot install-tools [browser|desktop|all]")
        return

    packages = tools_map.get(tool)
    if not packages:
        console.print(f"[red]Unknown tool: {tool}[/red]")
        return

    for pkg in packages:
        console.print(f"[cyan]Installing {pkg}...[/cyan]")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

        if pkg == "playwright":
            console.print("[cyan]Installing Chromium browser...[/cyan]")
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
