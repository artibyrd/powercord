import subprocess
import sys

# Get all test names
all_tests = [
    "test_category_permission_baseline",
    "test_category_permission_baseline_fully_synced",
    "test_category_permission_baseline_details_formatting",
    "test_public_announcement_protection",
    "test_announcement_admin_bypass",
    "test_public_announcement_no_alert_when_view_channel_denied",
    "test_public_announcement_no_alert_when_category_denies_view",
    "test_public_announcement_alert_when_view_channel_allowed",
    "test_exposed_staff_channels",
    "test_exposed_staff_channels_non_staff_role_and_sync",
    "test_unauthorized_chat_pings",
    "test_unauthorized_chat_pings_admin_bypass",
    "test_unauthorized_chat_pings_no_alert_when_view_channel_denied",
    "test_unauthorized_chat_pings_category_inheritance",
    "test_low_tier_role_privileges",
    "test_general_role_mentionability",
    "test_suggestive_honeypot_integration",
    "test_over_privileged_bot_integrations",
    "test_security_rule_engine",
    "test_security_rule_engine_evaluate_caching",
    "test_category_baseline_inert_leak_annotation",
]

target = "test_category_baseline_active_leak_not_annotated"

env = {
    **subprocess.os.environ,
    "POWERCORD_POSTGRES_PASSWORD": "OBPwDbD7zUFZw2YhL4h6zyR",
    "POWERCORD_POSTGRES_USER": "powercord",
    "POWERCORD_POSTGRES_DB": "powercord_test",
    "POWERCORD_DB_HOST": "localhost:5433",
}

for t in all_tests:
    cmd = ["poetry", "run", "pytest", "tests/unit/test_security_rules.py", "-k", f"{t} or {target}"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if "1 failed" in res.stdout or "errors" in res.stdout:
        print(f"FAILED when running {t} followed by {target}!")
        print(res.stdout)
        sys.exit(1)
    else:
        print(f"Passed: {t} + {target}")

print("All individual pairs passed!")
