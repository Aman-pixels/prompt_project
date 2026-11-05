"""Unit and integration tests for IPDPO."""
import os
import tempfile
from pathlib import Path
import pytest
from ipdpo.core.context_manager import ContextManager, TASK_RELEVANCE_MATRIX
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
from ipdpo.llm.gemini_client import GeminiClient, GeminiRefinementResult
from ipdpo.models.schemas import (
    ContextCategory,
    GenerationMethod,
    ProjectModel,
    ProjectStatus,
    TaskType,
)


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_ipdpo.db"
    db = Database(db_file)
    db.initialize_schema()
    return db


@pytest.fixture
def test_env(temp_db, tmp_path):
    active_file = tmp_path / ".test_active"
    proj_repo = ProjectRepository(temp_db)
    ctx_repo = ContextRepository(temp_db)
    task_repo = TaskRepository(temp_db)
    prompt_repo = PromptRepository(temp_db)
    version_repo = VersionRepository(temp_db)
    log_repo = OptimizationLogRepository(temp_db)

    proj_mgr = ProjectManager(proj_repo, active_file=active_file)
    ctx_mgr = ContextManager(ctx_repo)
    task_mgr = TaskManager(task_repo)
    prompt_engine = PromptEngine()
    evaluator = QualityEvaluator()
    version_mgr = VersionManager(prompt_repo, version_repo, log_repo)
    export_mgr = ExportManager(export_dir=tmp_path / "exports")

    return {
        "db": temp_db,
        "proj_mgr": proj_mgr,
        "ctx_mgr": ctx_mgr,
        "task_mgr": task_mgr,
        "prompt_engine": prompt_engine,
        "evaluator": evaluator,
        "version_mgr": version_mgr,
        "export_mgr": export_mgr,
        "prompt_repo": prompt_repo,
    }


def test_project_crud_and_active_state(test_env):
    mgr = test_env["proj_mgr"]
    proj = mgr.create_project(name="AlphaProject", description="A test system")
    assert proj.project_id is not None
    assert proj.name == "AlphaProject"
    assert mgr.get_active_project_id() == proj.project_id

    # List
    projects = mgr.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "AlphaProject"

    # Update
    updated = mgr.update_project(proj.project_id, description="Updated desc")
    assert updated.description == "Updated desc"

    # Archive
    archived = mgr.archive_project(proj.project_id)
    assert archived.status == ProjectStatus.ARCHIVED

    # Delete
    deleted = mgr.delete_project(proj.project_id)
    assert deleted is True
    assert mgr.get_project(proj.project_id) is None
    assert mgr.get_active_project_id() is None


def test_context_management_and_matrix_filtering(test_env):
    proj_mgr = test_env["proj_mgr"]
    ctx_mgr = test_env["ctx_mgr"]

    proj = proj_mgr.create_project(name="BetaProject")

    # Set context
    ctx_mgr.set_context(
        proj.project_id,
        ContextCategory.TECHNOLOGY_STACK,
        "Python 3.11, FastAPI, PostgreSQL",
    )
    ctx_mgr.set_context(
        proj.project_id,
        ContextCategory.SYSTEM_ARCHITECTURE,
        "Microservices architecture with REST and Kafka",
    )

    all_ctx = ctx_mgr.get_all_context(proj.project_id)
    assert len(all_ctx) == 2
    assert "Python 3.11" in all_ctx["technology_stack"]

    # Relevant context retrieval for Debugging
    relevant = ctx_mgr.get_relevant_context(proj.project_id, TaskType.DEBUGGING)
    assert "technology_stack" in relevant
    assert "system_architecture" in relevant
    assert relevant["technology_stack"] == "Python 3.11, FastAPI, PostgreSQL"

    # Missing context detection
    missing = ctx_mgr.get_missing_categories(proj.project_id, TaskType.DEBUGGING)
    assert "constraints" in missing
    assert "development_progress" in missing


def test_prompt_template_rendering_all_eight_categories(test_env):
    engine = test_env["prompt_engine"]
    context_data = {
        "overview": "Cloud-native payment gateway",
        "technology_stack": "Python 3.11, SQLite, Pydantic",
        "functional_requirements": "Process authorizations and refunds",
        "constraints": "Zero third-party proprietary dependencies",
    }

    for task_type in TaskType:
        rendered = engine.render_prompt(
            task_type=task_type,
            task_description=f"Perform testing and implementation for {task_type.value}",
            context=context_data,
            supplementary_input="class PaymentProcessor: pass",
        )
        assert len(rendered) > 100
        assert "# System Role" in rendered
        assert "# Immediate Task Objective" in rendered


def test_quality_evaluation_rubric(test_env):
    evaluator = test_env["evaluator"]
    context_sample = {
        "technology_stack": "Python 3.11, Typer",
        "constraints": "Do not use GUI frameworks",
    }

    prompt_sample = (
        "# System Role\nSenior Backend Architect.\n\n"
        "# Project Context\nPython 3.11, Typer.\n\n"
        "# Immediate Task Objective\nImplement robust CLI argument parser.\n\n"
        "# Constraints & Rules\nDo not use deprecated libraries.\n\n"
        "# Expected Output Format\nDeliver production-ready Markdown code blocks and unit test tables."
    )

    evaluation = evaluator.evaluate(
        prompt_text=prompt_sample,
        context=context_sample,
        task_type=TaskType.CODE_GENERATION,
        task_description="Implement robust CLI argument parser with comprehensive tests",
        supplementary_input="sample code",
    )

    assert 0.0 <= evaluation.overall_score <= 100.0
    assert evaluation.clarity.score >= 70.0
    assert evaluation.constraint_definition.score >= 50.0
    assert evaluation.output_specification.score >= 50.0


def test_immutable_version_management(test_env):
    proj_mgr = test_env["proj_mgr"]
    evaluator = test_env["evaluator"]
    version_mgr = test_env["version_mgr"]

    proj = proj_mgr.create_project(name="VersionedProject")
    dummy_eval = evaluator.evaluate("Initial draft", {}, TaskType.CODE_GENERATION, "Create module")

    # Create Version 1
    v1 = version_mgr.save_new_prompt(
        project_id=proj.project_id,
        title="Payment Service Prompt",
        task_type=TaskType.CODE_GENERATION,
        prompt_content="Version 1 Draft",
        evaluation=dummy_eval,
        generation_method=GenerationMethod.LOCAL_TEMPLATE,
    )
    assert v1.version_number == 1
    assert v1.prompt_content == "Version 1 Draft"

    # Append Version 2
    v2 = version_mgr.add_version(
        prompt_id=v1.prompt_id,
        prompt_content="Version 2 Refined by Gemini",
        evaluation=dummy_eval,
        generation_method=GenerationMethod.GEMINI_REFINED,
    )
    assert v2.version_number == 2
    assert v2.prompt_content == "Version 2 Refined by Gemini"

    # Verify immutability: v1 is unchanged
    retrieved_v1 = version_mgr.get_version(v1.prompt_id, 1)
    assert retrieved_v1.prompt_content == "Version 1 Draft"

    all_vers = version_mgr.list_versions(v1.prompt_id)
    assert len(all_vers) == 2


def test_export_manager_file_generation(test_env, tmp_path):
    proj_mgr = test_env["proj_mgr"]
    evaluator = test_env["evaluator"]
    version_mgr = test_env["version_mgr"]
    export_mgr = test_env["export_mgr"]
    prompt_repo = test_env["prompt_repo"]

    proj = proj_mgr.create_project(name="ExportProject")
    dummy_eval = evaluator.evaluate("Content", {}, TaskType.DOCUMENTATION, "Doc task")

    v1 = version_mgr.save_new_prompt(
        project_id=proj.project_id,
        title="API Documentation Prompt",
        task_type=TaskType.DOCUMENTATION,
        prompt_content="# API Documentation Guide\nDetails here.",
        evaluation=dummy_eval,
    )
    prompt_obj = prompt_repo.get_by_id(v1.prompt_id)

    # Test Markdown Export
    md_file = export_mgr.export(prompt_obj, v1, format_type="md")
    assert md_file.exists()
    assert md_file.suffix == ".md"
    assert "API Documentation Guide" in md_file.read_text(encoding="utf-8")

    # Test JSON Export
    json_file = export_mgr.export(prompt_obj, v1, format_type="json")
    assert json_file.exists()
    assert json_file.suffix == ".json"
    assert "documentation" in json_file.read_text(encoding="utf-8")

    # Test TXT Export
    txt_file = export_mgr.export(prompt_obj, v1, format_type="txt")
    assert txt_file.exists()
    assert txt_file.suffix == ".txt"


def test_gemini_client_fallback_when_offline():
    client = GeminiClient(api_key="")
    assert client.is_available() is False
    success, res, err, latency = client.refine_prompt("Some draft", "debugging")
    assert success is False
    assert res is None
    assert "GEMINI_API_KEY" in err
