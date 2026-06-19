from concurrent.futures import ThreadPoolExecutor
from typing import cast

from sqlmodel import Session

from app.db.models import DiscordAuditorConfig, DiscordChannel, DiscordRole
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

    # Get cached key
    cached_key = list(SecurityRuleEngine._evaluation_cache.keys())[0]
    assert cached_key[0] == guild_id

    # 2. Evaluate with string guild_id - should result in a cache hit and not duplicate key
    res2 = SecurityRuleEngine.evaluate(cast(int, str(guild_id)), session)
    assert res2 == res1
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # 3. Pop with string key - should remove the cached entry (because g_id conversion succeeds)
    SecurityRuleEngine._evaluation_cache.pop(str(guild_id), None)
    assert len(SecurityRuleEngine._evaluation_cache) == 0

    # 4. Evaluate and pop with invalid keys to ensure no crash or incorrect eviction
    _ = SecurityRuleEngine.evaluate(guild_id, session)
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # Pop with non-numeric string - should not remove the entry
    SecurityRuleEngine._evaluation_cache.pop("invalid_guild_id", None)
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # Pop with None - should not remove the entry
    SecurityRuleEngine._evaluation_cache.pop(None, None)
    assert len(SecurityRuleEngine._evaluation_cache) == 1

    # Pop with float (represented as numeric)
    SecurityRuleEngine._evaluation_cache.pop(float(guild_id), None)
    assert len(SecurityRuleEngine._evaluation_cache) == 0


def test_db_hash_changes_discord_role(session: Session):
    """Verify that modifications, deletions, and insertions of DiscordRole

    fields always trigger a cache miss/change in hash.
    """
    guild_id = 81000
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed initial DB state
    role = DiscordRole(
        id=81001,
        guild_id=guild_id,
        name="Standard Role",
        permissions=1024,
        position=1,
        color=123,
        is_hoisted=False,
        is_managed=False,
        is_mentionable=False,
    )
    session.add(role)
    session.commit()

    # Helper function to get the current single key in the cache
    def get_current_key(gid, sess):
        SecurityRuleEngine._evaluation_cache.clear()
        _ = SecurityRuleEngine.evaluate(gid, sess)
        keys = list(SecurityRuleEngine._evaluation_cache.keys())
        assert len(keys) == 1
        return keys[0]

    # Base evaluation
    key_base = get_current_key(guild_id, session)

    # 1. Modify name
    role.name = "Standard Role Modified"
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_base
    key_prev = key_mod

    # 2. Modify permissions
    role.permissions = 2048
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 3. Modify position
    role.position = 2
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 4. Modify color
    role.color = 456
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 5. Modify is_hoisted
    role.is_hoisted = True
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 6. Modify is_managed
    role.is_managed = True
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 7. Modify is_mentionable
    role.is_mentionable = True
    session.add(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 8. Delete role
    session.delete(role)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev


def test_db_hash_changes_discord_channel(session: Session):
    """Verify that modifications, deletions, and insertions of DiscordChannel

    fields always trigger a cache miss/change in hash.
    """
    guild_id = 91000
    SecurityRuleEngine._evaluation_cache.clear()

    # Seed initial DB state
    channel = DiscordChannel(
        id=91001,
        guild_id=guild_id,
        parent_id=None,
        name="general",
        type="text",
        position=0,
        overwrites="{}",
    )
    session.add(channel)
    session.commit()

    # Helper function to get the current single key in the cache
    def get_current_key(gid, sess):
        SecurityRuleEngine._evaluation_cache.clear()
        _ = SecurityRuleEngine.evaluate(gid, sess)
        keys = list(SecurityRuleEngine._evaluation_cache.keys())
        assert len(keys) == 1
        return keys[0]

    # Base evaluation
    key_base = get_current_key(guild_id, session)

    # 1. Modify parent_id
    channel.parent_id = 9999
    session.add(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_base
    key_prev = key_mod

    # 2. Modify name
    channel.name = "general-chat"
    session.add(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 3. Modify type
    channel.type = "voice"
    session.add(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 4. Modify position
    channel.position = 5
    session.add(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 5. Modify overwrites
    channel.overwrites = '{"some_role_id": {"allow": 1024}}'
    session.add(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 6. Delete channel
    session.delete(channel)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev


def test_db_hash_changes_discord_auditor_config(session: Session):
    """Verify that modifications, deletions, and insertions of DiscordAuditorConfig

    fields always trigger a cache miss/change in hash.
    """
    guild_id = 101000
    SecurityRuleEngine._evaluation_cache.clear()

    # Helper function to get the current single key in the cache
    def get_current_key(gid, sess):
        SecurityRuleEngine._evaluation_cache.clear()
        _ = SecurityRuleEngine.evaluate(gid, sess)
        keys = list(SecurityRuleEngine._evaluation_cache.keys())
        assert len(keys) == 1
        return keys[0]

    # Base evaluation (no config)
    key_base = get_current_key(guild_id, session)

    # 1. Insert config
    config = DiscordAuditorConfig(
        guild_id=guild_id,
        staff_separator_role_id=101001,
        staff_channel_ids="[]",
        announcement_channel_ids="[]",
    )
    session.add(config)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_base
    key_prev = key_mod

    # 2. Modify staff_separator_role_id
    config.staff_separator_role_id = 101002
    session.add(config)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 3. Modify staff_channel_ids
    config.staff_channel_ids = "[1, 2]"
    session.add(config)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 4. Modify announcement_channel_ids
    config.announcement_channel_ids = "[3, 4]"
    session.add(config)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev
    key_prev = key_mod

    # 5. Delete config
    session.delete(config)
    session.commit()
    key_mod = get_current_key(guild_id, session)
    assert key_mod != key_prev


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
