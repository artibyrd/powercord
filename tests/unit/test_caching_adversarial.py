from concurrent.futures import ThreadPoolExecutor
from typing import cast

from sqlmodel import Session

from app.db.models import DiscordAuditorConfig, DiscordRole
from app.extensions.utilities.widget import SecurityRuleEngine


def test_cache_key_boundaries(session: Session):
    """Verify that a mix of integer/string keys standardizes correctly

    and does not bypass or poison the cache.
    """
    guild_id = 71000

    # Seed DB
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=71001)
    sep_role = DiscordRole(id=71001, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    session.add_all([config, sep_role])
    session.commit()

    SecurityRuleEngine._evaluation_cache.clear()

    # 1. Evaluate with integer guild_id
    res1 = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # 2. Evaluate with string guild_id - should still hit cache due to int() cast
    res2 = SecurityRuleEngine.evaluate(cast(int, str(guild_id)), session)
    assert res2 == res1
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # 3. Invalidate with the centralized method
    SecurityRuleEngine.invalidate(guild_id)
    assert len(SecurityRuleEngine._evaluation_cache) == 0

    # 4. Invalidate with string key - should also work
    _ = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(SecurityRuleEngine._evaluation_cache) == 1
    SecurityRuleEngine.invalidate(str(guild_id))  # type: ignore[arg-type]
    assert len(SecurityRuleEngine._evaluation_cache) == 0

    # 5. Invalidate with non-numeric string - should not crash
    _ = SecurityRuleEngine.evaluate(guild_id, session)
    SecurityRuleEngine.invalidate("invalid_guild_id")  # type: ignore[arg-type]
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # 6. Invalidate with None - should not crash
    SecurityRuleEngine.invalidate(None)  # type: ignore[arg-type]
    assert len(SecurityRuleEngine._evaluation_cache) == 1


def test_invalidation_isolates_guilds(session: Session):
    """Verify that invalidating one guild does not affect another."""
    guild_a = 81000
    guild_b = 82000
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed guild A
    session.add(DiscordAuditorConfig(guild_id=guild_a, staff_separator_role_id=81001))
    session.add(DiscordRole(id=81001, guild_id=guild_a, name="--- Staff ---", permissions=0, position=5))
    # Seed guild B
    session.add(DiscordAuditorConfig(guild_id=guild_b, staff_separator_role_id=82001))
    session.add(DiscordRole(id=82001, guild_id=guild_b, name="--- Staff ---", permissions=0, position=5))
    session.commit()

    SecurityRuleEngine.evaluate(guild_a, session)
    res_b = SecurityRuleEngine.evaluate(guild_b, session)
    assert len(SecurityRuleEngine._evaluation_cache) == 2

    # Invalidate only guild A
    SecurityRuleEngine.invalidate(guild_a)
    assert len(SecurityRuleEngine._evaluation_cache) == 1
    assert guild_b in SecurityRuleEngine._evaluation_cache

    # Guild B still cached
    res_b2 = SecurityRuleEngine.evaluate(guild_b, session)
    assert res_b2 is res_b  # Same object reference (cache hit)


def test_cache_reflects_db_changes_after_invalidation(session: Session):
    """Verify that after invalidation, re-evaluation picks up DB changes."""
    guild_id = 91000
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed DB with no issues
    config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=91001)
    sep_role = DiscordRole(id=91001, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
    session.add_all([config, sep_role])
    session.commit()

    res1 = SecurityRuleEngine.evaluate(guild_id, session)
    score_before = res1["score"]

    # Add an admin role below the separator (should lower the score)
    low_role = DiscordRole(id=91002, guild_id=guild_id, name="Low Admin", permissions=1 << 3, position=2)
    session.add(low_role)
    session.commit()

    # Without invalidation, cache returns stale result
    res_stale = SecurityRuleEngine.evaluate(guild_id, session)
    assert res_stale["score"] == score_before  # Still cached

    # After invalidation, re-evaluation picks up the change
    SecurityRuleEngine.invalidate(guild_id)
    res_fresh = SecurityRuleEngine.evaluate(guild_id, session)
    assert res_fresh["score"] < score_before  # Lower score due to the new role


def test_concurrent_evaluations(engine):
    """Test that concurrent evaluations do not result in corrupted states

    or crash the cache.
    """
    guild_id = 111000
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed initial DB state using a separate local session
    with Session(engine) as session:
        config = DiscordAuditorConfig(guild_id=guild_id, staff_separator_role_id=111001)
        sep_role = DiscordRole(id=111001, guild_id=guild_id, name="--- Staff ---", permissions=0, position=5)
        session.add_all([config, sep_role])
        session.commit()

    # Define wrapper for concurrency
    def run_evaluate(gid):
        # We need a separate session/connection per thread
        with Session(engine) as thread_session:
            return SecurityRuleEngine.evaluate(gid, thread_session)

    # Trigger concurrent requests
    num_threads = 20
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(run_evaluate, guild_id) for _ in range(num_threads)]
        results = [f.result() for f in futures]

    # Verify all results are identical
    for r in results:
        assert r == results[0]

    # Verify only one cached entry exists
    assert len(SecurityRuleEngine._evaluation_cache) == 1
