# 设计:API 健壮性(W2)

> 日期:2026-06-29 · 状态:已通过头脑风暴评审,待用户复核
> 范围:**仅 W2**。前置 W0+W1 已合并(domain 层 + 转换核心重构)。
> 依据:`docs/code-review-2026-06-29.md`(#9 输入校验、N+1、分页、文件检查、审计 schema)。

## 0. 定位

W0+W1 修了财务正确性与解析健壮性;W2 收口**后端 API 契约与性能**:把脏输入从 500 变 422、
消除 N+1、给最大的响应(批次预览行)加分页、补关键索引、修缺文件 500、审计响应 schema 化。
**鉴权/租户隔离/加密属 W3,不在本 spec。**

执行顺序中 W2 在 W0+W1 之后、(W3 ∥ W5)之前。

## 1. 类型化输入契约 → 422(治本 #9)

当前 `ConversionRunCreate.mappings/rules` 是 `list[dict[str, Any]]`,脏输入(缺 `version_id`、
非法 `amount_mode`、未知 mapping type)以 500 暴露。新增 `app/tools/bank_journal/schemas/contracts.py`:

- **`ConditionIn`**:递归 Pydantic 模型,校验 `{all: [ConditionIn]}` / `{any: [ConditionIn]}` /
  `{not: ConditionIn}` / 叶子 `{field: str, op: <Literal 操作符集>, value: Any}`。
  操作符集合对齐 `domain/conditions.py` 已实现的:
  `eq ne contains not_contains contains_any in is_empty gte lte gt lt date_gte date_lte`。
- **`MappingIn`**:按 `type` 字段判别联合:
  - `field`:`{type, target, source: str}`
  - `fixed`:`{type, target, value: Any}`
  - `rule_output`:`{type, target, source: str}`
  - `concat`:`{type, target, sources: list[str], separator: str = ""}`
  - `conditional`:`{type, target, condition: ConditionIn(叶子), then_value, else_value}`
  - `manual`:`{type, target}`
- **`RuleIn`**:`{id: str, version_id: str, priority: int, conditions: ConditionIn,
  actions: list[ActionIn], allow_auto_confirm: bool = False}`。
- **`ActionIn`**:`{field: str, value: Any}`(对齐 `rule_service.apply_rules` 读取的 `action["field"]/["value"]`)。
- `ConversionRunCreate`:`mappings: list[MappingIn]`、`rules: list[RuleIn]`;
  `BankParseConfig.amount_mode: AmountMode`(枚举,非法值 → 422)。

**内部零改动**:`run_conversion` 顶部把校验过的模型 `model_dump()` 回 dict,
喂给现有 domain/service(它们仍按 dict 读 `rule["version_id"]` 等)。

**back-compat 硬约束**:`run_conversion_from_config` 用 DB 版本拼装的 dict 经 `ConversionRunCreate`
构造时会被这些模型校验。模型必须接受**所有现存合法配置形状**;现有集成测试(from_config / full_mvp_flow)
全绿即验证。过严而误拒既有形状 → 放宽模型(`value: Any`、额外字段宽容用 `model_config extra="ignore"` 视情况)。

## 2. 分页(只动真问题,保持不破坏)

- **新增** `GET /api/tools/bank-journal/conversion-runs/{run_id}/preview-rows?limit&offset`,
  返回信封 `Page[JournalPreviewRowData]`(见 §模块)。`limit` 默认 100、上限 500;`offset` 默认 0;
  `total` 为该批次预览行总数。
- 现有 `GET /conversion-runs/{run_id}` 详情端点**保持不变**(继续内联返回全部预览行),
  W5 前端迁移到新端点后再瘦身。
- 扁平 list 端点(批次/模板/规则/映射)分页**留到 W5**(与前端协同),W2 不改其响应形状。

`schemas/pagination.py`:
```python
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```

## 3. 索引 + 迁移

模型加 `index=True`:
- 各 `*_run_id` 外键:`journal_preview_rows.conversion_run_id`、`bank_transactions.conversion_run_id`、
  `conversion_run_files.conversion_run_id`、`conversion_run_rule_versions.conversion_run_id`。
- 各版本表 `(parent_id, version_no)` 复合索引(bank_template_versions / company_journal_template_versions /
  mapping_profile_versions / rule_versions)。
- `bank_transactions.row_hash`(去重历史查询热点)。
- `conversion_runs.company_id`。

新增 Alembic 迁移 `migrations/versions/000X_add_indexes.py`(create_index/drop_index,可逆)。
测试走 `create_all` 自动带索引;迁移供生产 PostgreSQL。

## 4. 消除 N+1

`template_service.list_bank_templates` / `list_journal_templates`、`mapping_profiles` 列表、`rules` 列表
当前对每个父行单独查最新版本。改为**一次查询**:窗口函数
`row_number() over (partition by <parent_fk> order by version_no desc) = 1`,或 group-by max(version_no) 连表。
响应形状不变,纯内部优化;结果须与原实现一致(测试断言同样的最新版本)。

## 5. 文件存在性检查

`run_conversion`(及 `run_conversion_from_config` 复用路径)解析前对每个 source file
`(upload_dir / source.storage_key).exists()`,缺失 → `HTTPException(404)`(对齐 `bank_templates.detect`
的既有写法),取代当前缺文件直接 500。

## 6. 审计响应 schema

`app/api/routes/audit.py` 的 `list_audit_logs` `response_model=list[Any]` → 定义
`app/schemas/audit.py::AuditLogResponse`(字段对齐 `AuditLog` 模型暴露所需列,敏感快照按现状返回——
脱敏与租户过滤属 W3);加可选 `limit`(默认 100、上限 500)/`offset`。
**租户过滤、ip/UA、脱敏属 W3**,不在本 spec。

## 7. 测试策略

- 契约 422:未知 mapping type、缺 `version_id`、非法 `op`、非法 `amount_mode`、`priority` 非整数。
- preview-rows 分页:total 正确、limit/offset 切片正确、越界 offset 返回空 items + 正确 total。
- N+1 优化:列表结果与原实现一致(同样的最新版本);(可选)断言查询次数下降。
- 缺文件 404:source file 记录存在但磁盘缺失 → 404 非 500。
- 审计 schema:返回结构符合 `AuditLogResponse`;分页生效。
- **回归硬约束**:现有 183 后端测试 + 7 前端 e2e 全绿;`run_conversion_from_config` 历史路径不被新契约误拒。

## 8. 模块布局

```
backend/app/tools/bank_journal/
  schemas/
    contracts.py        # 新:ConditionIn / MappingIn(判别联合)/ RuleIn / ActionIn
    pagination.py       # 新:Page[T] 信封
    conversion.py       # 改:ConversionRunCreate 用 contracts 类型;amount_mode 枚举
  routes/
    conversion_runs.py  # 新增 preview-rows 分页子端点
  services/
    conversion_service.py  # run_conversion 顶部 model_dump 契约;文件存在性检查;preview-rows 分页查询
    template_service.py / mapping_service 列表 / rule 列表  # N+1 → 单查询
  models/                # 各表加 index=True
backend/app/schemas/audit.py   # 新:AuditLogResponse
backend/app/api/routes/audit.py# 改:response_model + 分页
backend/migrations/versions/000X_add_indexes.py  # 新:索引迁移
```

## 9. 验收标准

- [ ] 脏 mappings/rules/amount_mode 输入返回 **422**(非 500):未知 type、缺 version_id、非法 op、非法 amount_mode。
- [ ] `run_conversion_from_config` 历史路径与现有用例不受影响(全绿)。
- [ ] 新增 preview-rows 分页端点:items/total/limit/offset 正确;limit 上限 500。
- [ ] 4 个 list 端点消除 N+1,结果与原实现一致。
- [ ] 关键索引在模型与一个可逆 Alembic 迁移中落地。
- [ ] 转换缺磁盘文件返回 404。
- [ ] 审计端点有强类型响应模型 + 分页。
- [ ] 现有 183 后端测试 + 7 e2e 全绿;新增 W2 用例通过。

## 10. 不在本 spec 范围

W3 鉴权/RBAC/租户过滤/字段加密/审计脱敏/SQLite FK pragma · W4 迁移真实执行+契约测试/PG 实测/异步 ·
W5 前端分页接入/扁平 list 分页/动态列。
