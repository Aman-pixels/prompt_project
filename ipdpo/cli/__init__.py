"""CLI package exports."""
from ipdpo.cli.analytics_cli import app as analytics_app
from ipdpo.cli.context_cli import app as context_app
from ipdpo.cli.history_cli import app as history_app
from ipdpo.cli.project_cli import app as project_app
from ipdpo.cli.prompt_cli import app as prompt_app
from ipdpo.cli.rag_cli import app as rag_app
from ipdpo.cli.task_cli import app as task_app

__all__ = [
    "analytics_app",
    "context_app",
    "history_app",
    "project_app",
    "prompt_app",
    "rag_app",
    "task_app",
]
