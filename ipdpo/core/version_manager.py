"""Prompt version management and audit service."""
from typing import Any, Dict, List, Optional
from ipdpo.database.repositories import OptimizationLogRepository, PromptRepository, VersionRepository
from ipdpo.models.schemas import (
    GenerationMethod,
    OptimizationLogModel,
    PromptModel,
    PromptVersionModel,
    QualityEvaluationResult,
    TaskType,
)


class VersionManager:
    """Manages prompt records, immutable versions, and optimization logs."""

    def __init__(
        self,
        prompt_repo: PromptRepository,
        version_repo: VersionRepository,
        log_repo: OptimizationLogRepository,
    ):
        self.prompt_repo = prompt_repo
        self.version_repo = version_repo
        self.log_repo = log_repo

    def save_new_prompt(
        self,
        project_id: str,
        title: str,
        task_type: TaskType,
        prompt_content: str,
        evaluation: QualityEvaluationResult,
        task_id: Optional[str] = None,
        generation_method: GenerationMethod = GenerationMethod.LOCAL_TEMPLATE,
        raw_input_task: str = "",
        model_name: Optional[str] = None,
        refinement_notes: Optional[Dict[str, Any]] = None,
        execution_time_ms: int = 0,
    ) -> PromptVersionModel:
        """Creates the initial prompt record and version 1."""
        prompt = PromptModel(
            project_id=project_id,
            task_id=task_id,
            title=title.strip(),
            task_type=task_type,
            current_version=1,
        )
        created_prompt = self.prompt_repo.create(prompt)

        version = PromptVersionModel(
            prompt_id=created_prompt.prompt_id,
            version_number=1,
            prompt_content=prompt_content,
            quality_score=evaluation.overall_score,
            score_breakdown=evaluation.model_dump(),
            generation_method=generation_method,
        )
        created_version = self.version_repo.create(version)

        # Log optimization audit record
        opt_log = OptimizationLogModel(
            version_id=created_version.version_id,
            method=generation_method.value,
            model_name=model_name,
            raw_input_task=raw_input_task,
            refinement_notes=refinement_notes,
            execution_time_ms=execution_time_ms,
        )
        self.log_repo.create(opt_log)

        return created_version

    def add_version(
        self,
        prompt_id: str,
        prompt_content: str,
        evaluation: QualityEvaluationResult,
        generation_method: GenerationMethod,
        raw_input_task: str = "",
        model_name: Optional[str] = None,
        refinement_notes: Optional[Dict[str, Any]] = None,
        execution_time_ms: int = 0,
    ) -> PromptVersionModel:
        """Appends a new immutable version to an existing prompt (incrementing version number)."""
        prompt = self.prompt_repo.get_by_id(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt with ID '{prompt_id}' does not exist.")

        next_version = prompt.current_version + 1

        version = PromptVersionModel(
            prompt_id=prompt_id,
            version_number=next_version,
            prompt_content=prompt_content,
            quality_score=evaluation.overall_score,
            score_breakdown=evaluation.model_dump(),
            generation_method=generation_method,
        )
        created_version = self.version_repo.create(version)
        self.prompt_repo.update_version(prompt_id, next_version)

        opt_log = OptimizationLogModel(
            version_id=created_version.version_id,
            method=generation_method.value,
            model_name=model_name,
            raw_input_task=raw_input_task,
            refinement_notes=refinement_notes,
            execution_time_ms=execution_time_ms,
        )
        self.log_repo.create(opt_log)

        return created_version

    def get_version(self, prompt_id: str, version_number: int) -> Optional[PromptVersionModel]:
        return self.version_repo.get_version(prompt_id, version_number)

    def get_latest_version(self, prompt_id: str) -> Optional[PromptVersionModel]:
        prompt = self.prompt_repo.get_by_id(prompt_id)
        if not prompt:
            return None
        return self.version_repo.get_version(prompt_id, prompt.current_version)

    def list_versions(self, prompt_id: str) -> List[PromptVersionModel]:
        return self.version_repo.list_versions_for_prompt(prompt_id)
