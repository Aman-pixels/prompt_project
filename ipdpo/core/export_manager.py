"""Export manager for generating Markdown, TXT, and JSON files and clipboard operations."""
import json
from pathlib import Path
from typing import Any, Dict, Optional
import pyperclip
from ipdpo.config import DEFAULT_EXPORT_DIR
from ipdpo.models.schemas import PromptModel, PromptVersionModel


class ExportManager:
    """Handles serialization of prompts to disk and system clipboard."""

    def __init__(self, export_dir: Path = DEFAULT_EXPORT_DIR):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        prompt: PromptModel,
        version: PromptVersionModel,
        format_type: str = "md",
        output_dir: Optional[Path] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> Path:
        target_dir = Path(output_dir) if output_dir else self.export_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in prompt.title).strip("_")
        base_name = f"{prompt.task_type.value}_{safe_title}_v{version.version_number}"
        fmt = format_type.lower().strip()

        if fmt == "md" or fmt == "markdown":
            file_path = target_dir / f"{base_name}.md"
            content = (
                f"<!-- IPDPO Generated Prompt -->\n"
                f"<!-- Title: {prompt.title} | Version: {version.version_number} | Score: {version.quality_score}/100 -->\n\n"
                f"{version.prompt_content}\n"
            )
            file_path.write_text(content, encoding="utf-8")
            return file_path

        elif fmt == "txt":
            file_path = target_dir / f"{base_name}.txt"
            file_path.write_text(version.prompt_content, encoding="utf-8")
            return file_path

        elif fmt == "json":
            file_path = target_dir / f"{base_name}.json"
            payload = {
                "prompt_id": prompt.prompt_id,
                "project_id": prompt.project_id,
                "title": prompt.title,
                "task_type": prompt.task_type.value,
                "version_number": version.version_number,
                "generation_method": version.generation_method.value,
                "quality_score": version.quality_score,
                "score_breakdown": version.score_breakdown,
                "created_at": version.created_at,
                "prompt_content": version.prompt_content,
                "context_snapshot": context_data or {},
            }
            file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return file_path

        else:
            raise ValueError(f"Unsupported export format '{format_type}'. Must be 'md', 'txt', or 'json'.")

    def copy_to_clipboard(self, text: str) -> bool:
        """Copies text to system clipboard. Returns True on success, False if unsupported."""
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False
