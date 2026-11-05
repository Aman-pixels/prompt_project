"""Project management service."""
from pathlib import Path
from typing import Any, Dict, List, Optional
from ipdpo.config import ACTIVE_PROJECT_FILE
from ipdpo.database.repositories import ProjectRepository
from ipdpo.models.schemas import ProjectModel, ProjectStatus


class ProjectManager:
    """Coordinates project lifecycle and active session state."""

    def __init__(self, repo: ProjectRepository, active_file: Path = ACTIVE_PROJECT_FILE):
        self.repo = repo
        self.active_file = active_file

    def create_project(self, name: str, description: str = "") -> ProjectModel:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name cannot be empty.")
        existing = self.repo.get_by_name(clean_name)
        if existing:
            raise ValueError(f"Project with name '{clean_name}' already exists.")

        project = ProjectModel(name=clean_name, description=description.strip())
        created = self.repo.create(project)
        self.set_active_project(created.project_id)
        return created

    def list_projects(self, include_archived: bool = True) -> List[Dict[str, Any]]:
        return self.repo.list_all(include_archived=include_archived)

    def get_project(self, project_id: str) -> Optional[ProjectModel]:
        return self.repo.get_by_id(project_id)

    def get_project_by_name(self, name: str) -> Optional[ProjectModel]:
        return self.repo.get_by_name(name.strip())

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[ProjectStatus] = None,
    ) -> Optional[ProjectModel]:
        return self.repo.update(project_id, name=name, description=description, status=status)

    def archive_project(self, project_id: str) -> Optional[ProjectModel]:
        return self.repo.update(project_id, status=ProjectStatus.ARCHIVED)

    def delete_project(self, project_id: str) -> bool:
        active_id = self.get_active_project_id()
        if active_id == project_id and self.active_file.exists():
            self.active_file.unlink()
        return self.repo.delete(project_id)

    def set_active_project(self, project_id: str) -> None:
        proj = self.repo.get_by_id(project_id)
        if not proj:
            raise ValueError(f"Project with ID '{project_id}' does not exist.")
        self.active_file.parent.mkdir(parents=True, exist_ok=True)
        self.active_file.write_text(project_id, encoding="utf-8")

    def get_active_project_id(self) -> Optional[str]:
        if self.active_file.exists():
            content = self.active_file.read_text(encoding="utf-8").strip()
            if content:
                # verify it still exists in DB
                if self.repo.get_by_id(content):
                    return content
        return None

    def get_active_project(self) -> Optional[ProjectModel]:
        active_id = self.get_active_project_id()
        if active_id:
            return self.repo.get_by_id(active_id)
        return None
