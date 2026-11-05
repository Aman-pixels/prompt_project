-- SQLite Schema Definition for IPDPO

PRAGMA foreign_keys = ON;

-- 1. Projects
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);

-- 2. Project Context
CREATE TABLE IF NOT EXISTS project_context (
    context_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'overview', 'objectives', 'functional_requirements', 'non_functional_requirements',
        'technology_stack', 'system_architecture', 'database_design',
        'development_progress', 'constraints', 'design_decisions'
    )),
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'import_json', 'import_yaml', 'import_md')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    UNIQUE (project_id, category)
);

CREATE INDEX IF NOT EXISTS idx_context_project_cat ON project_context(project_id, category);

-- 3. Development Tasks
CREATE TABLE IF NOT EXISTS development_tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_type TEXT NOT NULL CHECK (task_type IN (
        'requirements_analysis', 'system_architecture', 'database_design',
        'code_generation', 'debugging', 'testing', 'documentation', 'code_review'
    )),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    supplementary_input TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON development_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON development_tasks(task_type);

-- 4. Prompts
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT,
    title TEXT NOT NULL,
    task_type TEXT NOT NULL CHECK (task_type IN (
        'requirements_analysis', 'system_architecture', 'database_design',
        'code_generation', 'debugging', 'testing', 'documentation', 'code_review'
    )),
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES development_tasks(task_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_prompts_project ON prompts(project_id);
CREATE INDEX IF NOT EXISTS idx_prompts_task ON prompts(task_id);

-- 5. Prompt Versions (Immutable History)
CREATE TABLE IF NOT EXISTS prompt_versions (
    version_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    prompt_content TEXT NOT NULL,
    quality_score REAL NOT NULL,
    score_breakdown TEXT NOT NULL,
    generation_method TEXT NOT NULL CHECK (generation_method IN ('local_template', 'gemini_refined', 'user_edited')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id) ON DELETE CASCADE,
    UNIQUE (prompt_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_versions_prompt ON prompt_versions(prompt_id);
CREATE INDEX IF NOT EXISTS idx_versions_score ON prompt_versions(quality_score);

-- 6. Optimization Logs
CREATE TABLE IF NOT EXISTS optimization_logs (
    log_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('local_template', 'gemini_refined', 'user_edited', 'deterministic_template', 'gemini_refinement')),
    model_name TEXT,
    raw_input_task TEXT NOT NULL,
    refinement_notes TEXT,
    execution_time_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (version_id) REFERENCES prompt_versions(version_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_opt_logs_version ON optimization_logs(version_id);

-- 7. Local RAG Full-Text Search (SQLite FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
    chunk_id UNINDEXED,
    project_id UNINDEXED,
    source_file UNINDEXED,
    content,
    tokenize='porter unicode61'
);
