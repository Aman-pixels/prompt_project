"""Project management CLI commands."""
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from ipdpo import config
from ipdpo.core.project_manager import ProjectManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ProjectRepository

console = Console()
app = typer.Typer(help="Manage IPDPO projects (create, list, select, archive, delete).")


def get_manager() -> ProjectManager:
    db = Database()
    db.initialize_schema()
    repo = ProjectRepository(db)
    return ProjectManager(repo, active_file=config.ACTIVE_PROJECT_FILE)


@app.command("create")
def create_project(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name"),
    description: Optional[str] = typer.Option("", "--desc", "-d", help="Project description"),
):
    """Create a new project profile."""
    manager = get_manager()
    if not name:
        name = Prompt.ask("[bold green]Enter project name[/bold green]")
    if description is None:
        description = ""

    try:
        project = manager.create_project(name=name, description=description)
        console.print(f"[bold green]✓ Project created successfully![/bold green]")
        console.print(f"  [bold]ID:[/bold] {project.project_id}")
        console.print(f"  [bold]Name:[/bold] {project.name}")
        console.print(f"  [bold]Status:[/bold] {project.status.value}")
        console.print(f"  [cyan](Set as current active project)[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_projects(
    all_projects: bool = typer.Option(False, "--all", "-a", help="Include archived and deleted projects")
):
    """List all projects."""
    manager = get_manager()
    projects = manager.list_projects(include_archived=all_projects)
    active_id = manager.get_active_project_id()

    if not projects:
        console.print("[yellow]No projects found. Create one with 'ipdpo project create'.[/yellow]")
        return

    table = Table(title="IPDPO Projects", border_style="cyan")
    table.add_column("Active", justify="center", style="bold green")
    table.add_column("Project ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Contexts", justify="right")
    table.add_column("Description")

    for p in projects:
        is_active = "★" if p["project_id"] == active_id else ""
        status_color = "green" if p["status"] == "active" else "yellow"
        table.add_row(
            is_active,
            p["project_id"][:8] + "...",
            p["name"],
            f"[{status_color}]{p['status']}[/{status_color}]",
            str(p.get("context_count", 0)),
            p.get("description", "") or "",
        )

    console.print(table)


@app.command("select")
def select_project(
    identifier: Optional[str] = typer.Argument(None, help="Project name or ID")
):
    """Set the active working project."""
    manager = get_manager()
    if not identifier:
        projects = manager.list_projects()
        if not projects:
            console.print("[yellow]No projects exist yet.[/yellow]")
            return
        console.print("Available Projects:")
        for idx, p in enumerate(projects, 1):
            console.print(f"  [bold]{idx}.[/bold] {p['name']} ({p['project_id'][:8]}...)")
        choice = Prompt.ask("Select project number or ID")
        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            identifier = projects[int(choice) - 1]["project_id"]
        else:
            identifier = choice

    # Check ID or Name
    proj = manager.get_project(identifier) or manager.get_project_by_name(identifier)
    if not proj:
        console.print(f"[bold red]Error:[/bold red] Project '{identifier}' not found.")
        raise typer.Exit(code=1)

    manager.set_active_project(proj.project_id)
    console.print(f"[bold green]✓ Active project switched to:[/bold green] [bold]{proj.name}[/bold] ({proj.project_id[:8]}...)")


@app.command("status")
def project_status():
    """Display information about the currently active project."""
    manager = get_manager()
    proj = manager.get_active_project()
    if not proj:
        console.print("[yellow]No project is currently active. Select one with 'ipdpo project select'.[/yellow]")
        return

    console.print(f"[bold cyan]Active Project Summary[/bold cyan]")
    console.print(f"  [bold]Name:[/bold] {proj.name}")
    console.print(f"  [bold]ID:[/bold] {proj.project_id}")
    console.print(f"  [bold]Status:[/bold] {proj.status.value}")
    console.print(f"  [bold]Description:[/bold] {proj.description or 'N/A'}")
    console.print(f"  [bold]Created At:[/bold] {proj.created_at}")


@app.command("archive")
def archive_project(
    project_id: Optional[str] = typer.Argument(None, help="Project ID or name to archive")
):
    """Archive a project."""
    manager = get_manager()
    if not project_id:
        active = manager.get_active_project()
        if not active:
            console.print("[red]No project specified and no project currently active.[/red]")
            return
        project_id = active.project_id

    proj = manager.get_project(project_id) or manager.get_project_by_name(project_id)
    if not proj:
        console.print(f"[red]Project '{project_id}' not found.[/red]")
        return

    manager.archive_project(proj.project_id)
    console.print(f"[yellow]Project '{proj.name}' has been archived.[/yellow]")


@app.command("delete")
def delete_project(
    project_id: Optional[str] = typer.Argument(None, help="Project ID or name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
):
    """Delete a project and its associated context, tasks, and prompts."""
    manager = get_manager()
    if not project_id:
        active = manager.get_active_project()
        if not active:
            console.print("[red]No project specified.[/red]")
            return
        project_id = active.project_id

    proj = manager.get_project(project_id) or manager.get_project_by_name(project_id)
    if not proj:
        console.print(f"[red]Project '{project_id}' not found.[/red]")
        return

    if not force:
        confirm = Confirm.ask(f"[bold red]Are you sure you want to delete project '{proj.name}' and all its history?[/bold red]")
        if not confirm:
            console.print("Deletion aborted.")
            return

    manager.delete_project(proj.project_id)
    console.print(f"[bold green]✓ Project '{proj.name}' successfully deleted.[/bold green]")
