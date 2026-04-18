"""Daily report generation and optional email delivery for live cycler monitoring."""

from __future__ import annotations

import smtplib
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.live import (
    AnomalyEvent,
    AnomalySeverity,
    DailyReportRun,
    DeliveryStatus,
    NotificationTarget,
    NotificationTargetType,
    RunStatus,
    TestRun,
)
from app.services.live_monitor import build_dashboard_payload, utcnow


async def generate_daily_report(
    session: AsyncSession,
    *,
    report_date: Optional[date] = None,
    force: bool = False,
    send_email: bool = True,
) -> DailyReportRun:
    """Build and optionally send the current daily report."""
    tz = ZoneInfo(settings.report_timezone)
    local_now = datetime.now(tz)
    target_date = report_date or local_now.date()

    if not force:
        existing = await session.execute(
            select(DailyReportRun)
            .where(DailyReportRun.report_date == target_date)
            .order_by(DailyReportRun.started_at.desc())
            .limit(1)
        )
        report = existing.scalar_one_or_none()
        if report:
            return report

    payload = await build_report_payload(session, target_date)
    summary_markdown = render_report_markdown(payload)
    email_subject = (
        f"{settings.report_subject_prefix} Daily Battery Report - {target_date.isoformat()}"
    )

    report = DailyReportRun(
        report_date=target_date,
        summary_markdown=summary_markdown,
        summary_json=payload,
        email_subject=email_subject,
        delivery_status=DeliveryStatus.PENDING,
    )
    session.add(report)
    await session.flush()

    recipients = await get_recipients(session, payload.get("project_ids", []))
    report.recipient_count = len(recipients)

    if not send_email:
        report.delivery_status = DeliveryStatus.SKIPPED
        report.error_message = "Email delivery disabled for this run."
    elif not recipients:
        report.delivery_status = DeliveryStatus.SKIPPED
        report.error_message = "No enabled email notification targets were configured."
    elif not settings.smtp_host or not settings.report_sender:
        report.delivery_status = DeliveryStatus.SKIPPED
        report.error_message = "SMTP is not configured; report stored for in-app access only."
    else:
        try:
            send_report_email(email_subject, summary_markdown, recipients)
            report.delivery_status = DeliveryStatus.SENT
        except Exception as exc:  # noqa: BLE001 - surface SMTP errors in DB state
            report.delivery_status = DeliveryStatus.FAILED
            report.error_message = str(exc)

    report.finished_at = utcnow()
    await session.flush()
    return report


async def build_report_payload(session: AsyncSession, report_date: date) -> Dict[str, Any]:
    dashboard = await build_dashboard_payload(session)
    now = utcnow()
    since = now - timedelta(days=1)

    active_runs_result = await session.execute(
        select(TestRun)
        .where(TestRun.status.in_((RunStatus.ACTIVE, RunStatus.STALLED)))
        .order_by(TestRun.updated_at.desc())
    )
    completed_runs_result = await session.execute(
        select(TestRun)
        .where(TestRun.completed_at.is_not(None), TestRun.completed_at >= since)
        .order_by(TestRun.completed_at.desc())
    )
    new_anomalies_result = await session.execute(
        select(AnomalyEvent)
        .where(AnomalyEvent.first_seen_at >= since)
        .order_by(AnomalyEvent.first_seen_at.desc())
    )
    offline_anomalies_result = await session.execute(
        select(AnomalyEvent)
        .where(
            AnomalyEvent.active.is_(True),
            AnomalyEvent.anomaly_type.in_(("stalled_channel", "no_fresh_data", "parser_failure")),
        )
        .order_by(AnomalyEvent.last_seen_at.desc())
    )
    top_runs_result = await session.execute(
        select(TestRun)
        .where(TestRun.capacity_retention_pct.is_not(None))
        .order_by(TestRun.capacity_retention_pct.desc(), TestRun.updated_at.desc())
        .limit(5)
    )

    active_runs = active_runs_result.scalars().all()
    completed_runs = completed_runs_result.scalars().all()
    new_anomalies = new_anomalies_result.scalars().all()
    offline_anomalies = offline_anomalies_result.scalars().all()
    top_runs = top_runs_result.scalars().all()

    project_ids = sorted(
        {
            project_id
            for project_id in [
                *(run.project_id for run in active_runs),
                *(run.project_id for run in completed_runs),
            ]
            if project_id is not None
        }
    )

    return {
        "report_date": report_date.isoformat(),
        "generated_at": now.isoformat(),
        "project_ids": project_ids,
        "dashboard": {
            "generated_at": dashboard["generated_at"].isoformat(),
            "sources": dashboard["sources"],
            "channels": dashboard["channels"],
            "runs": dashboard["runs"],
            "anomalies": dashboard["anomalies"],
        },
        "active_runs": [serialize_run(run) for run in active_runs],
        "completed_runs": [serialize_run(run) for run in completed_runs],
        "new_anomalies": [serialize_anomaly(anomaly) for anomaly in new_anomalies],
        "offline_anomalies": [serialize_anomaly(anomaly) for anomaly in offline_anomalies],
        "top_runs": [serialize_run(run) for run in top_runs],
    }


async def get_recipients(session: AsyncSession, project_ids: Iterable[int]) -> list[str]:
    project_ids = list(project_ids)
    stmt = select(NotificationTarget).where(
        NotificationTarget.enabled.is_(True),
        NotificationTarget.target_type == NotificationTargetType.EMAIL,
    )
    if project_ids:
        stmt = stmt.where(
            or_(
                NotificationTarget.project_id.is_(None),
                NotificationTarget.project_id.in_(project_ids),
            )
        )
    result = await session.execute(stmt.order_by(NotificationTarget.destination.asc()))
    return list(dict.fromkeys(target.destination for target in result.scalars().all()))


def send_report_email(subject: str, body: str, recipients: list[str]) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.report_sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


def render_report_markdown(payload: Dict[str, Any]) -> str:
    """Create a compact workstation-friendly daily report."""
    lines = [
        f"# CellScope Daily Report - {payload['report_date']}",
        "",
        f"Generated at {payload['generated_at']}",
        "",
        "## Status",
        f"- Active runs: {len(payload['active_runs'])}",
        f"- Completed runs (last 24h): {len(payload['completed_runs'])}",
        f"- New anomalies (last 24h): {len(payload['new_anomalies'])}",
        f"- Offline/problem channels: {len(payload['offline_anomalies'])}",
        "",
    ]

    lines.extend(_render_run_section("## Active Runs", payload["active_runs"]))
    lines.extend(_render_run_section("## Completed Runs", payload["completed_runs"]))
    lines.extend(_render_anomaly_section("## New Anomalies", payload["new_anomalies"]))
    lines.extend(_render_anomaly_section("## Offline / Problem Channels", payload["offline_anomalies"]))
    lines.extend(_render_run_section("## Top Performing Runs", payload["top_runs"]))

    if not payload["active_runs"] and not payload["new_anomalies"]:
        lines.extend(
            [
                "## Recommendations",
                "- No urgent actions were detected in the last 24 hours.",
                "- Confirm all active channels are still exporting into the watched folders.",
            ]
        )
    else:
        lines.extend(
            [
                "## Recommendations",
                "- Review any critical or warning anomalies first, especially parser failures and no-fresh-data alerts.",
                "- Confirm completed runs are archived or remapped before the next test starts on those channels.",
                "- Use the dashboard to compare current retention trends against your top performers.",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _render_run_section(title: str, runs: list[Dict[str, Any]]) -> list[str]:
    lines = [title]
    if not runs:
        lines.append("- None")
        lines.append("")
        return lines

    for run in runs:
        summary = run.get("summary_json") or {}
        retention = run.get("capacity_retention_pct")
        retention_text = f"{retention:.1f}%" if retention is not None else "N/A"
        lines.append(
            f"- Run {run['id']} ({summary.get('cell_name', 'Unknown')}): cycle {run.get('last_cycle_index') or 'N/A'}, retention {retention_text}, status {run.get('status')}"
        )
    lines.append("")
    return lines


def _render_anomaly_section(title: str, anomalies: list[Dict[str, Any]]) -> list[str]:
    lines = [title]
    if not anomalies:
        lines.append("- None")
        lines.append("")
        return lines

    for anomaly in anomalies:
        lines.append(
            f"- [{anomaly['severity']}] {anomaly['title']}: {anomaly['description']}"
        )
    lines.append("")
    return lines


def serialize_run(run: TestRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "project_id": run.project_id,
        "experiment_id": run.experiment_id,
        "cell_id": run.cell_id,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "last_cycle_index": run.last_cycle_index,
        "capacity_retention_pct": run.capacity_retention_pct,
        "last_sampled_at": run.last_sampled_at.isoformat() if run.last_sampled_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "summary_json": run.summary_json,
    }


def serialize_anomaly(anomaly: AnomalyEvent) -> Dict[str, Any]:
    return {
        "id": anomaly.id,
        "severity": anomaly.severity.value if hasattr(anomaly.severity, "value") else str(anomaly.severity),
        "anomaly_type": anomaly.anomaly_type,
        "title": anomaly.title,
        "description": anomaly.description,
        "recommendation": anomaly.recommendation,
        "first_seen_at": anomaly.first_seen_at.isoformat() if anomaly.first_seen_at else None,
        "last_seen_at": anomaly.last_seen_at.isoformat() if anomaly.last_seen_at else None,
        "run_id": anomaly.run_id,
        "cell_id": anomaly.cell_id,
        "metadata_json": anomaly.metadata_json,
    }


def next_report_time(now: Optional[datetime] = None) -> datetime:
    """Return the next scheduled daily report time in UTC."""
    tz = ZoneInfo(settings.report_timezone)
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    scheduled = datetime.combine(
        local_now.date(), time(settings.report_hour, settings.report_minute), tzinfo=tz
    )
    if scheduled <= local_now:
        scheduled += timedelta(days=1)
    return scheduled.astimezone(timezone.utc)
