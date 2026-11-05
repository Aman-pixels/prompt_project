"""Pydantic domain schemas and enums for IPDPO."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ContextCategory(str, Enum):
    OVERVIEW = "overview"
    OBJECTIVES = "objectives"
    FUNCTIONAL_REQUIREMENTS = "functional_requirements"
    NON_FUNCTIONAL_REQUIREMENTS = "non_functional_requirements"
    TECHNOLOGY_STACK = "technology_stack"
    SYSTEM_ARCHITECTURE = "system_architecture"
    DATABASE_DESIGN = "database_design"
    DEVELOPMENT_PROGRESS = "development_progress"
    CONSTRAINTS = "constraints"
    DESIGN_DECISIONS = "design_decisions"


class ContextSource(str, Enum):
    MANUAL = "manual"
    IMPORT_JSON = "import_json"
    IMPORT_YAML = "import_yaml"
    IMPORT_MD = "import_md"


class TaskType(str, Enum):
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    SYSTEM_ARCHITECTURE = "system_architecture"
    DATABASE_DESIGN = "database_design"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    CODE_REVIEW = "code_review"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GenerationMethod(str, Enum):
    LOCAL_TEMPLATE = "local_template"
    GEMINI_REFINED = "gemini_refined"
    USER_EDITED = "user_edited"


# Domain Models

class ProjectModel(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class ProjectContextModel(BaseModel):
    context_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    category: ContextCategory
    content: str
    source: ContextSource = ContextSource.MANUAL
    is_active: bool = True
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class DevelopmentTaskModel(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    task_type: TaskType
    title: str
    description: str
    supplementary_input: Optional[str] = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class DimensionScore(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    weight: float
    findings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class QualityEvaluationResult(BaseModel):
    overall_score: float = Field(ge=0.0, le=100.0)
    clarity: DimensionScore
    context_completeness: DimensionScore
    task_specificity: DimensionScore
    constraint_definition: DimensionScore
    output_specification: DimensionScore
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class PromptModel(BaseModel):
    prompt_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    task_id: Optional[str] = None
    title: str
    task_type: TaskType
    current_version: int = 1
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class PromptVersionModel(BaseModel):
    version_id: str = Field(default_factory=lambda: str(uuid4()))
    prompt_id: str
    version_number: int
    prompt_content: str
    quality_score: float
    score_breakdown: Dict[str, Any]
    generation_method: GenerationMethod = GenerationMethod.LOCAL_TEMPLATE
    created_at: str = Field(default_factory=utc_now_iso)


class OptimizationLogModel(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid4()))
    version_id: str
    method: str
    model_name: Optional[str] = None
    raw_input_task: str
    refinement_notes: Optional[Dict[str, Any]] = None
    execution_time_ms: int = 0
    created_at: str = Field(default_factory=utc_now_iso)
