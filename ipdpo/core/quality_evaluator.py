"""Heuristic prompt quality evaluation engine."""
import re
from typing import Dict, List, Optional
from ipdpo.models.schemas import DimensionScore, QualityEvaluationResult, TaskType


class QualityEvaluator:
    """
    Evaluates prompts using a transparent heuristic rubric across 5 dimensions:
    Q = 0.25*C + 0.25*K + 0.20*S + 0.15*R + 0.15*O
    """

    def evaluate(
        self,
        prompt_text: str,
        context: Dict[str, Optional[str]],
        task_type: TaskType,
        task_description: str,
        supplementary_input: Optional[str] = None,
    ) -> QualityEvaluationResult:
        c_score = self._score_clarity(prompt_text)
        k_score = self._score_context_completeness(context, task_type)
        s_score = self._score_task_specificity(task_description, supplementary_input)
        r_score = self._score_constraint_definition(prompt_text)
        o_score = self._score_output_specification(prompt_text)

        overall = (
            0.25 * c_score.score
            + 0.25 * k_score.score
            + 0.20 * s_score.score
            + 0.15 * r_score.score
            + 0.15 * o_score.score
        )
        overall = round(max(0.0, min(100.0, overall)), 1)

        weaknesses: List[str] = []
        recommendations: List[str] = []

        for dim_name, dim_obj in [
            ("Clarity", c_score),
            ("Context Completeness", k_score),
            ("Task Specificity", s_score),
            ("Constraint Definition", r_score),
            ("Output Specification", o_score),
        ]:
            if dim_obj.score < 75.0:
                weaknesses.extend([f"[{dim_name}] {w}" for w in dim_obj.findings])
                recommendations.extend([f"[{dim_name}] {s}" for s in dim_obj.suggestions])

        return QualityEvaluationResult(
            overall_score=overall,
            clarity=c_score,
            context_completeness=k_score,
            task_specificity=s_score,
            constraint_definition=r_score,
            output_specification=o_score,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )

    def _score_clarity(self, text: str) -> DimensionScore:
        score = 100.0
        findings = []
        suggestions = []

        # Check for placeholders
        placeholders = re.findall(r"(TODO|<fill>|<insert>|FIXME|\bTBD\b|\bXXX\b)", text, re.IGNORECASE)
        if placeholders:
            score -= min(40.0, len(placeholders) * 10.0)
            findings.append(f"Found placeholder tokens ({', '.join(set(placeholders))}).")
            suggestions.append("Replace all placeholder tokens with explicit specifications.")

        # Check for length and section structuring
        if len(text.strip()) < 150:
            score -= 30.0
            findings.append("Prompt is very brief, lacking necessary introductory framing.")
            suggestions.append("Ensure role definition and engineering background are established.")

        sections = re.findall(r"^#+\s+.+", text, re.MULTILINE)
        if len(sections) < 3:
            score -= 20.0
            findings.append("Prompt lacks clear Markdown section headings.")
            suggestions.append("Organize prompt into distinct logical headers (# Role, # Context, # Tasks).")

        score = max(0.0, min(100.0, score))
        return DimensionScore(score=score, weight=0.25, findings=findings, suggestions=suggestions)

    def _score_context_completeness(
        self, context: Dict[str, Optional[str]], task_type: TaskType
    ) -> DimensionScore:
        findings = []
        suggestions = []

        total_relevant = len(context)
        if total_relevant == 0:
            return DimensionScore(score=100.0, weight=0.25, findings=[], suggestions=[])

        populated_count = sum(1 for v in context.values() if v and v.strip())
        ratio = populated_count / total_relevant
        score = round(ratio * 100.0, 1)

        missing = [k for k, v in context.items() if not v or not v.strip()]
        if missing:
            findings.append(f"Missing {len(missing)} relevant context categories: {', '.join(missing)}.")
            suggestions.append(f"Populate context for: {', '.join(missing)} using 'ipdpo context set'.")

        return DimensionScore(score=score, weight=0.25, findings=findings, suggestions=suggestions)

    def _score_task_specificity(
        self, task_description: str, supplementary_input: Optional[str]
    ) -> DimensionScore:
        score = 50.0
        findings = []
        suggestions = []

        words = len(task_description.strip().split())
        if words < 8:
            score -= 25.0
            findings.append("Task description is very short and lacks concrete details.")
            suggestions.append("Provide a more comprehensive task statement (mention specific components, errors, or files).")
        elif words >= 25:
            score += 25.0

        # Action verbs
        action_verbs = ["design", "implement", "refactor", "debug", "create", "test", "analyze", "audit", "document", "optimize"]
        matched_verbs = [v for v in action_verbs if re.search(rf"\b{v}\b", task_description, re.IGNORECASE)]
        if matched_verbs:
            score += 15.0
        else:
            findings.append("Task description lacks strong actionable verbs.")
            suggestions.append("Use precise engineering verbs (e.g., 'implement', 'debug', 'refactor', 'benchmark').")

        if supplementary_input and len(supplementary_input.strip()) > 20:
            score += 10.0

        score = max(0.0, min(100.0, score))
        return DimensionScore(score=score, weight=0.20, findings=findings, suggestions=suggestions)

    def _score_constraint_definition(self, text: str) -> DimensionScore:
        score = 40.0
        findings = []
        suggestions = []

        constraint_patterns = [
            r"\bdo not\b", r"\bmust not\b", r"\bavoid\b", r"\bprohibit",
            r"\bonly use\b", r"\bstrictly\b", r"\bwithout\b", r"\blimitation\b",
            r"\bconstraints?\b", r"\bboundar(y|ies)\b"
        ]

        matches = sum(1 for p in constraint_patterns if re.search(p, text, re.IGNORECASE))
        if matches >= 3:
            score += 60.0
        elif matches == 2:
            score += 40.0
        elif matches == 1:
            score += 20.0
        else:
            findings.append("Few explicit negative constraints or operational boundaries detected.")
            suggestions.append("Explicitly state what the model MUST NOT do (e.g., forbidden libraries, performance limits).")

        score = max(0.0, min(100.0, score))
        return DimensionScore(score=score, weight=0.15, findings=findings, suggestions=suggestions)

    def _score_output_specification(self, text: str) -> DimensionScore:
        score = 40.0
        findings = []
        suggestions = []

        output_patterns = [
            r"\bmarkdown\b", r"\bmermaid\b", r"\btable\b", r"\bcode block\b",
            r"\bexpected output\b", r"\bformat\b", r"\bdeliverables?\b", r"\bschema\b",
            r"\bstep-by-step\b", r"\bdiff\b"
        ]

        matches = sum(1 for p in output_patterns if re.search(p, text, re.IGNORECASE))
        if matches >= 3:
            score += 60.0
        elif matches == 2:
            score += 40.0
        elif matches == 1:
            score += 20.0
        else:
            findings.append("Output format specification is vague or generic.")
            suggestions.append("Define explicit response deliverables (e.g., Markdown table, code snippet with diff, Mermaid diagram).")

        score = max(0.0, min(100.0, score))
        return DimensionScore(score=score, weight=0.15, findings=findings, suggestions=suggestions)
