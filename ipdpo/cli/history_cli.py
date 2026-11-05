"""History, audit log, and prompt version inspection CLI commands."""
import difflib
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ipdpo import config
from ipdpo.core.project_manager import ProjectManager
from ipdpo.core.version_manager import VersionManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import (
    OptimizationLogRepository,
    ProjectRepository,
    PromptRepository,
    VersionRepository,
)

console = Console()
app = typer.Typer(help="Inspect prompt versions, diffs, and optimization logs.")


def get_services():
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    prompt_repo = PromptRepository(db)
    ver_repo = VersionRepository(db)
    log_repo = OptimizationLogRepository(db)
    return (
        ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE),
        VersionManager(prompt_repo, ver_repo, log_repo),
        prompt_repo,
    )


@app.command("list")
def list_history(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project ID"),
):
    """List generated prompts and their versions."""
    proj_mgr, _, prompt_repo = get_services()
    if not project_id:
        active = proj_mgr.get_active_project()
        if not active:
            console.print("[red]No active project. Specify --project or run 'ipdpo project select'.[/red]")
            raise typer.Exit(code=1)
        project_id = active.project_id

    prompts = prompt_repo.list_by_project(project_id)
    if not prompts:
        console.print("[yellow]No prompt history found for this project.[/yellow]")
        return

    table = Table(title="Prompt History & Versions", border_style="cyan")
    table.add_column("Prompt ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Versions", justify="center")
    table.add_column("Latest Score", justify="center")
    table.add_column("Method")
    table.add_column("Updated At")

    for p in prompts:
        score = p.get("quality_score", 0.0)
        s_color = "green" if score >= 80 else ("yellow" if score >= 60 else "red")
        table.add_row(
            p["prompt_id"][:8] + "...",
            p["title"],
            p["task_type"],
            f"v{p['current_version']}",
            f"[{s_color}]{score}[/{s_color}]",
            p.get("generation_method", "N/A"),
            p["updated_at"][:19].replace("T", " "),
        )

    console.print(table)


@app.command("versions")
def prompt_versions(
    prompt_id: str = typer.Argument(..., help="Prompt ID to inspect versions for")
):
    """List all immutable versions for a specific prompt."""
    _, version_mgr, prompt_repo = get_services()
    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        console.print(f"[red]Prompt '{prompt_id}' not found.[/red]")
        return

    versions = version_mgr.list_versions(prompt.prompt_id)
    if not versions:
        console.print(f"[yellow]No versions recorded for prompt '{prompt_id}'.[/yellow]")
        return

    table = Table(title=f"Versions for: {prompt.title}", border_style="cyan")
    table.add_column("Version", justify="center", style="bold")
    table.add_column("Method")
    table.add_column("Score", justify="center")
    table.add_column("Length (chars)", justify="right")
    table.add_column("Created At")

    for v in versions:
        s_color = "green" if v.quality_score >= 80 else ("yellow" if v.quality_score >= 60 else "red")
        table.add_row(
            f"v{v.version_number}",
            v.generation_method.value,
            f"[{s_color}]{v.quality_score}[/{s_color}]",
            str(len(v.prompt_content)),
            v.created_at[:19].replace("T", " "),
        )

    console.print(table)


@app.command("diff")
def diff_versions(
    prompt_id: str = typer.Argument(..., help="Prompt ID"),
    v1: int = typer.Option(1, "--v1", help="Base version number"),
    v2: int = typer.Option(2, "--v2", help="Comparison version number"),
):
    """Display terminal diff between two versions of a prompt."""
    _, version_mgr, prompt_repo = get_services()
    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        console.print(f"[red]Prompt '{prompt_id}' not found.[/red]")
        return

    ver1 = version_mgr.get_version(prompt.prompt_id, v1)
    ver2 = version_mgr.get_version(prompt.prompt_id, v2)

    if not ver1 or not ver2:
        console.print(f"[red]Could not retrieve both versions v{v1} and v{v2}.[/red]")
        return

    diff_lines = list(
        difflib.unified_diff(
            ver1.prompt_content.splitlines(keepends=True),
            ver2.prompt_content.splitlines(keepends=True),
            fromfile=f"v{v1} ({ver1.generation_method.value})",
            tofile=f"v{v2} ({ver2.generation_method.value})",
        )
    )

    if not diff_lines:
        console.print(f"[yellow]No textual differences between v{v1} and v{v2}.[/yellow]")
        return

    diff_text = "".join(diff_lines)
    console.print(Panel(diff_text, title=f"Diff: v{v1} vs v{v2} ({prompt.title})", border_style="cyan"))
