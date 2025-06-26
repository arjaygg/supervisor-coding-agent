"""
Static Analysis Celery Tasks

Integration tasks for running static analysis through the task queue system.
Provides async execution of SCC and Semgrep analysis with results storage.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from celery import current_task
from sqlalchemy.orm import Session

from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.db.database import get_db
from supervisor_agent.db import models, schemas, crud
from supervisor_agent.db.enums import TaskStatus
from supervisor_agent.analysis import (
    StaticAnalysisPipeline,
    quick_repository_analysis,
    get_ai_analysis_context,
)
from supervisor_agent.api.websocket import notify_task_update
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def analyze_repository_task(self, repo_path: str, task_id: Optional[int] = None):
    """
    Celery task for complete repository static analysis.

    Args:
        repo_path: Path to repository to analyze
        task_id: Optional task ID for tracking

    Returns:
        Dictionary with analysis results and metadata
    """
    db = next(get_db())
    start_time = datetime.now(timezone.utc)

    try:
        logger.info(f"Starting static analysis for repository: {repo_path}")

        # Update task status if task_id provided
        if task_id:
            update_data = schemas.TaskUpdate(
                status=TaskStatus.IN_PROGRESS, started_at=start_time
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Send real-time update
            asyncio.run(
                notify_task_update(
                    {
                        "id": task_id,
                        "type": "STATIC_ANALYSIS",
                        "status": "IN_PROGRESS",
                        "progress": 10,
                        "message": "Initializing static analysis pipeline",
                        "updated_at": start_time.isoformat(),
                    }
                )
            )

        # Initialize pipeline
        pipeline = StaticAnalysisPipeline()

        # Progress update
        if task_id:
            asyncio.run(
                notify_task_update(
                    {
                        "id": task_id,
                        "status": "IN_PROGRESS",
                        "progress": 25,
                        "message": "Running SCC and Semgrep analysis...",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

        # Run analysis
        result = pipeline.analyze_repository(
            repo_path, include_file_details=True, enable_parallel=True
        )

        # Progress update
        if task_id:
            asyncio.run(
                notify_task_update(
                    {
                        "id": task_id,
                        "status": "IN_PROGRESS",
                        "progress": 75,
                        "message": "Processing analysis results...",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

        # Store results in database
        analysis_data = {
            "repository_path": repo_path,
            "analysis_timestamp": result.analysis_timestamp.isoformat(),
            "pipeline_metrics": {
                "execution_time": result.pipeline_metrics.total_execution_time,
                "files_analyzed": result.pipeline_metrics.files_analyzed,
                "total_findings": result.pipeline_metrics.total_findings,
                "parallel_efficiency": result.pipeline_metrics.parallel_efficiency,
            },
            "unified_insights": {
                "code_quality_score": result.unified_insights.code_quality_score,
                "security_score": result.unified_insights.security_score,
                "maintainability_score": result.unified_insights.maintainability_score,
                "risk_profile": result.unified_insights.risk_profile,
                "technical_debt_count": len(
                    result.unified_insights.technical_debt_indicators
                ),
                "priority_recommendations_count": len(
                    result.unified_insights.priority_recommendations
                ),
            },
            "scc_summary": {
                "total_files": result.scc_result.total_metrics.files,
                "total_lines": result.scc_result.total_metrics.lines,
                "total_complexity": result.scc_result.total_metrics.complexity,
                "primary_languages": result.scc_result.repository_summary[
                    "primary_languages"
                ][:3],
            },
            "semgrep_summary": {
                "total_findings": result.semgrep_result.summary["total_findings"],
                "critical_issues": result.semgrep_result.summary["by_severity"][
                    "ERROR"
                ],
                "warning_issues": result.semgrep_result.summary["by_severity"][
                    "WARNING"
                ],
                "files_with_issues": result.semgrep_result.summary["files_with_issues"],
            },
        }

        # Create analysis record
        if task_id:
            # Store as task session result
            session_data = schemas.TaskSessionCreate(
                task_id=task_id,
                prompt=f"Static analysis of {repo_path}",
                response=json.dumps(analysis_data, indent=2),
                result=analysis_data,
                execution_time_seconds=result.pipeline_metrics.total_execution_time,
            )
            crud.TaskSessionCRUD.create_session(db, session_data)

            # Update task to completed
            update_data = schemas.TaskUpdate(
                status=TaskStatus.COMPLETED, completed_at=datetime.now(timezone.utc)
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Send completion notification
            asyncio.run(
                notify_task_update(
                    {
                        "id": task_id,
                        "type": "STATIC_ANALYSIS",
                        "status": "COMPLETED",
                        "progress": 100,
                        "message": f"Analysis complete: {result.unified_insights.code_quality_score}/100 quality score",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "results": {
                            "quality_score": result.unified_insights.code_quality_score,
                            "security_score": result.unified_insights.security_score,
                            "risk_profile": result.unified_insights.risk_profile,
                            "execution_time": result.pipeline_metrics.total_execution_time,
                        },
                    }
                )
            )

        logger.info(
            f"Static analysis completed for {repo_path}: "
            f"Quality: {result.unified_insights.code_quality_score}/100, "
            f"Security: {result.unified_insights.security_score}/100, "
            f"Risk: {result.unified_insights.risk_profile}"
        )

        return {
            "success": True,
            "repository_path": repo_path,
            "task_id": task_id,
            "analysis_data": analysis_data,
            "unified_json": pipeline.export_unified_json(result),
            "sarif_output": pipeline.export_sarif(result),
        }

    except Exception as e:
        logger.error(f"Static analysis failed for {repo_path}: {str(e)}", exc_info=True)

        # Update task status on failure
        if task_id:
            error_message = f"Static analysis failed: {str(e)}"
            update_data = schemas.TaskUpdate(
                status=TaskStatus.FAILED,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

            # Send failure notification
            asyncio.run(
                notify_task_update(
                    {
                        "id": task_id,
                        "type": "STATIC_ANALYSIS",
                        "status": "FAILED",
                        "error_message": error_message,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying static analysis for {repo_path} (attempt {self.request.retries + 1})"
            )
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {
            "success": False,
            "repository_path": repo_path,
            "task_id": task_id,
            "error": str(e),
        }

    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_files_task(
    self,
    file_paths: List[str],
    base_path: Optional[str] = None,
    task_id: Optional[int] = None,
):
    """
    Celery task for analyzing specific files.

    Args:
        file_paths: List of file paths to analyze
        base_path: Base path for relative file paths
        task_id: Optional task ID for tracking

    Returns:
        Dictionary with analysis results
    """
    db = next(get_db())
    start_time = datetime.now(timezone.utc)

    try:
        logger.info(f"Starting static analysis for {len(file_paths)} files")

        if task_id:
            update_data = schemas.TaskUpdate(
                status=TaskStatus.IN_PROGRESS, started_at=start_time
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

        # Initialize pipeline and analyze files
        pipeline = StaticAnalysisPipeline()
        result = pipeline.analyze_files(file_paths, base_path, enable_parallel=True)

        # Create response data
        analysis_data = {
            "file_paths": file_paths,
            "base_path": base_path,
            "analysis_timestamp": result.analysis_timestamp.isoformat(),
            "metrics": {
                "files_analyzed": len(file_paths),
                "execution_time": result.pipeline_metrics.total_execution_time,
                "total_findings": result.pipeline_metrics.total_findings,
            },
            "insights": {
                "code_quality_score": result.unified_insights.code_quality_score,
                "security_score": result.unified_insights.security_score,
                "risk_profile": result.unified_insights.risk_profile,
            },
        }

        if task_id:
            # Store results
            session_data = schemas.TaskSessionCreate(
                task_id=task_id,
                prompt=f"File analysis: {', '.join(file_paths[:3])}{'...' if len(file_paths) > 3 else ''}",
                response=json.dumps(analysis_data, indent=2),
                result=analysis_data,
                execution_time_seconds=result.pipeline_metrics.total_execution_time,
            )
            crud.TaskSessionCRUD.create_session(db, session_data)

            update_data = schemas.TaskUpdate(
                status=TaskStatus.COMPLETED, completed_at=datetime.now(timezone.utc)
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

        return {"success": True, "analysis_data": analysis_data, "task_id": task_id}

    except Exception as e:
        logger.error(f"File analysis failed: {str(e)}", exc_info=True)

        if task_id:
            update_data = schemas.TaskUpdate(
                status=TaskStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.now(timezone.utc),
            )
            crud.TaskCRUD.update_task(db, task_id, update_data)

        return {"success": False, "error": str(e), "task_id": task_id}

    finally:
        db.close()


@celery_app.task
def quick_analysis_task(repo_path: str):
    """
    Quick analysis task for dashboard/API consumption.

    Args:
        repo_path: Repository path to analyze

    Returns:
        Simplified analysis results
    """
    try:
        logger.info(f"Running quick analysis for {repo_path}")

        result = quick_repository_analysis(repo_path)

        logger.info(
            f"Quick analysis completed: Quality {result['quality_score']}, "
            f"Security {result['security_score']}, Risk {result['risk_profile']}"
        )

        return {"success": True, "repository_path": repo_path, "results": result}

    except Exception as e:
        logger.error(f"Quick analysis failed for {repo_path}: {str(e)}")
        return {"success": False, "repository_path": repo_path, "error": str(e)}


@celery_app.task
def get_ai_context_task(repo_path: str):
    """
    Task to generate AI model context from repository analysis.

    Args:
        repo_path: Repository path to analyze

    Returns:
        AI-ready context data
    """
    try:
        logger.info(f"Generating AI context for {repo_path}")

        context = get_ai_analysis_context(repo_path)

        return {"success": True, "repository_path": repo_path, "ai_context": context}

    except Exception as e:
        logger.error(f"AI context generation failed for {repo_path}: {str(e)}")
        return {"success": False, "repository_path": repo_path, "error": str(e)}


@celery_app.task
def batch_repository_analysis(repo_paths: List[str]):
    """
    Batch analysis task for multiple repositories.

    Args:
        repo_paths: List of repository paths to analyze

    Returns:
        Batch analysis results
    """
    results = []

    try:
        logger.info(f"Starting batch analysis for {len(repo_paths)} repositories")

        for repo_path in repo_paths:
            try:
                result = quick_repository_analysis(repo_path)
                results.append(
                    {"repository_path": repo_path, "success": True, "results": result}
                )
            except Exception as e:
                logger.error(f"Batch analysis failed for {repo_path}: {str(e)}")
                results.append(
                    {"repository_path": repo_path, "success": False, "error": str(e)}
                )

        success_count = sum(1 for r in results if r["success"])
        logger.info(
            f"Batch analysis completed: {success_count}/{len(repo_paths)} successful"
        )

        return {
            "success": True,
            "total_repositories": len(repo_paths),
            "successful_analyses": success_count,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}")
        return {"success": False, "error": str(e), "partial_results": results}


# Scheduled task for repository health monitoring
@celery_app.task
def monitor_repository_health(repo_path: str, threshold_quality_score: int = 70):
    """
    Scheduled task to monitor repository health metrics.

    Args:
        repo_path: Repository to monitor
        threshold_quality_score: Alert threshold for quality score

    Returns:
        Health monitoring results
    """
    try:
        logger.info(f"Monitoring repository health: {repo_path}")

        result = quick_repository_analysis(repo_path)

        # Check for quality threshold alerts
        alerts = []
        if result["quality_score"] < threshold_quality_score:
            alerts.append(
                {
                    "type": "quality_degradation",
                    "message": f"Quality score {result['quality_score']} below threshold {threshold_quality_score}",
                    "severity": "WARNING",
                }
            )

        if result["risk_profile"] in ["HIGH", "CRITICAL"]:
            alerts.append(
                {
                    "type": "high_risk",
                    "message": f"Repository risk level: {result['risk_profile']}",
                    "severity": (
                        "ERROR" if result["risk_profile"] == "CRITICAL" else "WARNING"
                    ),
                }
            )

        if result["total_findings"] > 50:
            alerts.append(
                {
                    "type": "high_finding_count",
                    "message": f"High number of findings: {result['total_findings']}",
                    "severity": "WARNING",
                }
            )

        # Send alerts if any (would integrate with notification system)
        if alerts:
            logger.warning(
                f"Repository health alerts for {repo_path}: {len(alerts)} issues"
            )

        return {
            "success": True,
            "repository_path": repo_path,
            "health_score": result["quality_score"],
            "risk_profile": result["risk_profile"],
            "alerts": alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Repository health monitoring failed for {repo_path}: {str(e)}")
        return {"success": False, "repository_path": repo_path, "error": str(e)}
