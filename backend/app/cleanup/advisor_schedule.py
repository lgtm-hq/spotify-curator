"""Scheduled AI advisor runs and history."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cleanup.suggest_jobs import (
    create_suggest_job,
    get_suggest_job,
    run_suggest_job,
)
from app.cleanup.suggest_options import CleanupSuggestOptions
from app.db import (
    AdvisorScheduleRecord,
    AdvisorScheduleRunRecord,
    UserRecord,
    dumps_json,
    loads_json,
    utcnow,
)
from app.notify import send_advisor_digest_email

logger = logging.getLogger(__name__)

DEFAULT_CRON = "0 9 * * 0"


def get_schedule(db: Session) -> dict[str, Any]:
    """Return the advisor schedule configuration."""
    record = _get_or_create_schedule(db)
    return _schedule_to_dict(record)


def update_schedule(
    db: Session,
    *,
    enabled: bool,
    cron: str,
    options: CleanupSuggestOptions,
    notify_email: bool,
) -> dict[str, Any]:
    """Update advisor schedule settings."""
    record = _get_or_create_schedule(db)
    record.enabled = enabled
    record.cron = cron.strip() or DEFAULT_CRON
    record.options_json = dumps_json(options.model_dump())
    record.notify_email = notify_email
    record.updated_at = utcnow()
    db.commit()
    db.refresh(record)

    from app.scheduler import refresh_advisor_schedule

    refresh_advisor_schedule()
    return _schedule_to_dict(record)


def list_schedule_runs(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent scheduled advisor run history."""
    records = (
        db.query(AdvisorScheduleRunRecord)
        .order_by(AdvisorScheduleRunRecord.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_dict(record) for record in records]


def run_scheduled_advisor() -> None:
    """Execute a scheduled advisor scan if enabled."""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        schedule = _get_or_create_schedule(db)
        if not schedule.enabled:
            logger.info("Advisor schedule disabled; skipping run")
            return

        user = db.get(UserRecord, 1)
        if user is None or not user.spotify_id:
            logger.warning("Advisor schedule skipped: no connected user")
            return

        options = CleanupSuggestOptions.model_validate(
            loads_json(schedule.options_json)
        )
        run_id = str(uuid.uuid4())
        started_at = utcnow()
        run_record = AdvisorScheduleRunRecord(
            id=run_id,
            started_at=started_at,
            status="running",
            triggered_by="schedule",
        )
        db.add(run_record)
        db.commit()

        job = create_suggest_job(options=options)
        run_suggest_job(job.job_id, current_user_id=user.spotify_id)

        finished_job = get_suggest_job(job.job_id)
        completed_at = utcnow()
        if finished_job is None or finished_job.status == "failed":
            error = finished_job.error if finished_job else "Job lost"
            run_record.status = "failed"
            run_record.error = error
            run_record.completed_at = completed_at
            schedule.last_run_status = "failed"
            schedule.last_run_summary = error
        else:
            result = finished_job.result or {}
            summary = str(result.get("summary") or "Advisor run completed.")
            run_record.status = "completed"
            run_record.summary = summary
            run_record.result_json = dumps_json(result)
            run_record.completed_at = completed_at
            schedule.last_run_status = "completed"
            schedule.last_run_summary = summary
            schedule.last_job_id = job.job_id

            if schedule.notify_email and user.email:
                send_advisor_digest_email(
                    to_address=user.email,
                    summary=summary,
                    suggestion_count=len(result.get("suggestions") or []),
                )

        schedule.last_run_at = completed_at
        schedule.updated_at = completed_at
        db.commit()
        logger.info("Scheduled advisor run %s finished: %s", run_id, run_record.status)
    except Exception:
        logger.exception("Scheduled advisor run failed")
    finally:
        db.close()


def _get_or_create_schedule(db: Session) -> AdvisorScheduleRecord:
    record = db.get(AdvisorScheduleRecord, 1)
    if record is None:
        record = AdvisorScheduleRecord(
            id=1,
            enabled=False,
            cron=DEFAULT_CRON,
            options_json=dumps_json(CleanupSuggestOptions().model_dump()),
            notify_email=True,
            updated_at=utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def _schedule_to_dict(record: AdvisorScheduleRecord) -> dict[str, Any]:
    return {
        "enabled": record.enabled,
        "cron": record.cron,
        "options": loads_json(record.options_json),
        "notify_email": record.notify_email,
        "last_run_at": _iso(record.last_run_at),
        "last_run_status": record.last_run_status,
        "last_run_summary": record.last_run_summary,
        "last_job_id": record.last_job_id,
        "updated_at": _iso(record.updated_at),
    }


def _run_to_dict(record: AdvisorScheduleRunRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "started_at": _iso(record.started_at),
        "completed_at": _iso(record.completed_at),
        "status": record.status,
        "summary": record.summary,
        "error": record.error,
        "triggered_by": record.triggered_by,
        "result": loads_json(record.result_json) if record.result_json else None,
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
