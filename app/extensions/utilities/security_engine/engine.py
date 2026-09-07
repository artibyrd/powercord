"""Evaluation cache and core orchestration engine for the security auditor."""

import logging
from typing import Any, cast

from cachetools import TTLCache  # type: ignore[import-untyped]
from sqlmodel import Session, select

from app.db.models import (
    DiscordAuditorConfig,
    DiscordChannel,
    DiscordRole,
    SecurityAlertOverride,
)
from app.extensions.utilities.security_engine.calculations import (
    compute_alert_hash,
    compute_db_checksum,
    compute_security_health_score,
)
from app.extensions.utilities.security_engine.rules import SECURITY_RULES


class EvaluationCache(TTLCache):
    """TTL cache supporting guild-specific prefix lookups and invalidation."""

    def pop(self, key, default=None):
        try:
            g_id = int(key)
            prefix = f"{g_id}:"
        except (ValueError, TypeError):
            prefix = None

        to_remove = []
        for k in list(self.keys()):
            if k == key:
                to_remove.append(k)
            elif prefix and isinstance(k, str) and k.startswith(prefix):
                to_remove.append(k)

        val = default
        for k in to_remove:
            val = super().pop(k, default)
        return val

    def __contains__(self, key):
        try:
            g_id = int(key)
            prefix = f"{g_id}:"
        except (ValueError, TypeError):
            prefix = None

        for k in list(self.keys()):
            if k == key:
                return True
            if prefix and isinstance(k, str) and k.startswith(prefix):
                return True
        return False

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            try:
                g_id = int(key)
                prefix = f"{g_id}:"
            except (ValueError, TypeError):
                prefix = None

            if prefix:
                for k in list(self.keys()):
                    if isinstance(k, str) and k.startswith(prefix):
                        return super().__getitem__(k)
            raise

    def __delitem__(self, key):
        try:
            super().__delitem__(key)
        except KeyError:
            try:
                g_id = int(key)
                prefix = f"{g_id}:"
            except (ValueError, TypeError):
                prefix = None

            if prefix:
                to_remove = [k for k in list(self.keys()) if isinstance(k, str) and k.startswith(prefix)]
                if to_remove:
                    for k in to_remove:
                        super().__delitem__(k)
                    return
            raise


class SecurityRuleEngine:
    """Security rule engine evaluating guild configurations against registered rules."""

    _evaluation_cache: EvaluationCache = EvaluationCache(maxsize=256, ttl=120)

    def __init__(self):
        self.rules = [rule_cls() for rule_cls in SECURITY_RULES]

    @classmethod
    def invalidate(cls, guild_id: int) -> None:
        """Remove cached evaluation for a guild, if present."""
        try:
            guild_id = int(guild_id)
        except (ValueError, TypeError):
            return
        cls._evaluation_cache.pop(guild_id, None)

    @staticmethod
    def evaluate(guild_id: int, session: Session, include_overridden: bool = False) -> dict:
        """Evaluates security rules for a guild with checksum-keyed caching."""
        guild_id = int(guild_id)

        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        channels = session.exec(select(DiscordChannel).where(DiscordChannel.guild_id == guild_id)).all()
        configs = session.exec(select(DiscordAuditorConfig).where(DiscordAuditorConfig.guild_id == guild_id)).all()
        overrides = session.exec(select(SecurityAlertOverride).where(SecurityAlertOverride.guild_id == guild_id)).all()

        checksum = compute_db_checksum(roles, channels, configs, overrides)

        cache_key = f"{guild_id}:{checksum}:{include_overridden}"
        if cache_key in SecurityRuleEngine._evaluation_cache:
            return cast(dict[str, Any], SecurityRuleEngine._evaluation_cache[cache_key])

        res = SecurityRuleEngine().run_all(guild_id, session, include_overridden=include_overridden)
        SecurityRuleEngine._evaluation_cache[cache_key] = res
        return res

    def _link_parent_alerts(self, alerts: list[dict], session: Session, guild_id: int) -> list[dict]:
        # Query roles to check permissions
        roles = session.exec(select(DiscordRole).where(DiscordRole.guild_id == guild_id)).all()
        admin_roles = {r.name for r in roles if r.permissions & (1 << 3)}
        mention_everyone_roles = {r.name for r in roles if r.permissions & (1 << 17)}

        # Initialize child_count and parent_hash
        for a in alerts:
            a["child_count"] = 0
            a["parent_hash"] = None

        # Identify parents
        parent_map: dict[str, list[dict]] = {}  # role_name -> list of parent alerts
        for a in alerts:
            rule = a.get("rule")
            role_name = a.get("role_name")
            if rule in ("Low-Tier Role Privileges", "Over-privileged Bot Integrations") and role_name:
                parent_map.setdefault(role_name, []).append(a)

        # Link children
        for a in alerts:
            rule = a.get("rule")
            role_name = a.get("role_name")
            if not role_name:
                continue

            potential_parents = parent_map.get(role_name, [])
            for parent in potential_parents:
                # Check Admin link condition
                if (
                    rule
                    in (
                        "Category Permission Baseline",
                        "Public Announcement Protection",
                        "Exposed Staff Channels",
                        "Unauthorized Chat Pings in Non-Text Locations",
                    )
                    and role_name in admin_roles
                ):
                    a["parent_hash"] = parent["alert_hash"]
                    a["parent_rule"] = parent["rule"]
                    parent["child_count"] += 1
                    break

                # Check Mention Everyone link condition
                if (
                    rule == "General Role Mentionability"
                    and parent["rule"] == "Low-Tier Role Privileges"
                    and role_name in mention_everyone_roles
                ):
                    a["parent_hash"] = parent["alert_hash"]
                    a["parent_rule"] = parent["rule"]
                    parent["child_count"] += 1
                    break

        # Reorder so children are grouped under parents
        parent_hashes = {p["alert_hash"] for plist in parent_map.values() for p in plist}
        parent_alerts = [a for a in alerts if a["alert_hash"] in parent_hashes]
        child_alerts_by_parent: dict[str, list[dict]] = {}
        for a in alerts:
            phash = a.get("parent_hash")
            if phash:
                child_alerts_by_parent.setdefault(phash, []).append(a)

        other_alerts = [a for a in alerts if a["alert_hash"] not in parent_hashes and not a.get("parent_hash")]

        ordered_alerts = []
        for parent in parent_alerts:
            ordered_alerts.append(parent)
            children_list = child_alerts_by_parent.get(parent["alert_hash"], [])
            ordered_alerts.extend(children_list)

        ordered_alerts.extend(other_alerts)
        return ordered_alerts

    def run_all(self, guild_id: int, session: Session, include_overridden: bool = False) -> dict:
        alerts = []
        for rule in self.rules:
            try:
                rule_alerts = rule.evaluate(guild_id, session)
                alerts.extend(rule_alerts)
            except Exception as e:
                logging.exception(f"Error evaluating rule {rule.name}: {e}")

        # Compute hash for every alert first
        for alert in alerts:
            ahash = compute_alert_hash(
                alert.get("rule", ""),
                alert.get("category", ""),
                alert.get("message", ""),
            )
            alert["alert_hash"] = ahash

        # Link parent/child alerts
        alerts = self._link_parent_alerts(alerts, session, guild_id)

        # Filter if not include_overridden
        overrides = session.exec(select(SecurityAlertOverride).where(SecurityAlertOverride.guild_id == guild_id)).all()
        override_hashes = {o.alert_hash for o in overrides}

        filtered_alerts = []
        for alert in alerts:
            if include_overridden or alert["alert_hash"] not in override_hashes:
                filtered_alerts.append(alert)

        # Now compute score only on non-overridden alerts!
        num_high = 0
        num_medium = 0
        num_low = 0
        for alert in filtered_alerts:
            if alert["alert_hash"] not in override_hashes:
                # Exclude child alerts from score if their parent is active (not overridden)
                parent_hash = alert.get("parent_hash")
                if parent_hash and parent_hash not in override_hashes:
                    continue

                details = str(alert.get("details", ""))
                if "[INERT" in details:
                    continue
                sev = alert.get("severity", "").lower()
                if sev == "high":
                    num_high += 1
                elif sev == "medium":
                    num_medium += 1
                elif sev == "low":
                    num_low += 1

        score = compute_security_health_score(num_high, num_medium, num_low)

        # Sort keeping parent-child grouping intact
        severity_order = {"high": 0, "medium": 1, "low": 2}
        alert_severities = {al["alert_hash"]: al.get("severity", "").lower() for al in filtered_alerts}

        def sort_key(a):
            phash = a.get("parent_hash")
            if phash and phash in alert_severities:
                group_sev = alert_severities[phash]
                is_child = 1
                parent_key = phash
            else:
                group_sev = a.get("severity", "").lower()
                is_child = 0
                parent_key = a["alert_hash"]
            return (severity_order.get(group_sev, 3), parent_key, is_child)

        filtered_alerts.sort(key=sort_key)
        return {"score": score, "alerts": filtered_alerts}
