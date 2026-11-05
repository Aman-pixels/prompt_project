"""Analytics and reporting engine using Pandas."""
import sqlite3
from typing import Any, Dict
import pandas as pd
from ipdpo.database.connection import Database


class AnalyticsEngine:
    """Generates analytical metrics, task distributions, and score trends using Pandas."""

    def __init__(self, db: Database):
        self.db = db

    def get_summary_metrics(self, project_id: str) -> Dict[str, Any]:
        """Calculates project-level metrics: prompt count, version count, average score."""
        with self.db.get_connection() as conn:
            prompts_df = pd.read_sql_query(
                "SELECT * FROM prompts WHERE project_id = ?",
                conn,
                params=(project_id,),
            )
            versions_df = pd.read_sql_query(
                """
                SELECT pv.*, p.task_type
                FROM prompt_versions pv
                JOIN prompts p ON pv.prompt_id = p.prompt_id
                WHERE p.project_id = ?
                """,
                conn,
                params=(project_id,),
            )

        if prompts_df.empty:
            return {
                "total_prompts": 0,
                "total_versions": 0,
                "average_score": 0.0,
                "task_distribution": {},
                "score_by_task": {},
            }

        total_prompts = len(prompts_df)
        total_versions = len(versions_df)
        avg_score = round(float(versions_df["quality_score"].mean()), 1) if not versions_df.empty else 0.0

        task_counts = prompts_df["task_type"].value_counts().to_dict()
        score_by_task = (
            versions_df.groupby("task_type")["quality_score"].mean().round(1).to_dict()
            if not versions_df.empty
            else {}
        )

        return {
            "total_prompts": total_prompts,
            "total_versions": total_versions,
            "average_score": avg_score,
            "task_distribution": task_counts,
            "score_by_task": score_by_task,
        }

    def get_global_metrics(self) -> Dict[str, Any]:
        """Computes aggregate analytics across all projects in the database."""
        with self.db.get_connection() as conn:
            projects_df = pd.read_sql_query("SELECT * FROM projects", conn)
            prompts_df = pd.read_sql_query("SELECT * FROM prompts", conn)
            versions_df = pd.read_sql_query("SELECT * FROM prompt_versions", conn)

        total_projects = len(projects_df)
        total_prompts = len(prompts_df)
        total_versions = len(versions_df)
        avg_score = round(float(versions_df["quality_score"].mean()), 1) if not versions_df.empty else 0.0

        method_counts = (
            versions_df["generation_method"].value_counts().to_dict()
            if not versions_df.empty
            else {}
        )

        return {
            "total_projects": total_projects,
            "total_prompts": total_prompts,
            "total_versions": total_versions,
            "overall_average_score": avg_score,
            "generation_methods": method_counts,
        }
