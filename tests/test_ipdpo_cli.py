"""CLI integration tests using Typer CliRunner."""
import tempfile
from pathlib import Path
from typer.testing import CliRunner
import pytest
from ipdpo.main import app
from ipdpo.database.connection import Database

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_isolated_env(tmp_path, monkeypatch):
    """Isolate DB and Active project file for CLI tests."""
    test_db = tmp_path / "cli_test.db"
    test_active = tmp_path / ".test_active"
    test_exports = tmp_path / "cli_exports"

    monkeypatch.setattr("ipdpo.config.DEFAULT_DB_PATH", test_db)
    monkeypatch.setattr("ipdpo.config.ACTIVE_PROJECT_FILE", test_active)
    monkeypatch.setattr("ipdpo.config.DEFAULT_EXPORT_DIR", test_exports)

    # Also patch Database default in all cli modules
    monkeypatch.setattr("ipdpo.database.connection.DEFAULT_DB_PATH", test_db)
    monkeypatch.setattr("ipdpo.core.project_manager.ACTIVE_PROJECT_FILE", test_active)

    # Initialize schema
    db = Database(test_db)
    db.initialize_schema()


def test_cli_project_flow():
    # 1. Create Project
    result = runner.invoke(app, ["project", "create", "--name", "CLITestProject", "--desc", "Test project via CLI"])
    assert result.exit_code == 0
    assert "Project created successfully" in result.stdout

    # 2. List Projects
    list_res = runner.invoke(app, ["project", "list"])
    assert list_res.exit_code == 0
    assert "CLITestProject" in list_res.stdout

    # 3. Status
    status_res = runner.invoke(app, ["project", "status"])
    assert status_res.exit_code == 0
    assert "CLITestProject" in status_res.stdout


def test_cli_context_flow():
    # Setup project first
    runner.invoke(app, ["project", "create", "--name", "ContextTestProject"])

    # Set context
    set_res = runner.invoke(app, ["context", "set", "--category", "technology_stack", "--content", "Python 3.11, Typer, SQLite"])
    assert set_res.exit_code == 0
    assert "successfully saved" in set_res.stdout

    # View context
    view_res = runner.invoke(app, ["context", "view"])
    assert view_res.exit_code == 0
    assert "technology_stack" in view_res.stdout


def test_cli_task_and_analytics_flow():
    runner.invoke(app, ["project", "create", "--name", "TaskAnalyticsProject"])

    # Create Task
    task_res = runner.invoke(app, [
        "task", "create",
        "--type", "debugging",
        "--title", "Fix SQLite deadlock",
        "--desc", "Address transient WAL lock contention under heavy concurrency",
    ])
    assert task_res.exit_code == 0
    assert "created successfully" in task_res.stdout

    # List Tasks
    list_res = runner.invoke(app, ["task", "list"])
    assert list_res.exit_code == 0
    assert "deadlock" in list_res.stdout

    # Analytics Summary
    summary_res = runner.invoke(app, ["analytics", "summary"])
    assert summary_res.exit_code == 0
    assert "Analytics Summary" in summary_res.stdout
