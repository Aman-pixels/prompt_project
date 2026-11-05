"""Context management CLI commands."""
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from ipdpo import config
from ipdpo.core.context_manager import ContextManager
from ipdpo.core.project_manager import ProjectManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ContextRepository, ProjectRepository
from ipdpo.models.schemas import ContextCategory

console = Console()
app = typer.Typer(help="Manage project context (set, view, import, clear).")


def get_services():
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    ctx_repo = ContextRepository(db)
    return ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE), ContextManager(ctx_repo)


@app.command("set")
def set_context(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Context category"),
    content: Optional[str] = typer.Option(None, "--content", "-t", help="Context content"),
):
    """Add or update structured context for the active project."""
    proj_mgr, ctx_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    valid_categories = [c.value for c in ContextCategory]
    if not category or category not in valid_categories:
        console.print(f"[bold cyan]Select Context Category for '{active_proj.name}':[/bold cyan]")
        for idx, cat_name in enumerate(valid_categories, 1):
            console.print(f"  [bold]{idx}.[/bold] {cat_name}")
        choice = Prompt.ask("Choose category number or name")
        if choice.isdigit() and 1 <= int(choice) <= len(valid_categories):
            category = valid_categories[int(choice) - 1]
        elif choice in valid_categories:
            category = choice
        else:
            console.print(f"[red]Invalid category '{choice}'.[/red]")
            raise typer.Exit(code=1)

    if not content:
        console.print(f"[bold green]Enter content for [{category}] (Press Enter when done, or enter multi-line text):[/bold green]")
        content = Prompt.ask("Content")

    try:
        cat_enum = ContextCategory(category)
        ctx = ctx_mgr.set_context(active_proj.project_id, cat_enum, content)
        console.print(f"[bold green]✓ Context for '{category}' successfully saved for '{active_proj.name}'![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("view")
def view_context(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Specific context category to view")
):
    """View stored context for the active project."""
    proj_mgr, ctx_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    all_ctx = ctx_mgr.get_all_context(active_proj.project_id)

    if not all_ctx:
        console.print(f"[yellow]No context entries stored yet for '{active_proj.name}'. Add with 'ipdpo context set'.[/yellow]")
        return

    if category:
        content = all_ctx.get(category)
        if not content:
            console.print(f"[yellow]No entry found for category '{category}'.[/yellow]")
            return
        console.print(Panel(Markdown(content), title=f"[bold cyan]{category}[/bold cyan] ({active_proj.name})", border_style="green"))
    else:
        table = Table(title=f"Context for {active_proj.name}", border_style="cyan")
        table.add_column("Category", style="bold cyan")
        table.add_column("Status", justify="center")
        table.add_column("Preview Snippet")

        for cat in ContextCategory:
            val = all_ctx.get(cat.value)
            if val:
                snippet = (val[:75] + "...") if len(val) > 75 else val
                table.add_row(cat.value, "[green]Set[/green]", snippet.replace("\n", " "))
            else:
                table.add_row(cat.value, "[dim yellow]Empty[/dim yellow]", "[dim]N/A[/dim]")

        console.print(table)


@app.command("import")
def import_context(
    file_path: Path = typer.Option(..., "--file", "-f", help="Path to JSON, YAML, or Markdown file"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category override if importing markdown/raw text"),
):
    """Import context from a JSON, YAML, or Markdown document."""
    proj_mgr, ctx_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    cat_override = ContextCategory(category) if category else None

    try:
        imported = ctx_mgr.import_from_file(active_proj.project_id, file_path, category_override=cat_override)
        console.print(f"[bold green]✓ Successfully imported {len(imported)} context category(s) into '{active_proj.name}':[/bold green]")
        for c in imported:
            console.print(f"  • {c.value}")
    except Exception as e:
        console.print(f"[bold red]Import Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("clear")
def clear_context(
    category: str = typer.Option(..., "--category", "-c", help="Category to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear a context category for the active project."""
    proj_mgr, ctx_mgr = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    if not force:
        if not Confirm.ask(f"Are you sure you want to delete context category '{category}'?"):
            console.print("Cancelled.")
            return

    try:
        cat_enum = ContextCategory(category)
        success = ctx_mgr.delete_context(active_proj.project_id, cat_enum)
        if success:
            console.print(f"[bold green]✓ Category '{category}' cleared.[/bold green]")
        else:
            console.print(f"[yellow]Category '{category}' was not set.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
