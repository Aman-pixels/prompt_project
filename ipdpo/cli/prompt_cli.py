"""Prompt generation, refinement, evaluation, and export CLI commands."""
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
from ipdpo.core.export_manager import ExportManager
from ipdpo.core.project_manager import ProjectManager
from ipdpo.core.prompt_engine import PromptEngine
from ipdpo.core.quality_evaluator import QualityEvaluator
from ipdpo.core.task_manager import TaskManager
from ipdpo.core.version_manager import VersionManager
from ipdpo.database.connection import Database
from ipdpo.database.repositories import (
    ContextRepository,
    OptimizationLogRepository,
    ProjectRepository,
    PromptRepository,
    TaskRepository,
    VersionRepository,
)
from ipdpo.llm.gemini_client import GeminiClient
from ipdpo.models.schemas import GenerationMethod, TaskType
from ipdpo.rag.service import RAGService

console = Console()
app = typer.Typer(help="Generate, refine, review, evaluate, and export prompts.")


def get_environment():
    db = Database()
    db.initialize_schema()
    proj_repo = ProjectRepository(db)
    ctx_repo = ContextRepository(db)
    task_repo = TaskRepository(db)
    prompt_repo = PromptRepository(db)
    version_repo = VersionRepository(db)
    log_repo = OptimizationLogRepository(db)
    rag_service = RAGService(db)

    return (
        ProjectManager(proj_repo, active_file=config.ACTIVE_PROJECT_FILE),
        ContextManager(ctx_repo),
        TaskManager(task_repo),
        PromptEngine(),
        QualityEvaluator(),
        VersionManager(prompt_repo, version_repo, log_repo),
        ExportManager(export_dir=config.DEFAULT_EXPORT_DIR),
        GeminiClient(),
        prompt_repo,
        rag_service,
    )


def display_evaluation(evaluation, title="Prompt Quality Evaluation"):
    score = evaluation.overall_score
    color = "green" if score >= 80 else ("yellow" if score >= 60 else "red")

    table = Table(title=f"{title} (Composite Score: [{color}]{score}/100[/{color}])", border_style="cyan")
    table.add_column("Dimension", style="bold")
    table.add_column("Weight", justify="center")
    table.add_column("Score", justify="center")
    table.add_column("Findings & Observations")

    for name, dim in [
        ("Clarity (C)", evaluation.clarity),
        ("Context Completeness (K)", evaluation.context_completeness),
        ("Task Specificity (S)", evaluation.task_specificity),
        ("Constraint Definition (R)", evaluation.constraint_definition),
        ("Output Specification (O)", evaluation.output_specification),
    ]:
        d_color = "green" if dim.score >= 80 else ("yellow" if dim.score >= 60 else "red")
        obs = "; ".join(dim.findings) if dim.findings else "[green]All criteria satisfied[/green]"
        table.add_row(name, f"{int(dim.weight * 100)}%", f"[{d_color}]{dim.score}[/{d_color}]", obs)

    console.print(table)
    if evaluation.recommendations:
        console.print("[bold yellow]Recommendations for Improvement:[/bold yellow]")
        for rec in evaluation.recommendations:
            console.print(f"  • {rec}")
    console.print("[dim italic]Note: This score is a heuristic indicator and does not guarantee model output perfection.[/dim italic]\n")


@app.command("generate")
def generate_prompt(
    task_type: Optional[str] = typer.Option(None, "--type", "-t", help="Task type"),
    title: Optional[str] = typer.Option(None, "--title", help="Prompt title"),
    task_desc: Optional[str] = typer.Option(None, "--desc", "-d", help="Task description"),
    input_file: Optional[Path] = typer.Option(None, "--input-file", "-i", help="Supplementary input file"),
    use_rag: bool = typer.Option(False, "--rag", help="Enrich prompt with semantic RAG snippets from indexed project files"),
    rag_limit: int = typer.Option(3, "--top-k", help="Maximum RAG snippets to retrieve"),
):
    """Interactive workflow to assemble, optimize, evaluate, and save a prompt."""
    (
        proj_mgr,
        ctx_mgr,
        task_mgr,
        prompt_engine,
        evaluator,
        version_mgr,
        export_mgr,
        gemini_client,
        prompt_repo,
        rag_service,
    ) = get_environment()

    active_proj = proj_mgr.get_active_project()
    if not active_proj:
        console.print("[red]No active project selected. Run 'ipdpo project select' first.[/red]")
        raise typer.Exit(code=1)

    valid_types = [t.value for t in TaskType]
    if not task_type or task_type not in valid_types:
        console.print(f"[bold cyan]Select Task Type for '{active_proj.name}':[/bold cyan]")
        for idx, t_name in enumerate(valid_types, 1):
            console.print(f"  [bold]{idx}.[/bold] {t_name}")
        choice = Prompt.ask("Choose category number or name")
        if choice.isdigit() and 1 <= int(choice) <= len(valid_types):
            task_type = valid_types[int(choice) - 1]
        elif choice in valid_types:
            task_type = choice
        else:
            console.print(f"[red]Invalid task type '{choice}'.[/red]")
            raise typer.Exit(code=1)

    t_enum = TaskType(task_type)

    if not title:
        title = Prompt.ask("Enter a title for this prompt session")
    if not task_desc:
        task_desc = Prompt.ask("Enter immediate task description")

    supplementary = ""
    if input_file and input_file.exists():
        supplementary = input_file.read_text(encoding="utf-8")
    elif not input_file:
        supp_check = Confirm.ask("Do you want to provide supplementary input (code snippet, error log, schema)?", default=False)
        if supp_check:
            supplementary = Prompt.ask("Enter supplementary input")

    # Step 1: Context Retrieval & Missing Check
    relevant_ctx = ctx_mgr.get_relevant_context(active_proj.project_id, t_enum)
    missing = ctx_mgr.get_missing_categories(active_proj.project_id, t_enum)

    # Optional RAG semantic augmentation
    if use_rag:
        console.print(f"[cyan]Searching RAG index for task-relevant snippets (query: '{task_desc[:40]}...')...[/cyan]")
        rag_hits = rag_service.hybrid_search(active_proj.project_id, task_desc, limit=rag_limit)
        if rag_hits:
            console.print(f"[bold green]✓ Retrieved {len(rag_hits)} semantic snippet(s) from indexed codebase/docs.[/bold green]")
            relevant_ctx["rag_snippets"] = [
                f"[{Path(h['source_file']).name} ({h['engine']})]:\n{h['content']}"
                for h in rag_hits
            ]
        else:
            console.print("[yellow]No relevant RAG chunks found in index. Proceeding with stored category context.[/yellow]")

    if missing:
        console.print(f"[yellow]Notice: The following relevant context items are currently missing for this project:[/yellow]")
        for m in missing:
            console.print(f"  - {m}")
        if not Confirm.ask("Do you want to proceed with available context?", default=True):
            console.print("Generation cancelled. Populate context with 'ipdpo context set'.")
            return

    # Step 2: Local Deterministic Prompt Assembly
    console.print("\n[cyan]Assembling prompt using task-specific Jinja2 template...[/cyan]")
    draft_prompt = prompt_engine.render_prompt(
        task_type=t_enum,
        task_description=task_desc,
        context=relevant_ctx,
        supplementary_input=supplementary,
    )

    # Step 3: Heuristic Evaluation
    current_evaluation = evaluator.evaluate(
        prompt_text=draft_prompt,
        context=relevant_ctx,
        task_type=t_enum,
        task_description=task_desc,
        supplementary_input=supplementary,
    )

    # Step 4: Interactive Review Loop
    current_prompt = draft_prompt
    current_method = GenerationMethod.LOCAL_TEMPLATE
    refinement_notes = None
    exec_latency = 0
    model_name = None

    while True:
        console.print("\n" + "=" * 80)
        console.print(Panel(Markdown(current_prompt), title="Current Generated Prompt Draft", border_style="cyan"))
        display_evaluation(current_evaluation)

        console.print("[bold]Available Actions:[/bold]")
        console.print("  [A] Approve & Save Prompt Version")
        console.print("  [R] Refine & Sharpen with Gemini (LLM)")
        console.print("  [C] Copy Prompt to Clipboard")
        console.print("  [D] Discard & Exit")

        action = Prompt.ask("Choose action", choices=["A", "a", "R", "r", "C", "c", "D", "d"], default="A").upper()

        if action == "C":
            if export_mgr.copy_to_clipboard(current_prompt):
                console.print("[green]✓ Copied prompt to clipboard![/green]")
            else:
                console.print("[yellow]Clipboard copy not supported on this host environment.[/yellow]")
            continue

        elif action == "R":
            console.print("[cyan]Requesting Gemini semantic refinement...[/cyan]")
            success, result, notes, latency = gemini_client.refine_prompt(
                draft_prompt=current_prompt,
                task_type=t_enum.value,
            )
            if success and result:
                console.print(f"[green]✓ Gemini Refinement Completed in {latency}ms![/green]")
                current_prompt = result.refined_prompt
                current_method = GenerationMethod.GEMINI_REFINED
                model_name = gemini_client.model_name
                refinement_notes = {
                    "weaknesses": result.weaknesses_identified,
                    "improvements": result.improvements_made,
                    "notes": notes,
                }
                exec_latency = latency
                # Re-evaluate refined prompt
                current_evaluation = evaluator.evaluate(
                    prompt_text=current_prompt,
                    context=relevant_ctx,
                    task_type=t_enum,
                    task_description=task_desc,
                    supplementary_input=supplementary,
                )
            else:
                console.print(f"[bold red]Refinement Failed / Offline:[/bold red] {notes}")
                console.print("[yellow]Continuing with local deterministic version.[/yellow]")

        elif action == "D":
            console.print("[yellow]Prompt generation aborted. No records saved.[/yellow]")
            return

        elif action == "A":
            # Save prompt version
            saved_ver = version_mgr.save_new_prompt(
                project_id=active_proj.project_id,
                title=title,
                task_type=t_enum,
                prompt_content=current_prompt,
                evaluation=current_evaluation,
                generation_method=current_method,
                raw_input_task=task_desc,
                model_name=model_name,
                refinement_notes=refinement_notes,
                execution_time_ms=exec_latency,
            )
            console.print(f"\n[bold green]✓ Prompt saved successfully as Version 1![/bold green]")
            console.print(f"  [bold]Prompt ID:[/bold] {saved_ver.prompt_id}")
            console.print(f"  [bold]Version:[/bold] v{saved_ver.version_number}")
            console.print(f"  [bold]Final Quality Score:[/bold] {saved_ver.quality_score}/100")

            # Try to copy to clipboard
            export_mgr.copy_to_clipboard(current_prompt)

            # Auto export prompt to Markdown
            saved_prompt_obj = prompt_repo.get_by_id(saved_ver.prompt_id)
            if saved_prompt_obj:
                exp_path = export_mgr.export(saved_prompt_obj, saved_ver, format_type="md")
                console.print(f"  [bold]Exported to:[/bold] [cyan]{exp_path}[/cyan]")
            break


@app.command("show")
def show_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt ID to inspect"),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Specific version number"),
):
    """Display a stored prompt and its evaluation breakdown."""
    _, _, _, _, _, version_mgr, _, _, prompt_repo = get_environment()

    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        console.print(f"[red]Prompt '{prompt_id}' not found.[/red]")
        return

    ver_num = version if version is not None else prompt.current_version
    ver_obj = version_mgr.get_version(prompt.prompt_id, ver_num)
    if not ver_obj:
        console.print(f"[red]Version v{ver_num} not found for prompt '{prompt_id}'.[/red]")
        return

    console.print(Panel(
        Markdown(ver_obj.prompt_content),
        title=f"[bold]{prompt.title}[/bold] (v{ver_obj.version_number} - {ver_obj.generation_method.value} - Score: {ver_obj.quality_score}/100)",
        border_style="green",
    ))


@app.command("export")
def export_prompt(
    prompt_id: str = typer.Argument(..., help="Prompt ID to export"),
    format_type: str = typer.Option("md", "--format", "-f", help="Export format: md, txt, json"),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Version number (defaults to latest)"),
    out_dir: Optional[Path] = typer.Option(None, "--out", "-o", help="Custom output directory"),
):
    """Export a prompt version to disk (Markdown, TXT, or JSON)."""
    _, ctx_mgr, _, _, _, version_mgr, export_mgr, _, prompt_repo = get_environment()

    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        console.print(f"[red]Prompt '{prompt_id}' not found.[/red]")
        return

    ver_num = version if version is not None else prompt.current_version
    ver_obj = version_mgr.get_version(prompt.prompt_id, ver_num)
    if not ver_obj:
        console.print(f"[red]Version v{ver_num} not found.[/red]")
        return

    context_data = ctx_mgr.get_all_context(prompt.project_id)
    try:
        path = export_mgr.export(prompt, ver_obj, format_type=format_type, output_dir=out_dir, context_data=context_data)
        console.print(f"[bold green]✓ Export successful![/bold green] File written to: [cyan]{path}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Export Error:[/bold red] {e}")
