"""Prompt construction engine using task-specific Jinja2 templates."""
from pathlib import Path
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ipdpo.models.schemas import TaskType

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class PromptEngine:
    """Renders deterministic, task-specific prompts from context and task descriptions."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_prompt(
        self,
        task_type: TaskType,
        task_description: str,
        context: Dict[str, Optional[str]],
        supplementary_input: Optional[str] = None,
    ) -> str:
        """
        Renders the task-specific Jinja2 template with provided context and user task details.
        """
        template_name = f"{task_type.value}.j2"
        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            raise FileNotFoundError(
                f"Prompt template '{template_name}' not found in {self.templates_dir}: {e}"
            )

        # Format context including any dynamic RAG retrieved snippets
        enriched_context = dict(context)
        if "rag_snippets" in context and context["rag_snippets"]:
            # Append RAG excerpts under project context
            rag_header = "\n### Semantically Retrieved Project Snippets (RAG):\n"
            rag_body = "\n".join([f"- {s}" for s in context["rag_snippets"]])
            existing_overview = enriched_context.get("overview") or ""
            enriched_context["overview"] = f"{existing_overview}\n{rag_header}{rag_body}".strip()

        rendered = template.render(
            task_type=task_type.value,
            task_description=task_description.strip(),
            context=enriched_context,
            supplementary_input=supplementary_input.strip() if supplementary_input else "",
        )
        return rendered.strip()
