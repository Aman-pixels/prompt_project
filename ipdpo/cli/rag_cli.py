"""RAG indexing and querying CLI commands."""
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ipdpo.core.project_manager import ProjectManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import ProjectRepository
from ipdpo.rag.service import RAGService

console = Console()
app = typer.Typer(help="Manage RAG document indexing and semantic retrieval.")


def get_services():
    from ipdpo import config
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    proj_mgr = ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE)
    rag_service = RAGService(db)
    return proj_mgr, rag_service


@app.command("index")
def index_documents(
    path: Path = typer.Option(..., "--path", "-p", help="Directory or file path to index"),
):
    """Index project source code, documentation, schemas, or markdown into RAG store."""
    proj_mgr, rag_service = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    target_path = Path(path).resolve()
    if not target_path.exists():
        console.print(f"[red]Path '{target_path}' does not exist.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Indexing '{target_path}' for active project '{active_proj.name}'...[/cyan]")
    try:
        num_chunks = rag_service.index_path(active_proj.project_id, target_path)
        console.print(f"[bold green]✓ Successfully indexed {num_chunks} chunk(s) into RAG store![/bold green]")
        console.print("[dim]Chunks are now searchable via BM25 (SQLite FTS5) and dense vectors (ChromaDB).[/dim]")
    except Exception as e:
        console.print(f"[bold red]Indexing Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("query")
def query_rag(
    query_text: str = typer.Argument(..., help="Search query or task requirement"),
    limit: int = typer.Option(3, "--limit", "-k", help="Number of chunks to retrieve"),
):
    """Test semantic & BM25 retrieval for a given query against active project index."""
    proj_mgr, rag_service = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project. Select one first with 'ipdpo project select'.[/red]")
        raise typer.Exit(code=1)

    results = rag_service.hybrid_search(active_proj.project_id, query_text, limit=limit)
    if not results:
        console.print(f"[yellow]No relevant chunks found for query in '{active_proj.name}'. Run 'ipdpo rag index' first.[/yellow]")
        return

    console.print(f"\n[bold cyan]Top {len(results)} RAG Matches for '{query_text}':[/bold cyan]\n")
    for idx, r in enumerate(results, 1):
        engine_label = f"[{r['engine']}]"
        console.print(Panel(
            r["content"],
            title=f"#{idx} | Source: {Path(r['source_file']).name} {engine_label} (Score: {r['score']})",
            border_style="green",
        ))


@app.command("clear")
def clear_index():
    """Clear all indexed RAG documents for the active project."""
    proj_mgr, rag_service = get_services()
    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project.[/red]")
        raise typer.Exit(code=1)

    rag_service.clear_project_index(active_proj.project_id)
    console.print(f"[bold green]✓ Cleared all RAG index data for '{active_proj.name}'.[/bold green]")
