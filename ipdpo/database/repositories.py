"""Repository implementations for IPDPO entities."""
import json
import sqlite3
from typing import Any, Dict, List, Optional
from ipdpo.database.connection import Database
from ipdpo.models.schemas import (
    ContextCategory,
    ContextSource,
    DevelopmentTaskModel,
    GenerationMethod,
    OptimizationLogModel,
    ProjectContextModel,
    ProjectModel,
    ProjectStatus,
    PromptModel,
    PromptVersionModel,
    TaskStatus,
    TaskType,
    utc_now_iso,
)


class ProjectRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, project: ProjectModel) -> ProjectModel:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.name,
                    project.description,
                    project.status.value,
                    project.created_at,
                    project.updated_at,
                ),
            )
            conn.commit()
        return project

    def get_by_id(self, project_id: str) -> Optional[ProjectModel]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
            if row:
                return ProjectModel(
                    project_id=row["project_id"],
                    name=row["name"],
                    description=row["description"],
                    status=ProjectStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def get_by_name(self, name: str) -> Optional[ProjectModel]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return ProjectModel(
                    project_id=row["project_id"],
                    name=row["name"],
                    description=row["description"],
                    status=ProjectStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def list_all(self, include_archived: bool = True) -> List[Dict[str, Any]]:
        query = """
            SELECT p.*, COUNT(c.context_id) as context_count
            FROM projects p
            LEFT JOIN project_context c ON p.project_id = c.project_id AND c.is_active = 1
        """
        params = []
        if not include_archived:
            query += " WHERE p.status = 'active'"
        query += " GROUP BY p.project_id ORDER BY p.updated_at DESC"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update(self, project_id: str, name: Optional[str] = None, description: Optional[str] = None, status: Optional[ProjectStatus] = None) -> Optional[ProjectModel]:
        project = self.get_by_id(project_id)
        if not project:
            return None

        new_name = name if name is not None else project.name
        new_desc = description if description is not None else project.description
        new_status = status.value if status is not None else project.status.value
        updated_at = utc_now_iso()

        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, status = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (new_name, new_desc, new_status, updated_at, project_id),
            )
            conn.commit()
        return self.get_by_id(project_id)

    def delete(self, project_id: str) -> bool:
        with self.db.get_connection() as conn:
            cur = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()
            return cur.rowcount > 0


class ContextRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, context: ProjectContextModel) -> ProjectContextModel:
        now = utc_now_iso()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO project_context (context_id, project_id, category, content, source, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, category) DO UPDATE SET
                    content = excluded.content,
                    source = excluded.source,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (
                    context.context_id,
                    context.project_id,
                    context.category.value,
                    context.content,
                    context.source.value,
                    1 if context.is_active else 0,
                    context.created_at,
                    now,
                ),
            )
            # Update project updated_at
            conn.execute("UPDATE projects SET updated_at = ? WHERE project_id = ?", (now, context.project_id))
            conn.commit()
        return context

    def get(self, project_id: str, category: ContextCategory) -> Optional[ProjectContextModel]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM project_context WHERE project_id = ? AND category = ?",
                (project_id, category.value),
            ).fetchone()
            if row:
                return ProjectContextModel(
                    context_id=row["context_id"],
                    project_id=row["project_id"],
                    category=ContextCategory(row["category"]),
                    content=row["content"],
                    source=ContextSource(row["source"]),
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def get_all_for_project(self, project_id: str) -> Dict[str, str]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT category, content FROM project_context WHERE project_id = ? AND is_active = 1",
                (project_id,),
            ).fetchall()
            return {row["category"]: row["content"] for row in rows}

    def delete(self, project_id: str, category: ContextCategory) -> bool:
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM project_context WHERE project_id = ? AND category = ?",
                (project_id, category.value),
            )
            conn.commit()
            return cur.rowcount > 0


class TaskRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, task: DevelopmentTaskModel) -> DevelopmentTaskModel:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO development_tasks (task_id, project_id, task_type, title, description, supplementary_input, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.project_id,
                    task.task_type.value,
                    task.title,
                    task.description,
                    task.supplementary_input,
                    task.status.value,
                    task.created_at,
                    task.updated_at,
                ),
            )
            conn.commit()
        return task

    def get_by_id(self, task_id: str) -> Optional[DevelopmentTaskModel]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM development_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row:
                return DevelopmentTaskModel(
                    task_id=row["task_id"],
                    project_id=row["project_id"],
                    task_type=TaskType(row["task_type"]),
                    title=row["title"],
                    description=row["description"],
                    supplementary_input=row["supplementary_input"],
                    status=TaskStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def list_by_project(self, project_id: str) -> List[DevelopmentTaskModel]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM development_tasks WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            return [
                DevelopmentTaskModel(
                    task_id=row["task_id"],
                    project_id=row["project_id"],
                    task_type=TaskType(row["task_type"]),
                    title=row["title"],
                    description=row["description"],
                    supplementary_input=row["supplementary_input"],
                    status=TaskStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]


class PromptRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, prompt: PromptModel) -> PromptModel:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO prompts (prompt_id, project_id, task_id, title, task_type, current_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt.prompt_id,
                    prompt.project_id,
                    prompt.task_id,
                    prompt.title,
                    prompt.task_type.value,
                    prompt.current_version,
                    prompt.created_at,
                    prompt.updated_at,
                ),
            )
            conn.commit()
        return prompt

    def update_version(self, prompt_id: str, new_version: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE prompts SET current_version = ?, updated_at = ? WHERE prompt_id = ?",
                (new_version, utc_now_iso(), prompt_id),
            )
            conn.commit()

    def get_by_id(self, prompt_id: str) -> Optional[PromptModel]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM prompts WHERE prompt_id = ?", (prompt_id,)).fetchone()
            if row:
                return PromptModel(
                    prompt_id=row["prompt_id"],
                    project_id=row["project_id"],
                    task_id=row["task_id"],
                    title=row["title"],
                    task_type=TaskType(row["task_type"]),
                    current_version=row["current_version"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT p.*, pv.quality_score, pv.generation_method
            FROM prompts p
            LEFT JOIN prompt_versions pv ON p.prompt_id = pv.prompt_id AND p.current_version = pv.version_number
            WHERE p.project_id = ?
            ORDER BY p.updated_at DESC
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(query, (project_id,)).fetchall()
            return [dict(row) for row in rows]


class VersionRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, version: PromptVersionModel) -> PromptVersionModel:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO prompt_versions (version_id, prompt_id, version_number, prompt_content, quality_score, score_breakdown, generation_method, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.version_id,
                    version.prompt_id,
                    version.version_number,
                    version.prompt_content,
                    version.quality_score,
                    json.dumps(version.score_breakdown),
                    version.generation_method.value,
                    version.created_at,
                ),
            )
            conn.commit()
        return version

    def get_version(self, prompt_id: str, version_number: int) -> Optional[PromptVersionModel]:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_versions WHERE prompt_id = ? AND version_number = ?",
                (prompt_id, version_number),
            ).fetchone()
            if row:
                return PromptVersionModel(
                    version_id=row["version_id"],
                    prompt_id=row["prompt_id"],
                    version_number=row["version_number"],
                    prompt_content=row["prompt_content"],
                    quality_score=row["quality_score"],
                    score_breakdown=json.loads(row["score_breakdown"]),
                    generation_method=GenerationMethod(row["generation_method"]),
                    created_at=row["created_at"],
                )
        return None

    def list_versions_for_prompt(self, prompt_id: str) -> List[PromptVersionModel]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_versions WHERE prompt_id = ? ORDER BY version_number ASC",
                (prompt_id,),
            ).fetchall()
            return [
                PromptVersionModel(
                    version_id=row["version_id"],
                    prompt_id=row["prompt_id"],
                    version_number=row["version_number"],
                    prompt_content=row["prompt_content"],
                    quality_score=row["quality_score"],
                    score_breakdown=json.loads(row["score_breakdown"]),
                    generation_method=GenerationMethod(row["generation_method"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]


class OptimizationLogRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, log: OptimizationLogModel) -> OptimizationLogModel:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO optimization_logs (log_id, version_id, method, model_name, raw_input_task, refinement_notes, execution_time_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.log_id,
                    log.version_id,
                    log.method,
                    log.model_name,
                    log.raw_input_task,
                    json.dumps(log.refinement_notes or {}),
                    log.execution_time_ms,
                    log.created_at,
                ),
            )
            conn.commit()
        return log
