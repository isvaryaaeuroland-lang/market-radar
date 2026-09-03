"""Slack webhook notifier. Silently no-ops if no webhook is configured, so
the pipeline works fine without alerting set up (e.g. during local dev)."""
from __future__ import annotations

import logging

import requests

from ..config import settings
from ..schemas import DiffResult

logger = logging.getLogger(__name__)


def _format_message(domain: str, result: DiffResult) -> str:
    material = [c for c in result.changes if c.classification == "material"]
    lines = [f"*Competitor alert: {domain}*", f"{len(material)} material change(s) detected:"]
    for change in material:
        lines.append(f"• *{change.field}*: {change.before} → {change.after}\n  _{change.reasoning}_")
    return "\n".join(lines)


def notify_material_change(domain: str, result: DiffResult) -> None:
    if not settings.slack_webhook_url:
        logger.info("SLACK_WEBHOOK_URL not set — skipping alert for %s (would have fired).", domain)
        return

    try:
        resp = requests.post(
            settings.slack_webhook_url,
            json={"text": _format_message(domain, result)},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to send Slack alert for %s: %s", domain, exc)
