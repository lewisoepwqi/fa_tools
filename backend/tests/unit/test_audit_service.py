from app.services.audit_service import build_audit_event


def test_build_audit_event_contains_before_and_after_snapshots() -> None:
    event = build_audit_event(
        company_id="company-1",
        actor_id="user-1",
        action="template.version.created",
        entity_type="bank_template_version",
        entity_id="version-1",
        before=None,
        after={"version_no": 1},
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert event["action"] == "template.version.created"
    assert event["after_json"] == {"version_no": 1}
