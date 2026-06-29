from app.services.audit_service import audit_ctx


class _FakeReq:
    class client:
        host = "1.2.3.4"
    headers = {"user-agent": "pytest"}


class _FakeReqNoClient:
    client = None
    headers = {"user-agent": "test"}


class _FakeReqNoHeaders:
    class client:
        host = "5.6.7.8"
    headers = {}


def test_audit_ctx_extracts():
    ctx = audit_ctx(_FakeReq())
    assert ctx == {"ip_address": "1.2.3.4", "user_agent": "pytest"}


def test_audit_ctx_handles_none_client():
    ctx = audit_ctx(_FakeReqNoClient())
    assert ctx == {"ip_address": None, "user_agent": "test"}


def test_audit_ctx_handles_missing_user_agent():
    ctx = audit_ctx(_FakeReqNoHeaders())
    assert ctx == {"ip_address": "5.6.7.8", "user_agent": None}
