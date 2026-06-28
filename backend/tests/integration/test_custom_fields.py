"""公司级自定义扩展字段：CRUD + 合并 schema 测试。

覆盖：
- 创建/列表/更新/删除、公司隔离
- 槽位自动分配与占用、唯一性校验、与内置字段冲突拦截
- standard-schema 合并端点返回内置+扩展全集 + 配额
"""


def _create(client, company_id: str = "company-1", **overrides) -> dict:
    payload = {
        "company_id": company_id,
        "field_key": "cost_center",
        "name": "成本中心",
        "data_type": "text",
        "header_keywords": ["成本中心", "部门"],
        "created_by": "user-1",
    }
    payload.update(overrides)
    return client.post("/api/tools/bank-journal/custom-fields", json=payload).json()


def test_create_and_list_custom_field(client) -> None:
    created = _create(client)
    assert created["field_key"] == "cost_center"
    assert created["name"] == "成本中心"
    assert created["data_type"] == "text"
    assert created["slot_key"].startswith("ext_text_")  # 自动分配文本槽
    assert created["header_keywords"] == ["成本中心", "部门"]
    assert created["status"] == "active"

    listed = client.get(
        "/api/tools/bank-journal/custom-fields", params={"company_id": "company-1"}
    ).json()
    assert [c["id"] for c in listed] == [created["id"]]


def test_slot_auto_allocation_per_type(client) -> None:
    """不同类型分配到各自槽位族。"""
    t1 = _create(
        client, field_key="f_text_1", name="文本1", data_type="text", header_keywords=["x1"]
    )
    a1 = _create(
        client, field_key="f_amt_1", name="金额1", data_type="amount", header_keywords=["y1"]
    )
    d1 = _create(
        client, field_key="f_date_1", name="日期1", data_type="date", header_keywords=["z1"]
    )
    assert t1["slot_key"] == "ext_text_1"
    assert a1["slot_key"] == "ext_amount_1"
    assert d1["slot_key"] == "ext_date_1"


def test_company_isolation(client) -> None:
    """公司隔离：不同公司同名/同 key 互不影响。"""
    c1 = _create(client, company_id="company-1", field_key="proj", name="项目")
    c2 = _create(client, company_id="company-2", field_key="proj", name="项目")
    assert c1["id"] != c2["id"]
    listed = client.get(
        "/api/tools/bank-journal/custom-fields", params={"company_id": "company-1"}
    ).json()
    assert [c["id"] for c in listed] == [c1["id"]]


def test_unique_field_key_per_company(client) -> None:
    _create(client, field_key="cost_center", name="成本中心")
    resp = client.post(
        "/api/tools/bank-journal/custom-fields",
        json={
            "company_id": "company-1",
            "field_key": "cost_center",
            "name": "另一名称",
            "data_type": "text",
            "header_keywords": ["x"],
        },
    )
    assert resp.status_code == 409


def test_reject_builtin_field_key(client) -> None:
    resp = client.post(
        "/api/tools/bank-journal/custom-fields",
        json={
            "company_id": "company-1",
            "field_key": "summary",  # 内置字段
            "name": "摘要",
            "data_type": "text",
            "header_keywords": ["x"],
        },
    )
    assert resp.status_code == 409


def test_text_slot_cap_enforced(client) -> None:
    """文本槽 8 个上限：第 9 个返回 409。"""
    for i in range(8):
        _create(
            client,
            field_key=f"f{i}",
            name=f"字段{i}",
            data_type="text",
            header_keywords=[f"k{i}"],
        )
    resp = client.post(
        "/api/tools/bank-journal/custom-fields",
        json={
            "company_id": "company-1",
            "field_key": "f8",
            "name": "字段8",
            "data_type": "text",
            "header_keywords": ["k8"],
        },
    )
    assert resp.status_code == 409


def test_update_custom_field(client) -> None:
    created = _create(client)
    resp = client.patch(
        f"/api/tools/bank-journal/custom-fields/{created['id']}",
        json={"name": "成本中心(改)", "header_keywords": ["成本中心", "中心"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "成本中心(改)"
    assert body["header_keywords"] == ["成本中心", "中心"]


def test_delete_then_field_key_not_reusable(client) -> None:
    """删除后 field_key 历史不可复用（数据安全：避免同 key 跨槽位语义错乱）。

    与方案边界一致：field_key 和 slot_key 删除都不回收。
    重建需用新的 field_key，分配到下一个空闲槽位。
    """
    created = _create(client, field_key="cost_center", name="成本中心")
    assert created["slot_key"] == "ext_text_1"
    resp = client.delete(f"/api/tools/bank-journal/custom-fields/{created['id']}")
    assert resp.status_code == 204
    # 已删除不在列表
    listed = client.get(
        "/api/tools/bank-journal/custom-fields", params={"company_id": "company-1"}
    ).json()
    assert listed == []
    # 同 field_key 不可重建（被软删行的历史占用拦截）
    resp = client.post(
        "/api/tools/bank-journal/custom-fields",
        json={
            "company_id": "company-1",
            "field_key": "cost_center",
            "name": "成本中心",
            "data_type": "text",
            "header_keywords": ["成本中心"],
        },
    )
    assert resp.status_code == 409
    # 换新 field_key 可建，分配到下一个空闲文本槽（ext_text_1 被软删行占用）
    recreated = _create(
        client, field_key="cost_center_v2", name="成本中心", header_keywords=["成本中心"]
    )
    assert recreated["slot_key"] == "ext_text_2"


def test_standard_schema_merges_builtin_and_custom(client) -> None:
    _create(client, field_key="cost_center", name="成本中心", data_type="text",
            header_keywords=["成本中心"])
    schema = client.get(
        "/api/tools/bank-journal/custom-fields/standard-schema",
        params={"company_id": "company-1"},
    ).json()
    keys = {f["key"]: f for f in schema["fields"]}
    # 内置
    assert keys["transaction_date"]["builtin"] is True
    assert keys["transaction_date"]["label"] == "交易日期"
    # 扩展
    assert keys["cost_center"]["builtin"] is False
    assert keys["cost_center"]["label"] == "成本中心"
    assert keys["cost_center"]["type"] == "text"
    # 配额
    assert schema["slot_quota"]["text"] == {"used": 1, "total": 8}
    assert schema["slot_quota"]["amount"] == {"used": 0, "total": 4}
    assert schema["slot_quota"]["date"] == {"used": 0, "total": 2}


def test_delete_blocked_when_referenced_by_mapping(client) -> None:
    """扩展字段被映射方案引用时删除被拦截（保守策略）。"""
    # 1) 建扩展字段
    cf = _create(client, field_key="cost_center", name="成本中心", data_type="text",
                 header_keywords=["成本中心"])
    # 2) 建映射方案，其 mappings_json 引用 cost_center 作为来源
    mapping = client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "引用扩展字段的映射",
            "version": {
                "mappings_json": {"成本中心列": "cost_center"},  # source 引用扩展字段 key
                "created_by": "user-1",
            },
        },
    )
    assert mapping.status_code in (200, 201)
    # 3) 删除扩展字段应被拦截
    resp = client.delete(f"/api/tools/bank-journal/custom-fields/{cf['id']}")
    assert resp.status_code == 409
