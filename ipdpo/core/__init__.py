"""Core package exports."""
from ipdpo.core.context_manager import TASK_RELEVANCE_MATRIX, ContextManager
from ipdpo.core.export_manager import ExportManager
from ipdpo.core.project_manager import ProjectManager
from ipdpo.core.prompt_engine import PromptEngine
from ipdpo.core.quality_evaluator import QualityEvaluator
from ipdpo.core.task_manager import TaskManager
from ipdpo.core.version_manager import VersionManager

__all__ = [
    "ContextManager",
    "ExportManager",
    "ProjectManager",
    "PromptEngine",
    "QualityEvaluator",
    "TASK_RELEVANCE_MATRIX",
    "TaskManager",
    "VersionManager",
]
