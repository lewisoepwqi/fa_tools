"""审计端点集成测试: 分页信封 + 字段强类型 + limit 上限校验。"""


def test_audit_logs_paged_and_typed(client):
    resp = client.get("/api/audit-logs?limit=5&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 5 and body["offset"] == 0
    # 每条结构符合 AuditLogResponse 的键
    for item in body["items"]:
        assert {"id", "action", "entity_type", "entity_id", "created_at"} <= set(item)


def test_audit_logs_limit_cap(client):
    resp = client.get("/api/audit-logs?limit=9999")
    assert resp.status_code == 422
