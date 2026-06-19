import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.common.alchemy import get_session
from app.db.models import DiscordAuditorConfig
from app.extensions.utilities.widget import SecurityRuleEngine

router = APIRouter()


class AuditorConfigUpdate(BaseModel):
    staff_separator_role_id: Optional[int] = None
    staff_channel_ids: Optional[list[int]] = None
    announcement_channel_ids: Optional[list[int]] = None


@router.get("/api/guild/{guild_id}/audit/score")
async def get_audit_score(guild_id: int, session: Session = Depends(get_session)):
    """Calculates the overall health score and severity counts (high, medium, low)."""
    evaluation = SecurityRuleEngine.evaluate(guild_id, session)
    score = evaluation.get("score", 100)
    alerts = evaluation.get("alerts", [])

    high_count = sum(1 for a in alerts if a.get("severity", "").lower() == "high")
    med_count = sum(1 for a in alerts if a.get("severity", "").lower() == "medium")
    low_count = sum(1 for a in alerts if a.get("severity", "").lower() == "low")

    return {
        "score": score,
        "severities": {
            "high": high_count,
            "medium": med_count,
            "low": low_count,
        },
    }


@router.get("/api/guild/{guild_id}/audit/alerts")
async def get_audit_alerts(
    guild_id: int,
    category: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """Retrieves the security alerts list filterable by an optional category query parameter."""
    evaluation = SecurityRuleEngine.evaluate(guild_id, session)
    alerts = evaluation.get("alerts", [])

    if category:
        alerts = [a for a in alerts if a.get("category", "").lower() == category.lower()]

    return alerts


@router.get("/api/guild/{guild_id}/audit/config")
async def get_auditor_config(guild_id: int, session: Session = Depends(get_session)):
    """Returns the current auditor configuration settings."""
    config = session.get(DiscordAuditorConfig, guild_id)
    if not config:
        return {
            "staff_separator_role_id": None,
            "staff_channel_ids": [],
            "announcement_channel_ids": [],
        }

    try:
        staff_channels = json.loads(config.staff_channel_ids) if config.staff_channel_ids else []
    except Exception:
        staff_channels = []

    try:
        announcement_channels = json.loads(config.announcement_channel_ids) if config.announcement_channel_ids else []
    except Exception:
        announcement_channels = []

    return {
        "staff_separator_role_id": config.staff_separator_role_id,
        "staff_channel_ids": staff_channels,
        "announcement_channel_ids": announcement_channels,
    }


@router.post("/api/guild/{guild_id}/audit/config")
async def update_auditor_config(
    guild_id: int,
    payload: AuditorConfigUpdate,
    session: Session = Depends(get_session),
):
    """Saves configuration parameters and returns the updated configuration."""
    config = session.get(DiscordAuditorConfig, guild_id)
    if not config:
        config = DiscordAuditorConfig(guild_id=guild_id)
        session.add(config)

    # Note: staff_separator_role_id can be set to None or a specific integer
    if "staff_separator_role_id" in payload.model_fields_set:
        config.staff_separator_role_id = payload.staff_separator_role_id

    if payload.staff_channel_ids is not None:
        config.staff_channel_ids = json.dumps(payload.staff_channel_ids)
    if payload.announcement_channel_ids is not None:
        config.announcement_channel_ids = json.dumps(payload.announcement_channel_ids)

    session.add(config)
    session.commit()
    SecurityRuleEngine._evaluation_cache.pop(guild_id, None)
    session.refresh(config)

    try:
        staff_channels = json.loads(config.staff_channel_ids) if config.staff_channel_ids else []
    except Exception:
        staff_channels = []

    try:
        announcement_channels = json.loads(config.announcement_channel_ids) if config.announcement_channel_ids else []
    except Exception:
        announcement_channels = []

    return {
        "staff_separator_role_id": config.staff_separator_role_id,
        "staff_channel_ids": staff_channels,
        "announcement_channel_ids": announcement_channels,
    }
