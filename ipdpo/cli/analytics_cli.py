"""Analytics and reporting CLI commands using Pandas."""
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ipdpo import config
from ipdpo.analytics.reports import AnalyticsEngine
from ipdpo.core.project_manager import ProjectManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ProjectRepository

console = Console()
app = typer.Typer(help="Generate prompt optimization analytics and score reports.")


def get_services():
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    return ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE), AnalyticsEngine(db)


@app.command("summary")
def project_summary(
    project_id: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID")
):
    """Display analytics summary for the active or specified project."""
    proj_mgr, analytics = get_services()
    if not project_id:
        active = proj_mgr.get_active_project()
        if not active:
            console.print("[red]No active project. Specify --project or run 'ipdpo project select'.[/red]")
            raise typer.Exit(code=1)
        project_id = active.project_id
        project_name = active.name
    else:
        proj = proj_mgr.get_project(project_id)
        project_name = proj.name if proj else project_id

    data = analytics.get_summary_metrics(project_id)

    console.print(f"[bold cyan]Analytics Summary: {project_name}[/bold cyan]")
    console.print(f"  • Total Prompts Generated: [bold]{data['total_prompts']}[/bold]")
    console.print(f"  • Total Prompt Versions Tracked: [bold]{data['total_versions']}[/bold]")
    console.print(f"  • Average Quality Score: [bold green]{data['average_score']}/100[/bold green]")

    if data["task_distribution"]:
        table = Table(title="Task Category Breakdown", border_style="cyan")
        table.add_column("Task Category", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Avg Score", justify="right")

        for task_cat, count in data["task_distribution"].items():
            avg_s = data["score_by_task"].get(task_cat, 0.0)
            table.add_row(task_cat, str(count), f"{avg_s}/100")

        console.print(table)


@app.command("global")
def global_metrics():
    """Display system-wide analytics across all projects."""
    _, analytics = get_services()
    data = analytics.get_global_metrics()

    table = Table(title="Global IPDPO Workbench Metrics", border_style="green")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Projects", str(data["total_projects"]))
    table.add_row("Total Prompts Synthesized", str(data["total_prompts"]))
    table.add_row("Total Versions Preserved", str(data["total_versions"]))
    table.add_row("Overall Average Score", f"{data['overall_average_score']}/100")

    console.print(table)
    if data["generation_methods"]:
        console.print("[bold]Generation Method Breakdown:[/bold]")
        for method, count in data["generation_methods"].items():
            console.print(f"  • {method}: {count}")
