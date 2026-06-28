"""内置字段覆盖的 CRUD + 关键词 overlay + standard-schema 合并测试。

覆盖：
- upsert/列表/删除恢复
- field_key 必须是内置字段（扩展字段 key 被拒）
- type_override 合法性校验
- standard-schema 返回覆盖后的 label/type/keywords，并标记 overridden
- 覆盖关键词合并进 standard-schema
"""

COMPANY = "company-1"


def _upsert(client, field_key: str, **overrides) -> dict:
    payload = {"company_id": COMPANY, "field_key": field_key}
    payload.update(overrides)
    return client.put(
        f"/api/tools/bank-journal/custom-fields/builtin-overrides/{field_key}",
        json=payload,
    ).json()


def test_upsert_and_list_builtin_override(client) -> None:
    resp = _upsert(client, "transaction_date", label_override="业务日期")
    assert resp["field_key"] == "transaction_date"
    assert resp["label_override"] == "业务日期"

    listed = client.get(
        "/api/tools/bank-journal/custom-fields/builtin-overrides", params={"company_id": COMPANY}
    ).json()
    assert [o["field_key"] for o in listed] == ["transaction_date"]


def test_upsert_rejects_non_builtin_field_key(client) -> None:
    """覆盖 field_key 必须是内置字段，扩展字段 key 被拒（应走 custom-fields API）。"""
    resp = client.put(
        "/api/tools/bank-journal/custom-fields/builtin-overrides/cost_center",
        json={"company_id": COMPANY, "field_key": "cost_center", "label_override": "X"},
    )
    assert resp.status_code == 409


def test_upsert_rejects_invalid_type_override(client) -> None:
    resp = client.put(
        "/api/tools/bank-journal/custom-fields/builtin-overrides/transaction_date",
        json={
            "company_id": COMPANY,
            "field_key": "transaction_date",
            "type_override": "invalid_type",
        },
    )
    assert resp.status_code == 400


def test_upsert_is_idempotent_update(client) -> None:
    """同 field_key 多次 PUT 为 upsert（更新而非重复创建）。"""
    _upsert(client, "summary", label_override="备注1")
    _upsert(client, "summary", label_override="备注2")
    listed = client.get(
        "/api/tools/bank-journal/custom-fields/builtin-overrides", params={"company_id": COMPANY}
    ).json()
    summary_overrides = [o for o in listed if o["field_key"] == "summary"]
    assert len(summary_overrides) == 1
    assert summary_overrides[0]["label_override"] == "备注2"


def test_delete_override_restores_default(client) -> None:
    _upsert(client, "transaction_date", label_override="业务日期")
    resp = client.delete(
        "/api/tools/bank-journal/custom-fields/builtin-overrides/transaction_date",
        params={"company_id": COMPANY},
    )
    assert resp.status_code == 204
    listed = client.get(
        "/api/tools/bank-journal/custom-fields/builtin-overrides", params={"company_id": COMPANY}
    ).json()
    assert listed == []


def test_standard_schema_merges_override(client) -> None:
    """standard-schema 返回覆盖后的 label/type/keywords，并标记 overridden + builtin。"""
    _upsert(
        client,
        "transaction_date",
        label_override="业务日期",
        header_keywords_override=["业务日期"],
        type_override="text",
    )
    schema = client.get(
        "/api/tools/bank-journal/custom-fields/standard-schema", params={"company_id": COMPANY}
    ).json()
    by_key = {f["key"]: f for f in schema["fields"]}
    td = by_key["transaction_date"]
    assert td["builtin"] is True
    assert td["overridden"] is True
    assert td["label"] == "业务日期"
    assert td["type"] == "text"
    # 关键词 union：内置默认 + 覆盖
    assert "业务日期" in td["keywords"]
    assert "交易日期" in td["keywords"]  # 内置默认仍在
    # 未覆盖的内置字段
    assert by_key["summary"]["overridden"] is False
    assert by_key["summary"]["label"] == "摘要"


def test_company_isolation_of_overrides(client) -> None:
    _upsert(client, "transaction_date", label_override="公司A的叫法", )
    schema_b = client.get(
        "/api/tools/bank-journal/custom-fields/standard-schema", params={"company_id": "company-2"}
    ).json()
    by_key = {f["key"]: f for f in schema_b["fields"]}
    # company-2 不受 company-1 覆盖影响
    assert by_key["transaction_date"]["label"] == "交易日期"
    assert by_key["transaction_date"]["overridden"] is False


def test_detect_recognizes_override_keyword(client) -> None:
    """公司给 transaction_date 加关键词'业务日期'后，standard-schema 返回的 keywords 含它。

    验证覆盖写入 → 合并读取链路正确（detect 端到端见 test_standard_schema_merges_override）。
    """
    _upsert(client, "transaction_date", header_keywords_override=["业务日期"])
    schema = client.get(
        "/api/tools/bank-journal/custom-fields/standard-schema", params={"company_id": COMPANY}
    ).json()
    by_key = {f["key"]: f for f in schema["fields"]}
    assert "业务日期" in by_key["transaction_date"]["keywords"]
    assert "交易日期" in by_key["transaction_date"]["keywords"]  # 内置默认仍在
