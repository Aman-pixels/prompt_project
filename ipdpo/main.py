"""Interactive Project Development Prompt Optimizer (IPDPO) Main Entry Point."""
import typer
from rich.console import Console
from rich.panel import Panel
from ipdpo import __version__
from ipdpo.cli.analytics_cli import app as analytics_app
from ipdpo.cli.context_cli import app as context_app
from ipdpo.cli.history_cli import app as history_app
from ipdpo.cli.project_cli import app as project_app
from ipdpo.cli.prompt_cli import app as prompt_app
from ipdpo.cli.rag_cli import app as rag_app
from ipdpo.cli.task_cli import app as task_app
from ipdpo.core.project_manager import ProjectManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ProjectRepository

console = Console()

app = typer.Typer(
    name="ipdpo",
    help="Interactive Project Development Prompt Optimizer (IPDPO) CLI Workbench.",
    no_args_is_help=False,
)

# Register Subcommand Groups
app.add_typer(project_app, name="project")
app.add_typer(context_app, name="context")
app.add_typer(task_app, name="task")
app.add_typer(prompt_app, name="prompt")
app.add_typer(rag_app, name="rag")
app.add_typer(history_app, name="history")
app.add_typer(analytics_app, name="analytics")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show IPDPO version and exit"),
):
    """Interactive Project Development Prompt Optimizer (IPDPO) Workbench."""
    if version:
        console.print(f"[bold cyan]IPDPO version {__version__}[/bold cyan]")
        raise typer.Exit()

    # If user ran `ipdpo` with no subcommands, show welcome dashboard and active project
    if ctx.invoked_subcommand is None:
        db = Database()
        db.initialize_schema()
        proj_repo = ProjectRepository(db)
        proj_mgr = ProjectManager(proj_repo)
        active_proj = proj_mgr.get_active_project()

        active_info = (
            f"[bold green]Active Project:[/bold green] {active_proj.name} ({active_proj.project_id[:8]}...)"
            if active_proj
            else "[yellow]No active project selected. Run 'ipdpo project create' or 'ipdpo project select'.[/yellow]"
        )

        welcome_banner = (
            f"[bold cyan]INTERACTIVE PROJECT DEVELOPMENT PROMPT OPTIMIZER (IPDPO)[/bold cyan] v{__version__}\n"
            f"[dim]A prompt engineering workbench for structured software development lifecycles.[/dim]\n\n"
            f"{active_info}\n\n"
            f"[bold]Quick Navigation:[/bold]\n"
            f"  • [cyan]ipdpo project[/cyan]   - Manage projects (create, list, select, archive)\n"
            f"  • [cyan]ipdpo context[/cyan]   - Manage persistent project context categories\n"
            f"  • [cyan]ipdpo rag[/cyan]       - Index & query project source code & documentation\n"
            f"  • [cyan]ipdpo task[/cyan]      - Define development tasks\n"
            f"  • [cyan]ipdpo prompt[/cyan]    - Generate, evaluate, refine, and export prompts\n"
            f"  • [cyan]ipdpo history[/cyan]   - Inspect previous prompt versions and diffs\n"
            f"  • [cyan]ipdpo analytics[/cyan] - View Pandas-powered metrics and quality trends\n\n"
            f"Type [bold]ipdpo --help[/bold] or [bold]ipdpo <command> --help[/bold] for detailed command options."
        )
        console.print(Panel(welcome_banner, border_style="cyan"))


if __name__ == "__main__":
    app()
