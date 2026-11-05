"""Context management and task-relevance retrieval service."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml
from ipdpo.database.repositories import ContextRepository
from ipdpo.models.schemas import ContextCategory, ContextSource, ProjectContextModel, TaskType

# Deterministic Relevance Matrix: Maps each development task type to relevant context categories
TASK_RELEVANCE_MATRIX: Dict[TaskType, List[ContextCategory]] = {
    TaskType.REQUIREMENTS_ANALYSIS: [
        ContextCategory.OVERVIEW,
        ContextCategory.OBJECTIVES,
        ContextCategory.FUNCTIONAL_REQUIREMENTS,
        ContextCategory.NON_FUNCTIONAL_REQUIREMENTS,
        ContextCategory.CONSTRAINTS,
    ],
    TaskType.SYSTEM_ARCHITECTURE: [
        ContextCategory.OVERVIEW,
        ContextCategory.FUNCTIONAL_REQUIREMENTS,
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.CONSTRAINTS,
        ContextCategory.DESIGN_DECISIONS,
    ],
    TaskType.DATABASE_DESIGN: [
        ContextCategory.FUNCTIONAL_REQUIREMENTS,
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.DATABASE_DESIGN,
        ContextCategory.CONSTRAINTS,
    ],
    TaskType.CODE_GENERATION: [
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.DATABASE_DESIGN,
        ContextCategory.DEVELOPMENT_PROGRESS,
        ContextCategory.CONSTRAINTS,
        ContextCategory.DESIGN_DECISIONS,
    ],
    TaskType.DEBUGGING: [
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.CONSTRAINTS,
        ContextCategory.DEVELOPMENT_PROGRESS,
    ],
    TaskType.TESTING: [
        ContextCategory.FUNCTIONAL_REQUIREMENTS,
        ContextCategory.NON_FUNCTIONAL_REQUIREMENTS,
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.CONSTRAINTS,
    ],
    TaskType.DOCUMENTATION: [
        ContextCategory.OVERVIEW,
        ContextCategory.FUNCTIONAL_REQUIREMENTS,
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.SYSTEM_ARCHITECTURE,
        ContextCategory.DESIGN_DECISIONS,
    ],
    TaskType.CODE_REVIEW: [
        ContextCategory.TECHNOLOGY_STACK,
        ContextCategory.NON_FUNCTIONAL_REQUIREMENTS,
        ContextCategory.CONSTRAINTS,
        ContextCategory.DESIGN_DECISIONS,
    ],
}


class ContextManager:
    """Manages project context storage, validation, imports, and task-relevant filtering."""

    def __init__(self, repo: ContextRepository):
        self.repo = repo

    def set_context(
        self,
        project_id: str,
        category: ContextCategory,
        content: str,
        source: ContextSource = ContextSource.MANUAL,
    ) -> ProjectContextModel:
        clean_content = content.strip()
        if not clean_content:
            raise ValueError(f"Content for category '{category.value}' cannot be empty.")

        context = ProjectContextModel(
            project_id=project_id,
            category=category,
            content=clean_content,
            source=source,
            is_active=True,
        )
        return self.repo.upsert(context)

    def get_context(self, project_id: str, category: ContextCategory) -> Optional[ProjectContextModel]:
        return self.repo.get(project_id, category)

    def get_all_context(self, project_id: str) -> Dict[str, str]:
        return self.repo.get_all_for_project(project_id)

    def delete_context(self, project_id: str, category: ContextCategory) -> bool:
        return self.repo.delete(project_id, category)

    def get_relevant_context(
        self, project_id: str, task_type: TaskType
    ) -> Dict[str, Optional[str]]:
        """
        Retrieves context items designated as relevant for the specific task category.
        Returns a dict mapping category name -> content (or None if missing).
        """
        all_ctx = self.repo.get_all_for_project(project_id)
        relevant_categories = TASK_RELEVANCE_MATRIX.get(task_type, list(ContextCategory))

        result: Dict[str, Optional[str]] = {}
        for cat in relevant_categories:
            result[cat.value] = all_ctx.get(cat.value, None)
        return result

    def get_missing_categories(self, project_id: str, task_type: TaskType) -> List[str]:
        """Returns list of relevant category names that are currently empty or missing."""
        relevant = self.get_relevant_context(project_id, task_type)
        return [cat for cat, content in relevant.items() if not content]

    def import_from_file(self, project_id: str, file_path: Path, category_override: Optional[ContextCategory] = None) -> List[ContextCategory]:
        """
        Imports context from JSON, YAML, or Markdown files.
        If category_override is given, imports entire file content into that category.
        Otherwise, parses file keys that match valid ContextCategory enum values.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        raw_text = path.read_text(encoding="utf-8")
        imported: List[ContextCategory] = []

        if category_override:
            source = ContextSource.IMPORT_MD if path.suffix.lower() == ".md" else (
                ContextSource.IMPORT_JSON if path.suffix.lower() == ".json" else ContextSource.IMPORT_YAML
            )
            self.set_context(project_id, category_override, raw_text, source=source)
            imported.append(category_override)
            return imported

        suffix = path.suffix.lower()
        data: Dict[str, Any] = {}

        if suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(raw_text) or {}
            source = ContextSource.IMPORT_YAML
        elif suffix == ".json":
            data = json.loads(raw_text)
            source = ContextSource.IMPORT_JSON
        else:
            raise ValueError(f"Direct structured mapping requires a .json or .yaml file, or specify a --category override for '{path.name}'.")

        for cat in ContextCategory:
            if cat.value in data and data[cat.value]:
                val = data[cat.value]
                content_str = json.dumps(val, indent=2) if isinstance(val, (dict, list)) else str(val)
                self.set_context(project_id, cat, content_str, source=source)
                imported.append(cat)

        return imported
