"""Development task management CLI commands."""
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from ipdpo import config
from ipdpo.core.project_manager import ProjectManager
from ipdpo.core.task_manager import TaskManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ProjectRepository, TaskRepository
from ipdpo.models.schemas import TaskType

console = Console()
app = typer.Typer(help="Manage development tasks (create, list, view).")


def get_services():
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    task_repo = TaskRepository(db)
    return ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE), TaskManager(task_repo)


@app.command("create")
def create_task(
    task_type: Optional[str] = typer.Option(None, "--type", "-t", help="Task category"),
    title: Optional[str] = typer.Option(None, "--title", help="Short task title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Task description"),
    input_file: Optional[Path] = typer.Option(None, "--input-file", "-i", help="Supplementary input file"),
):
    """Create a new development task under the active project."""
    proj_mgr, task_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    valid_types = [t.value for t in TaskType]
    if not task_type or task_type not in valid_types:
        console.print("[bold cyan]Select Task Category:[/bold cyan]")
        for idx, t_name in enumerate(valid_types, 1):
            console.print(f"  [bold]{idx}.[/bold] {t_name}")
        choice = Prompt.ask("Choose category number or name")
        if choice.isdigit() and 1 <= int(choice) <= len(valid_types):
            task_type = valid_types[int(choice) - 1]
        elif choice in valid_types:
            task_type = choice
        else:
            console.print(f"[red]Invalid category '{choice}'.[/red]")
            raise typer.Exit(code=1)

    if not title:
        title = Prompt.ask("Enter short task title")
    if not description:
        description = Prompt.ask("Enter detailed task description")

    supplementary = ""
    if input_file and input_file.exists():
        supplementary = input_file.read_text(encoding="utf-8")

    try:
        t_enum = TaskType(task_type)
        task = task_mgr.create_task(
            project_id=active_proj.project_id,
            task_type=t_enum,
            title=title,
            description=description,
            supplementary_input=supplementary,
        )
        console.print(f"[bold green]✓ Task '{task.title}' created successfully![/bold green]")
        console.print(f"  [bold]Task ID:[/bold] {task.task_id}")
        console.print(f"  [bold]Category:[/bold] {task.task_type.value}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_tasks():
    """List all tasks registered for the active project."""
    proj_mgr, task_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    tasks = task_mgr.list_tasks(active_proj.project_id)
    if not tasks:
        console.print(f"[yellow]No tasks found for '{active_proj.name}'. Create one with 'ipdpo task create'.[/yellow]")
        return

    table = Table(title=f"Development Tasks: {active_proj.name}", border_style="cyan")
    table.add_column("Task ID", style="dim")
    table.add_column("Category", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Status")
    table.add_column("Created At")

    for t in tasks:
        table.add_row(
            t.task_id[:8] + "...",
            t.task_type.value,
            t.title,
            t.status.value,
            t.created_at[:19].replace("T", " "),
        )

    console.print(table)
