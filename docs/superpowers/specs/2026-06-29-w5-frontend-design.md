# 设计：前端收口与分页（W5）

> 日期：2026-06-29 · 状态：自主模式产出（用户已授权「不逐项确认、自行决定」），待用户复核
> 范围：**W5** —— 列表分页（后端补 + 前端接入）、preview-rows 分页接入、日记账动态列、规则拖拽重排 UI、公司选择器修复 + `GET /api/companies`、权限门控补齐。
> 前置：W0+W1（转换核心）、W2（API 健壮性）、W3（安全加固，含编辑/版本/启停/审计后端端点）均已合并。

## 0. 定位与重大现状修正

W5 原计划假设「模板/映射/规则**编辑能力前后端均为零**」。**实测代码库已远超 gap-analysis（2026-06-27）的描述**——以下已全部实现，W5 **不重建**：

- 后端 4 实体（银行模板 / 日记账模板 / 映射方案 / 规则）：`POST /{id}/versions`（编辑=新版本）、`GET /{id}/versions`、`PATCH /{id}/status`（启停）、`DELETE /{id}`（软删 + 引用拦截）、银行模板 `POST /detect`、规则 `POST /reorder` 均已实现；审计事件 `*.modified` / `*.disabled` / `*.enabled` / `rule.priority_changed` 均已挂上。
- 前端 4 实体：新建 / 编辑(新版本) / 版本历史 / 停用 Switch / 删除 全套 UI 已有；含 `BankTemplateWizard`、`MappingEditor` / `RuleEditor` / `JournalColumnsEditor` 可复用编辑器、自定义字段页、品牌主题 token（红 `#b5141d` / 蓝 `#133f8e` 已落 `theme.ts`）。
- 人工确认闭环（单行编辑 / 确认 / 批量确认 / 导出）已接通 `ConversionRunDetailPage`。
- 公司切换器已存在于 `AppShell`。

因此 W5 收敛为**7 项真实剩余缺口**，全部围绕「分页 / 动态列 / 拖拽 / 公司选择 / 权限门控」，体量可控且聚焦。

## 1. 范围

### In（W5 做）
1. **后端列表分页**：4 实体主列表 + 批次列表接入既有 `Page[T]` 信封（`limit`/`offset` + `{items,total,limit,offset}`）。
2. **前端列表分页接入**：上述列表页改造 api 层 + Table 服务端分页。
3. **preview-rows 分页接入**：`ConversionRunDetailPage` 标准路由形态改用后端既有分页端点；为该端点补 `status` 过滤参数；扩展 `ConversionRunSummary` 加分状态计数以保留统计面板。
4. **日记账动态列**：批次详情表格列与单行编辑字段，按所属日记账模板版本 `columns_json` 动态渲染，替换写死的 `['日期','摘要','科目','金额']` 与写死编辑字段「科目」。
5. **规则拖拽重排 UI**：`RulePage` 列表加拖拽排序，提交既有 `POST /reorder`（前端 api `reorderRules` 已就绪）。
6. **公司选择器修复 + `GET /api/companies`**：修 `accessible_companies === 'all'`（admin/auditor）选不到具体公司导致无法创建数据的 bug；新增平台共享端点 `GET /api/companies`。
7. **权限门控补齐**：停用 Switch / 删除按钮加 `template_manage` 门控；启用 `registry` 的 `requiredPermission`（菜单级按权限显隐）。
8. **顺带 bug 修复**：规则 `reorder` 审计 `company_id=None`（routes/rules.py:376）跨公司批量丢公司归属 → 按被改规则的 company_id 记录。

### Out（W5 不做，显式排除）
- **P0-2 批次快照版本 ID**（conversion run 引用已保存版本而非内联 config）：属转换管道改造，非前端；版本机制虽已具备，但改动落在 `conversion_service`，**留作 W4 或独立后续**，本 spec 不含。
- 引擎类缺口（P1-1~P1-8：异常码补全、金额模式、conditional 映射、日期规则、detect 接线深化等）：非本工作流。
- 去重哈希 / 余额连续性（P1-3）：W4 brainstorm 决定。
- 版本表 / service 层架构重构（映射方案 / 规则逻辑在路由内、无 service）：与本目标无关的重构，YAGNI，不做。
- 导出记录独立页：批次详情已含导出入口，独立「导出记录页」价值低，本轮不做（如需后续单列）。

## 2. 后端改动

### 2.1 列表分页（统一 `Page[T]`）
现状：4 实体 list + 批次 list 返回扁平 `list[...]`；分页范式 `Page[T]` 已存在（`schemas/pagination.py`），仅 preview-rows / audit-logs 在用。

改动（沿用既有约定 `limit: int = Query(100, ge=1, le=500)` / `offset: int = Query(0, ge=0)`）：
- `routes/bank_templates.py` `GET ""` → `Page[BankTemplateResponse]`
- `routes/journal_templates.py` `GET ""` → `Page[CompanyJournalTemplateResponse]`
- `routes/mapping_profiles.py` `GET ""` → `Page[MappingProfileResponse]`（保留既有过滤参数）
- `routes/rules.py` `GET ""` → `Page[RuleResponse]`（保留既有过滤参数）
- `routes/conversion_runs.py` `GET ""` → `Page[ConversionRunListItemResponse]`（保留 `company_id` 过滤）

实现：在对应 service / 路由内 `total = base.count()` → `base.offset(offset).limit(limit)`，租户过滤（`accessible_company_filter`）在分页前施加。**versions 列表端点**（`GET /{id}/versions`）量小，本轮**不分页**（保持扁平，降低改动面）。

> **破坏性变更**：list 响应结构由数组变 `{items,...}`。前端同批改造（§3.1）。其余后端消费方仅测试，TDD 内同步更新断言。

### 2.2 preview-rows：`status` 过滤 + summary 分状态计数
- `GET /{run_id}/preview-rows` 增可选 `status: str | None = Query(None)`；非空时 `filter(JournalPreviewRow.status == status)`（`status` 为索引列，便宜）。`total` 反映过滤后总数。
- 扩展 `ConversionRunSummary`（`schemas/conversion.py:82`）增字段：`auto_confirmed_rows`、`needs_confirmation_rows`、`conflict_rows`（默认 0）。在装配 run 响应（`_summary_from_json` 或新增 counts 查询）时用一次 `GROUP BY status` 统计填充；同时把这三个计数写入 `summary_json` 落库（转换完成时）。保证统计面板在分页下仍准确，且不依赖前端全量行。
- 兼容：异常码筛选（exception_codes 数组）不做服务端过滤（JSON 数组查询涉及 PG/SQLite 可移植性，属 W4）；前端异常筛选改为「在当前页内过滤」并明确标注，或移除——见 §3.2 决策。

### 2.3 `GET /api/companies`（平台共享层）
- 新增 `app/api/routes/companies.py`：`GET /api/companies` → `list[CompanyResponse]{id, name}`，`Depends(require(Permission.READ))`。按 `accessible_company_filter(user)` 收窄：跨公司角色（admin/auditor）返回全部公司，其余返回授权集内公司。注册到 `app/main.py`。
- 审计：只读，不记审计。

### 2.4 reorder 审计公司归属修复
- `routes/rules.py:~376` reorder 写审计时 `company_id=None` → 改为按被重排规则的 `company_id` 记录（逐条 reorder 已在循环内持有 `parent.company_id`，用之）。补一条测试断言审计 company_id 非空且正确。

## 3. 前端改动

### 3.1 列表分页接入
- `api/client.ts` 范式不变；各 list api（`bankTemplates.ts` / `journalTemplates.ts` / `mappingProfiles.ts` / `rules.ts` / `conversionRuns.ts`）返回类型由 `T[]` 改为 `Page<T>`（新增共享 `types/pagination.ts` 的 `Page<T>` 接口）。新增（或复用）一个 `listXxx({limit, offset, ...filters})` 签名。
- 各列表页（`BankTemplatePage` / `JournalTemplatePage` / `MappingProfilePage` / `RulePage` / `ConversionRunListPage`）：`<Table>` 由 `pagination={false}` 改为服务端分页（`pagination={{ current, pageSize, total, onChange }}`），用 state 持 `{page, pageSize}`，change 时重新拉取。默认 pageSize 20。
- 「被引用情况」等反向查询（模板详情页用 `listMappingProfiles({bank_template_id})`）：取 `.items`，本轮不强制分页展示（量小，取首页即可，必要时显示 total）。

### 3.2 preview-rows 分页接入（`ConversionRunDetailPage`）
两种使用形态分别处理：
- **独立路由形态**（`:runId`，无 `runProp`）：
  - 元数据 + 统计：仍调 `getConversionRun(id)` 取 `summary`（现含分状态计数）与批次属性；**不再依赖内嵌 `preview_rows` 做统计**。
  - 表格：改用新 api `listPreviewRows(runId, {limit, offset, status})`（`previewRows.ts` 新增），服务端分页 + `status` 服务端筛选。
  - 编辑/确认后：重拉当前页 + 重拉 summary（计数刷新），不再本地全量 patch。
- **内联形态**（上传后 `runProp` 携带已转换小批次）：保持现状用内嵌 `preview_rows`（刚转换、量小，无需分页）。
- **异常码筛选决策**：服务端只做 `status` 过滤；异常码下拉改为「筛选当前页」并在 label 标注「(本页)」，避免给出「全量已筛」的错觉。（完整跨页异常筛选俟 W4 解决 JSON 查询可移植性后再加。）

### 3.3 日记账动态列
- 列来源：批次绑定的日记账模板版本 `columns_json`（列名字符串数组）。
- 取数：批次响应或预览行响应需能拿到列定义。优先方案——批次详情响应 `getConversionRun` 增 `journal_columns: string[]`（后端从批次绑定的日记账模板版本 `columns_json` 读出；批次未绑定版本时回退为「本批次 preview rows 的 `output_values` 键并集」）。前端据此动态生成 `ColumnsType`，单元格读 `record.output_values[列名]`。
- 单行编辑：编辑字段集合 = `journal_columns`（替换写死「科目」），用动态 `Form.Item` 渲染，必填列（`required_columns_json`）标必填。
- 兜底：`journal_columns` 为空时退回当前写死 4 列，保证不回归。

### 3.4 规则拖拽重排 UI（`RulePage`）
- 列表按 `priority` 升序展示；用 antd `Table` + 可拖拽行（`dnd-kit` 或 antd 官方 `react-dnd` 范式；优先 `@dnd-kit/sortable`，无新增重依赖则用 antd `Table` components 自定义 row）。拖拽产生新顺序 → 计算各规则新 `priority` → 调 `reorderRules({items:[{rule_id, priority}]})` → 成功后重拉。
- 门控 `template_manage`（无权禁用拖拽）；依赖 `currentCompanyId`。
- 仅对**当前页**排序（分页 + 拖拽并存时，priority 为全局序，跨页拖拽不在本轮；page=全部或 pageSize 足够大时可用）。规则通常少，pageSize 默认设较大（如 50）以容纳整公司规则集。

### 3.5 公司选择器修复 + 接入 `GET /api/companies`
- `AppShell` 公司 `<Select>`：当 `me.accessible_companies === 'all'`（admin/auditor）时，改为调 `GET /api/companies` 拉全部公司填充选项，让用户能选到**具体** company_id（修复现状 value 被强制 `''`、`currentCompanyId` 恒 null 导致无法创建数据的 bug）。数组形态维持现状。
- 「全部公司」语义：列表浏览时允许「全部」（不传 company_id）；但创建类操作要求选中具体公司——保持各页现有「`currentCompanyId` 为空时禁用新建」逻辑即可，配合本修复让 admin 也能选到具体公司。
- `api/companies.ts` 新增 `listCompanies()`。

### 3.6 权限门控补齐
- 4 实体列表/详情的**停用 Switch、删除 Popconfirm 按钮**：加 `hasPermission('template_manage')` 门控（`disabled` + Tooltip「权限不足」，与现有按钮范式一致）。
- `registry`：给 `bankJournalTool` 及其 children 设 `requiredPermission`（如工具级 `read`、模板/规则配置子项 `template_manage`、审计 `audit_view`），启用 `AppShell` 既有的菜单过滤（字段已定义未用）。粒度对齐后端 RBAC，避免显示无权访问的入口。

## 4. 模块边界与可测性

| 单元 | 职责 | 测试 |
|---|---|---|
| 各 list service/路由（后端） | 接 `Page[T]` 分页 + 租户过滤先于分页 | 集成测：total 正确、offset/limit 截断、跨公司收窄 |
| preview-rows 端点（后端） | `status` 过滤 + 分页 | 集成测：按 status 过滤后的 total/items |
| `ConversionRunSummary` 计数（后端） | GROUP BY 分状态计数落库 + 出参 | 单元/集成测：计数与造数一致 |
| `GET /api/companies`（后端） | 按可访问集返回公司 | 集成测：admin 全量 / processor 收窄 / 401 |
| reorder 审计（后端） | company_id 正确归属 | 集成测：审计 company_id 断言 |
| 前端 list api 层 | `Page<T>` 解析 | 既有 vitest（如有）+ build 通过 |
| `ConversionRunDetailPage` | 分页加载 + 动态列 + 统计取 summary | e2e 冒烟（加载、翻页、确认刷新） |
| `RulePage` 拖拽 | 拖拽→reorder→重拉 | e2e 冒烟（拖拽改序持久化） |

## 5. 执行顺序（TDD，先后端再前端，单任务可独立验证）

1. 后端：`ConversionRunSummary` 分状态计数（落库 + 出参 + GROUP BY）。
2. 后端：preview-rows `status` 过滤参数。
3. 后端：4 实体 list + 批次 list 接 `Page[T]` 分页（逐实体一任务或合并，集成测护航）。
4. 后端：`GET /api/companies` 新端点 + 注册。
5. 后端：reorder 审计 company_id 修复。
6. 前端：`Page<T>` 类型 + list api 改造 + 5 个列表页服务端分页。
7. 前端：`ConversionRunDetailPage` 改用 preview-rows 分页端点 + 统计取 summary。
8. 前端：日记账动态列（含动态编辑字段）。
9. 前端：规则拖拽重排 UI。
10. 前端：公司选择器修复 + `listCompanies` 接入。
11. 前端：权限门控补齐（按钮 + registry 菜单）。

每任务门禁：`cd backend && .venv/bin/pytest -q` + `.venv/bin/python -m ruff check .` 全绿；前端任务加 `npm run build`，关键交互（分页 / 拖拽 / 动态列）补 e2e 冒烟。

## 6. 验收

- 后端 pytest + ruff 全绿（含新增分页 / 计数 / 公司端点 / 审计修复用例）；列表端点返回 `{items,total,limit,offset}`；preview-rows 支持 `status` 过滤；`GET /api/companies` 按角色收窄；reorder 审计 company_id 正确。
- 前端 `npm run build` 通过；列表页服务端分页可翻页；批次详情分页加载预览行、统计数正确、动态列按模板渲染、编辑字段动态；规则可拖拽改序并持久化；admin 用户可在公司选择器选到具体公司并创建数据；停用/删除按钮按权限显隐；菜单按权限过滤。
- 视觉遵 `.impeccable.md`：新增 UI（分页器、拖拽手柄、公司选择）沿用 `theme.ts` token，不脱离 antd 另造。

## 7. 跨工作流依赖与排序

- **W5 → W4**：P0-2（批次快照已保存版本 ID）依赖的「版本机制」已存在，但其实现落在转换管道（`conversion_service`），归 W4/后续；W5 完成后 W4 可直接做。preview-rows 异常码的跨页服务端过滤依赖 W4 的 JSON 查询可移植性方案。
- **W5 自身**：后端（任务 1–5）先于前端（6–11）；前端分页接入（6）是动态列（8）/详情分页（7）的前置。
