# PRD 合规差距分析（Gap Analysis）

> 生成时间：2026-06-27
> 对照文档：`prd-bank-statement-journal.md`（产品需求）、`technical-design-bank-statement-journal.md`（技术设计）、`mvp-acceptance-checklist.md`（验收清单）、`handover.md`（交接说明）
> 核查方式：逐条 grep + 引用代码行号验证（3 个并行审计覆盖后端引擎 / 导出确认 / 认证版本化前端三个领域）
> 结论：当前实现 = PRD 的"最小可跑通骨架"，离 MVP 验收标准仍有系统性缺口

---

## 0. 阅读说明

- **严重级别**：P0 = 直接违反 MVP 验收标准；P1 = PRD §6/§9 明确要求但未实现；P2 = PRD §7/§6.10/§9 的支撑能力缺口。
- **现状证据**：所有断言均附 `文件:行号`，可逐一核对。
- **性质澄清**：部分缺口已被 `handover.md` §11 / 验收清单"已知后续项"**显式记录为非 MVP**（认证 / PostgreSQL 实测 / 账号加密 / 异步任务等）；另一部分是**验收清单标 [x] 但实际未真正满足**（导出 only_confirmed / 处理报告 / 版本快照追溯等）——后者为**真缺口**，建议优先处理。下文每条均标注其性质。
- **截至本文件生成时**，已完成「处理批次与模板规则的列表+详情」补齐（50 测试绿、前端可构建、端到端真实数据验证通过）。本文件聚焦**仍未满足**的部分。

---

## 1. 一句话现状

后端引擎、版本化编辑、人工确认闭环、导出报告、认证权限均有明确未满足项；前端管理页基本是"只读查看器"，关键交互页缺失。模板/映射/规则的**编辑功能前后端均为零实现**。

---

## 2. 🔴 P0 — 直接违反 MVP 验收标准的缺口（建议优先）

### P0-1. 版本化只读：无法创建新版本（"编辑"功能完全缺失）

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.2 "修改模板时创建新版本"、验收 §10.1.3 "历史批次能查看当时使用的模板版本"、技术设计 §8.1 |
| 现状 | 4 个版本化实体（银行模板 / 日记账模板 / 映射 / 规则）**均无 `POST /{id}/versions` 端点**。所有 `create_*` 永远写 `version_no=1`，全代码库无 `version_no=2` 的代码路径。唯一 `PATCH` 在 `preview_rows`（流水行字段修改，与模板无关）。 |
| 证据 | `app/api/routes/bank_templates.py`、`journal_templates.py`、`mapping_profiles.py`、`rules.py` 各仅有 POST/GET/GET；`create_*` 写 `version_no=1` |
| 性质 | **真缺口**（验收 §10.1 隐含要求） |

### P0-2. 转换批次不快照模板/映射版本

| 项 | 内容 |
|---|---|
| PRD 依据 | 验收 §10.3.3 "任意导出文件可查看使用的模板、映射、规则版本"、技术设计 §8.2 批次快照 |
| 现状 | `ConversionRun` 的 3 个版本 FK 列（`bank_template_version_id` / `company_journal_template_version_id` / `mapping_profile_version_id`）**永远为 NULL**。`run_conversion` 把配置（parse_config/mappings/rules）内联在请求体里，不引用已保存版本。 |
| 证据 | `app/models/conversion.py:37-45` 列存在；`app/services/conversion_service.py:79-86` 构造 `ConversionRun` 时未赋值这 3 列 |
| 性质 | **真缺口**（验收 §10.3.3） |
| 注 | 规则版本经 `conversion_run_rule_versions` 表快照（但指向客户端自报 id 如 `rule-version-1`，未校验）。 |

### P0-3. `only_confirmed` 导出选项无效

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.9.5 "可选择仅导出已确认记录" |
| 现状 | 字段被接收并存库（`export.py:11` / `exports.py:49`），但导出时**直接写客户端传来的 rows，不查库、不过滤 status**——开关形同虚设。 |
| 证据 | `app/api/routes/exports.py:42-52` 写 `payload.rows` 原样，从不引用 `JournalPreviewRow` 表 |
| 性质 | **真缺口**（验收清单 Export 已标 [x]，但功能未真正生效） |

### P0-4. 无处理报告

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.9.7 "同时生成处理报告"、§6.9 列 11 项报告字段（批次号/上传文件/模板版本/映射版本/规则版本/总行数/成功行数/自动确认行数/人工确认行数/异常行数/导出人时间） |
| 现状 | `Export.report_storage_key` 列**从未被赋值**，无任何报告生成逻辑。 |
| 证据 | 全仓库 grep `report_storage_key` 仅命中 model + migration，无赋值 |
| 性质 | **真缺口**（PRD 明确要求） |

### P0-5. 导出不校验必填字段

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.9.4 "必填字段完整" |
| 现状 | 导出 writer 逐字段写出，无完整性校验。 |
| 证据 | `app/services/export_service.py` 两个 writer 均无 required 字段检查 |
| 性质 | **真缺口**（PRD 明确要求） |

### P0-6. 人工确认/修改前端完全不可达

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.7 预览与人工确认、验收 §10.4 |
| 现状 | 后端 `PATCH /api/preview-rows/{id}` 与 `POST /api/preview-rows/{id}/confirm` **已实现**，但前端**无任何调用方**（`frontend/src/api/` 无对应函数，批次详情页无确认/编辑按钮）。确认闭环在 UI 上断裂。 |
| 证据 | `frontend/src/api/` 仅 conversionRuns/files/bankTemplates/journalTemplates/mappingProfiles/rules，无 previewRows；`ConversionRunDetailPage.tsx` 无确认按钮 |
| 性质 | **真缺口**（验收 §10.4.1/§10.4.2） |

---

## 3. 🟠 P1 — 引擎 / 检测能力缺口（PRD §6.6 / §6.8 / §9 明确要求）

### P1-1. 异常码 12 个只产出 3 个

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.8 列 10 类异常、技术设计 §10 定义 12 个异常码 |
| 现状 | 仅 `MISSING_REQUIRED_FIELD` / `RULE_CONFLICT` / `NO_RULE_MATCH` 产出。其余 9 个（`INVALID_DATE` / `INVALID_AMOUNT` / `AMOUNT_DIRECTION_MISMATCH` / `UNKNOWN_DIRECTION` / `DUPLICATE_IN_BATCH` / `DUPLICATE_HISTORY` / `BALANCE_DISCONTINUITY` / `TEMPLATE_NOT_MATCHED` / `UNSUPPORTED_FILE_TYPE`）**定义了但代码从不产出**。 |
| 致命问题 | 解析层错误（日期/金额/方向）**直接 `raise ValueError` 中断整个批次**，而非标记单行异常 → 与 PRD §6.8 "逐行识别异常" 设计相悖 |
| 证据 | `app/core/enums.py:37-49` 定义；`parser_service.py:240/266/205/156` raise；grep 全 app/ 仅 3 处 emit |
| 性质 | **真缺口** |

### P1-2. 金额模式 4 种只实现 1 种

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.2.10、技术设计 §9.2 |
| 现状 | 仅 `income_expense_columns` 工作，其余 3 种（`single_amount_with_direction` / `debit_credit_columns` / `signed_amount`）`raise ValueError`。 |
| 证据 | `app/services/parser_service.py:193-194` |
| 性质 | **真缺口** |

### P1-3. 去重与余额连续性全缺

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.8.8 疑似重复流水、§6.8.9 余额连续性异常、技术设计 §9.4 |
| 现状 | `bank_transactions.row_hash` 列**永远为空**；无 `DUPLICATE_IN_BATCH` 检测；上传时 sha256 算了**从不查重**（`DUPLICATE_HISTORY` 无）；`BALANCE_DISCONTINUITY` 无连续性比对。 |
| 证据 | grep `row_hash` 仅命中 model+migration；`files.py` 上传无条件插入 |
| 性质 | 已在 handover §11 标注为非 MVP（可后续） |

### P1-4. 规则引擎 None 值崩溃 bug

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.6 规则健壮性、技术设计 §15.2 风险缓解 |
| 现状 | `gte`/`lte` 操作符在字段为 None 时 `Decimal(str(None))` = `Decimal("None")` 抛 `InvalidOperation`，且该模块**未导入 `InvalidOperation`**，会作为未捕获异常暴露。 |
| 证据 | `app/services/rule_service.py:76-79`；`Decimal` 已导入，`InvalidOperation` 未导入 |
| 性质 | **真缺口（潜在崩溃）** |

### P1-5. 日期范围规则不可用

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.6.8 "交易日期在指定范围" |
| 现状 | 无独立日期操作符，`gte`/`lte` 强转 Decimal，对日期串必然崩。 |
| 证据 | `app/services/rule_service.py:76-79` |
| 性质 | **真缺口** |

### P1-6. `conditional` 映射类型缺失

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.5 映射类型 4 条件映射 |
| 现状 | 6 种映射类型实现 5 种（`field`/`fixed`/`concat`/`rule_output`/`manual`），独缺 `conditional`，直接 raise。 |
| 证据 | `app/services/mapping_service.py:40` |
| 性质 | **真缺口** |

### P1-7. 表头自动识别是死代码

| 项 | 内容 |
|---|---|
| PRD 依据 | §5.1.3 / §9.1 "系统识别表头、字段、金额方向、日期格式、数据起始行" |
| 现状 | `detect_header_row` 函数存在且有单测，但 `parse_bank_statement` **从不调用它**，直接用配置里的 `header_row_index`。首次配置流程（PRD §5.1）无法自动识别。 |
| 证据 | `app/services/parser_service.py:53-72` 实现；`:80-83` 解析路径直接用 config index，未调 detect |
| 性质 | **真缺口** |

### P1-8. `/bank-templates/detect` 端点缺失

| 项 | 内容 |
|---|---|
| PRD 依据 | §5.1 首次配置流程、技术设计 §11.2 |
| 现状 | 设计规划的"上传样本自动识别"端点不存在，对应模板识别确认页（PRD §9 #4）无法实现。 |
| 证据 | `bank_templates.py` 路由无 detect；grep app/ 无 detect 端点 |
| 性质 | **真缺口** |

---

## 4. 🟡 P2 — 认证 / 权限 / 审计缺口（PRD §7、§6.10）

### P2-1. 完全无认证

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.10.1 登录、§7 权限角色、技术设计 §3 Auth & RBAC |
| 现状 | 无 JWT/session/密码校验，`deps.py` 只有 DB 依赖。路由靠请求体自报身份（`user-1`）。 |
| 证据 | `app/api/deps.py` 仅 `DbSession`；`app/models/user.py:13` 有 `password_hash` 列但无读写；无登录端点 |
| 性质 | 已在 handover §11 标注为非 MVP |

### P2-2. RBAC 5 角色未实现

| 项 | 内容 |
|---|---|
| PRD 依据 | §7 五类角色（管理员/模板管理员/财务处理员/复核员/审计员） |
| 现状 | `Role` 表存在但无 user_role 关联表、无任何角色检查中间件/依赖。 |
| 证据 | `app/models/user.py:22-27` Role 表；grep `app/` 无 role 查询/权限检查 |
| 性质 | 已在 handover §11 标注为非 MVP |

### P2-3. 审计只记 CREATE，缺 MODIFY/停用/重排/登录/权限

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.10 列 8 类必须记录 |
| 现状 | 9 个审计事件全是 `*.created`。缺 `*.modified` / `*.disabled` / `rule.priority_changed` / `login` / `permission.changed`。根因：这些操作端点本身都不存在。 |
| 证据 | grep `record_audit_event` 仅 9 处，action 全为 `*.created`/`file.uploaded`/`export.created` |
| 性质 | 部分依赖 P0-1/P2-4 端点先存在 |

### P2-4. 无停用/启用、无规则重排端点

| 项 | 内容 |
|---|---|
| PRD 依据 | §6.10.3/§6.10.5、技术设计 §11.5 `PATCH /status`、`POST /rules/reorder` |
| 现状 | 无任何 `PATCH /status` 路由；无 `/rules/reorder`。status 列永远 `active`。 |
| 证据 | grep `@router` 无 status/reorder 路由 |
| 性质 | **真缺口**（与 P0-1 编辑能力同属"模板管理"未完成部分） |

---

## 5. 🟡 P2 — 前端页面缺口（PRD §9 列 12 个关键页面）

| # | PRD 页面 | 状态 | 说明 |
|---|---------|------|------|
| 1 | 登录页 | ❌ 不存在 | 无 `/login` 路由，无 LoginPage（依赖 P2-1） |
| 2 | 首页/批次列表 | ✅ 已实现 | `ConversionRunListPage` @ `/runs` |
| 3 | 上传银行流水页 | ⚠️ 部分 | 上传可用，但公司/账号/模板/映射选择器**全部写死**，非 PRD §5.2 要求的可选配置 |
| 4 | 模板识别确认页 | ❌ 不存在 | 依赖后端 P1-8 detect 端点 |
| 5 | 银行模板管理页 | ⚠️ 只读 | 列表+详情存在，**无新建/编辑/停用/新版本 UI** |
| 6 | 公司日记账模板管理页 | ⚠️ 只读 | 同上 |
| 7 | 字段映射配置页 | ⚠️ 只读 | **无配置 UI** |
| 8 | 规则管理页 | ⚠️ 只读 | 无拖拽优先级/启停/条件动作编辑器 |
| 9 | 转换预览页 | ⚠️ 合并进批次详情 | 缺"左原始/右日记账"分栏、按异常筛选、批量确认 |
| 10 | 人工确认页 | ❌ UI 不可达 | 后端接口有，前端无确认/编辑入口（见 P0-6） |
| 11 | 导出记录页 | ❌ 不存在 | 导出端点无前端调用方 |
| 12 | 审计日志页 | ✅ 已实现 | `AuditLogPage` @ `/audit` |

**模板/映射/规则管理页共性缺口**（即 P0-1 的前端侧）：新建表单、编辑(新版本)表单、版本历史展示、停用按钮——4 个实体全缺。

---

## 6. ✅ 已正确实现（无需改动）

- 三层数据模型 + 全链路持久化（source_files → bank_transactions → journal_preview_rows → exports）
- 版本化数据**结构**（不可变语义设计正确，仅缺创建新版本的端点）
- 规则冲突检测、保守确认策略（未命中/必填缺失/冲突一律待确认）
- 追溯链：BankTransaction 带 `source_file_id` / `source_sheet_name` / `source_row_index` / `raw_row_json`，preview_row 带 `bank_transaction_id`
- 单行人工修改后端（PATCH 存 old/new/reason/adjusted_by）
- CSV/XLSX 导出、审计快照、路径穿越防护（未知 id → 404）
- 处理批次与模板规则的列表 + 详情（本轮已补齐）

---

## 7. 修复优先级建议（按价值与依赖关系）

> 性质标注：**【真缺口】** = 应优先；**【非MVP/已记录】** = 可按 handover §11 节奏后续推进。

### 第一梯队：完成"确认→导出"业务闭环（P0 核心，改动可控）
1. **P0-6** 前端确认闭环：批次详情页加编辑/确认按钮 + `api/previewRows.ts` —— 让已实现的后端能力可达【真缺口】
2. **P0-3** 修复 `only_confirmed`：导出改为查库按 status 过滤【真缺口】
3. **P0-5** 导出必填字段校验【真缺口】
4. **P0-4** 生成处理报告（填充 `report_storage_key` + 报告下载端点）【真缺口】

### 第二梯队：完成"模板管理"编辑闭环（P0-1 + P2-4，体量较大）
5. **P0-1** 4 实体的 `POST /{id}/versions` 新版本端点 + 审计【真缺口】
6. **P2-4** 4 实体的 `PATCH /{id}/status` 停用端点 + 审计【真缺口】
7. 前端：新建表单 + 编辑(新版本)表单 + 版本历史 + 停用按钮（4 实体）【真缺口】
8. **P0-2** 转换批次快照模板/映射版本 ID（依赖第一梯队后的版本机制）【真缺口】

### 第三梯队：引擎健壮性（P1，多为防崩溃与合规）
9. **P1-4** 规则引擎 None 防护（防潜在崩溃）【真缺口】
10. **P1-1** 解析错误改为标记单行异常码而非中断批次【真缺口】
11. **P1-2** 补齐 3 种金额模式【真缺口】
12. **P1-6** 补 `conditional` 映射【真缺口】
13. **P1-5** 日期范围规则操作符【真缺口】
14. **P1-7/P1-8** 表头自动识别接线 + detect 端点 + 模板识别页【真缺口】

### 第四梯队：去重 / 认证 / 异步（handover §11 已记录，非 MVP 阻塞）
15. **P1-3** 去重哈希 + 余额连续性【非MVP/已记录】
16. **P2-1/P2-2** 认证 + RBAC【非MVP/已记录】
17. **P2-3** 审计补全（依赖上述端点先存在）【部分依赖】
18. PostgreSQL 实测、账号加密、异步任务、前端分包【非MVP/已记录】

---

## 8. 附：模板/映射/规则"编辑能力"完整缺口矩阵

> 覆盖银行模板 / 日记账模板 / 映射方案 / 规则 4 个实体，每实体均缺以下 4 类操作（除"新建 v1"后端已有）。

| 能力 | 后端端点 | 前端 | 银行模板 | 日记账模板 | 映射方案 | 规则 |
|------|---------|------|:---:|:---:|:---:|:---:|
| 新建 v1 | `POST /api/{entity}` | 新建表单 | 后端✅/前端❌ | 后端✅/前端❌ | 后端✅/前端❌ | 后端✅/前端❌ |
| **编辑=新建版本** | `POST /api/{entity}/{id}/versions` | 编辑表单 | **全缺** | **全缺** | **全缺** | **全缺** |
| 版本历史 | `GET /api/{entity}/{id}/versions` | 版本历史抽屉 | **全缺** | **全缺** | **全缺** | **全缺** |
| 停用/启用 | `PATCH /api/{entity}/{id}/status` | 停用按钮 | **全缺** | **全缺** | **全缺** | **全缺** |
| 调整优先级 | `POST /api/rules/reorder` | 拖拽排序 | — | — | — | **全缺** |

**设计约束提醒**（PRD §6.2 / 技术设计 §8.1）：版本化记录一经批次引用不可变；界面"编辑"实际是创建 `version_no+1` 的新版本行，旧版本数据不动，历史批次仍引用旧版本 ID。
