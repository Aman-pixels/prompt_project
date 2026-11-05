# Interactive Project Development Prompt Optimizer (IPDPO)

An intermediate-level Python Command-Line Interface (CLI) application and prompt-engineering workbench designed to maintain persistent project context across sessions and generate, evaluate, refine, and export task-specific prompts for software development lifecycles.

---

## 1. Project Objective & Highlights

IPDPO bridges the gap between software engineers and AI coding assistants. Instead of constantly copy-pasting architectural constraints, data schemas, and technology versions into unstructured chat windows, IPDPO serves as an authoritative local context repository and deterministic prompt synthesis engine.

* **Local-First Architecture:** $100\%$ operational offline using embedded SQLite, Jinja2 templates, and transparent heuristic evaluation.
* **Multi-Stage Development Prompts:** Dedicated templates for Requirements Analysis, System Architecture, Database Design, Code Generation, Debugging, Testing, Documentation, and Code Review.
* **Deterministic Relevance Matrix:** Retrieves only the context categories relevant to the specific development task.
* **Hybrid Local RAG Subsystem:** Ingests external source code (`.py`, `.sql`, `.ts`, etc.) and docs (`.md`, `.txt`), splitting them into semantic chunks and indexing them using a hybrid SQLite FTS5 (BM25) and ChromaDB vector engine.
* **Transparent Heuristic Quality Rubric:** Evaluates prompts out of $100$ points across 5 weighted dimensions:
  $$Q = 0.25C + 0.25K + 0.20S + 0.15R + 0.15O$$
* **Gemini LLM Refinement:** Optional semantic ambiguity detection and refinement powered by the official Google GenAI SDK (`google-genai`).
* **Immutable Versioning & Audit Logs:** Every prompt iteration is versioned ($v1, v2, \dots$) with full diffing, scoring history, and export capabilities.
* **Multi-Format Exports & Analytics:** Export to Markdown (`.md`), Plain Text (`.txt`), or structured JSON (`.json`), copy directly to clipboard, and generate Pandas-powered quality reports.

---

## 2. Technology Stack

* **Language:** Python 3.11+
* **CLI Framework:** Typer with Rich (tables, markdown rendering, diff viewer, panels)
* **Data Validation:** Pydantic v2
* **Templating Engine:** Jinja2
* **Persistence:** SQLite 3 (WAL mode, foreign keys enabled)
* **Analytics:** Pandas
* **AI Integration:** Google GenAI Python SDK (`google-genai`)
* **Testing:** pytest, pytest-mock

---

## 3. Project Structure

```
ipdpo/
├── __init__.py
├── config.py                  # Environment & filesystem settings
├── main.py                    # Master Typer CLI entry point
├── cli/                       # Presentation layer
│   ├── __init__.py
│   ├── project_cli.py         # Project lifecycle commands
│   ├── context_cli.py         # Structured context commands
│   ├── task_cli.py            # Development task definitions
│   ├── prompt_cli.py          # Prompt synthesis, review & export
│   ├── history_cli.py         # Version inspection & terminal diffs
│   └── analytics_cli.py       # Pandas-powered summary reports
├── core/                      # Application & domain services
│   ├── __init__.py
│   ├── project_manager.py     # Project business logic
│   ├── context_manager.py     # Context storage & task relevance matrix
│   ├── task_manager.py        # Task CRUD
│   ├── prompt_engine.py       # Jinja2 template assembler
│   ├── quality_evaluator.py   # Heuristic scoring engine (5 dimensions)
│   ├── version_manager.py     # Immutable version control & logs
│   └── export_manager.py      # Markdown/TXT/JSON serializer & clipboard
├── database/                  # Persistence layer
│   ├── __init__.py
│   ├── connection.py          # SQLite connection factory
│   ├── schema.sql             # Relational DDL & indexes
│   └── repositories.py        # Typed SQL repository pattern
├── llm/                       # LLM Adapter layer
│   ├── __init__.py
│   └── gemini_client.py       # google-genai client & offline fallbacks
├── models/                    # Domain schemas
│   ├── __init__.py
│   └── schemas.py             # Pydantic models & enums
├── templates/                 # Task-specific Jinja2 templates
│   ├── requirements_analysis.j2
│   ├── system_architecture.j2
│   ├── database_design.j2
│   ├── code_generation.j2
│   ├── debugging.j2
│   ├── testing.j2
│   ├── documentation.j2
│   └── code_review.j2
└── analytics/                 # Reporting engine
    ├── __init__.py
    └── reports.py             # Pandas aggregations
tests/                         # Automated test suite
├── test_ipdpo_core.py
└── test_ipdpo_cli.py
```

---

## 4. Setup and Installation

### 4.1 Windows (PowerShell)

```powershell
# 1. Clone or navigate to the repository
cd a:\prompt_project

# 2. (Optional) Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
Copy-Item .env.example .env
# Edit .env and insert your GEMINI_API_KEY (optional for LLM refinement)
```

### 4.2 Linux / macOS

```bash
# 1. Navigate to repository
cd prompt_project

# 2. (Optional) Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env to add your GEMINI_API_KEY
```

---

## 5. Usage Guide & Workflows

### 5.1 Project Management
```bash
# Display dashboard
python -m ipdpo.main

# Create a project profile
python -m ipdpo.main project create --name "ECommerceCore" --desc "Distributed commerce platform"

# List all projects
python -m ipdpo.main project list

# Switch active project
python -m ipdpo.main project select ECommerceCore

# Check active project status
python -m ipdpo.main project status
```

### 5.2 Context Management & RAG Subsystem
```bash
# Add technology stack context
python -m ipdpo.main context set --category technology_stack --content "Python 3.11, FastAPI, PostgreSQL, Redis, Docker"

# Add constraints
python -m ipdpo.main context set --category constraints --content "Must not use external SaaS APIs for auth; self-hosted JWT only."

# View all context for the active project
python -m ipdpo.main context view

# Import context from a YAML or JSON file
python -m ipdpo.main context import --file ./specs/architecture.json

# Index project codebase or specifications for semantic retrieval
python -m ipdpo.main rag index --path ./ipdpo

# Query the RAG index directly
python -m ipdpo.main rag query "How does prompt quality evaluation work?"
```

### 5.3 Prompt Generation, Quality Scoring & Refinement
```bash
# Launch prompt generator wizard with RAG semantic augmentation
python -m ipdpo.main prompt generate --type debugging --title "Fix Redis connection leak" --desc "Investigate and resolve connection exhaustion under burst loads" --rag --top-k 3

# The interactive CLI will:
# 1. Automatically retrieve relevant context (tech stack, architecture, constraints)
# 2. Retrieve top-3 semantic code/documentation snippets from the RAG index
# 3. Assemble the prompt via Jinja2
# 4. Score quality out of 100 with actionable tips
# 5. Provide options to Approve, Refine with Gemini, Copy to Clipboard, or Discard.
```

### 5.4 Version Inspection & Diffing
```bash
# List prompt history
python -m ipdpo.main history list

# Inspect versions of a specific prompt
python -m ipdpo.main history versions <prompt_id>

# Diff between v1 and v2 in the terminal
python -m ipdpo.main history diff <prompt_id> --v1 1 --v2 2
```

### 5.5 Exports & Analytics
```bash
# Export prompt to Markdown, TXT, or JSON
python -m ipdpo.main prompt export <prompt_id> --format md
python -m ipdpo.main prompt export <prompt_id> --format json

# Project analytics summary
python -m ipdpo.main analytics summary

# Global workbench metrics across all projects
python -m ipdpo.main analytics global
```

---

## 6. Running Tests

Execute the complete automated test suite covering repositories, templates, rubric calculations, offline fallbacks, and CLI flows:

```bash
pytest -v
```
