"""Development task management service."""
from typing import List, Optional
from ipdpo.database.repositories import TaskRepository
from ipdpo.models.schemas import DevelopmentTaskModel, TaskStatus, TaskType


class TaskManager:
    """Manages development task specifications."""

    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def create_task(
        self,
        project_id: str,
        task_type: TaskType,
        title: str,
        description: str,
        supplementary_input: Optional[str] = None,
    ) -> DevelopmentTaskModel:
        clean_title = title.strip()
        clean_desc = description.strip()
        if not clean_title:
            raise ValueError("Task title cannot be empty.")
        if not clean_desc:
            raise ValueError("Task description cannot be empty.")

        task = DevelopmentTaskModel(
            project_id=project_id,
            task_type=task_type,
            title=clean_title,
            description=clean_desc,
            supplementary_input=supplementary_input.strip() if supplementary_input else "",
            status=TaskStatus.PENDING,
        )
        return self.repo.create(task)

    def get_task(self, task_id: str) -> Optional[DevelopmentTaskModel]:
        return self.repo.get_by_id(task_id)

    def list_tasks(self, project_id: str) -> List[DevelopmentTaskModel]:
        return self.repo.list_by_project(project_id)
