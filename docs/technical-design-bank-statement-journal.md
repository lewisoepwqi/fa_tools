# 银行流水转公司日记账工具技术设计

## 1. 设计目标

本设计服务于第一个 MVP：把银行流水文件转换为公司要求的日记账文件。

系统必须满足四个核心约束：

1. 原始文件和原始行不可丢失。
2. 模板、映射、规则必须版本化。
3. 自动化结果必须可解释。
4. 不确定项必须进入人工确认。

## 2. 推荐技术栈

### 2.1 前端

推荐：React + TypeScript + Ant Design。

原因：

1. 财务工具以表格、表单、筛选、批量操作为主，Ant Design 的组件契合度高。
2. TypeScript 有助于约束复杂字段映射和状态流转。
3. React 生态在文件上传、虚拟表格、Excel 预览方面选择较多。

### 2.2 后端

推荐：Python FastAPI。

原因：

1. Excel、CSV、数据清洗、规则处理的 Python 生态成熟。
2. FastAPI 适合快速提供结构化 API。
3. 后续如接入 OCR、机器学习、数据分析，Python 扩展成本低。

### 2.3 数据库

推荐：PostgreSQL。

原因：

1. 关系模型适合模板、规则、批次、审计日志。
2. JSONB 可保存原始字段快照、规则条件、规则动作。
3. 后续可支持复杂检索和报表。

### 2.4 异步任务

推荐：Celery + Redis，或 RQ + Redis。

用途：

1. 文件解析。
2. 大批量规则匹配。
3. 导出文件生成。
4. 批次统计。

### 2.5 文件存储

MVP 可使用本地文件存储；生产建议使用 S3 兼容对象存储，例如 MinIO。

存储对象：

1. 原始上传文件。
2. 解析中间文件。
3. 导出文件。
4. 处理报告。

## 3. 架构概览

```text
Browser
  |
  | HTTPS / REST API
  v
FastAPI Backend
  |
  |-- Auth & RBAC
  |-- Template Service
  |-- Mapping Service
  |-- Rule Service
  |-- Conversion Service
  |-- Preview & Confirmation Service
  |-- Export Service
  |-- Audit Service
  |
  | async jobs
  v
Worker
  |
  |-- Parse Excel/CSV
  |-- Normalize Bank Transactions
  |-- Apply Mappings and Rules
  |-- Generate Export Files
  |
  +--> PostgreSQL
  +--> Object Storage
```

### 3.1 工具化隔离（实现位置）

本工具是 fa_tools 工具包中的一个独立模块，物理上与平台共享层隔离：

**后端 `backend/app/tools/bank_journal/`：**
- `models/ services/ schemas/ routes/` 全部为本工具专属。
- 工具根 `__init__.py` 暴露 `register(app)`，由 `app/main.py` 调用挂载路由。
- 工具模型在 `models/__init__.py` 顶部导入即注册到 `Base.metadata`，`migrations/env.py` 通过 `import app.tools.bank_journal` 触发。
- 平台共享层（`models/` 下的 user/company/audit/file、`services/audit_service`+`file_service`、`api/routes/files`+`audit`、`core`、`db`）保留在 `app/` 根。
- 工具路由前缀统一 `/api/tools/bank-journal/...`；表名/Alembic 迁移不变。

**前端 `frontend/src/tools/bank_journal/`：**
- `pages/ components/ types/ api/ routes.tsx index.ts` 全部为本工具专属。
- `index.ts` 导出 `Tool` 描述符，加入 `src/tools/registry.ts`，AppShell 菜单与 App 路由据此动态生成。
- 平台共享层（`App.tsx`、`api/client.ts`、`api/files.ts`、`components/AppShell.tsx`、`pages/AuditLogPage.tsx`）保留在 `src/` 根。

下方 §4 描述的是本工具内部的逻辑模块边界。

## 4. 模块边界

### 4.1 File Service

职责：

1. 接收文件上传。
2. 计算文件哈希。
3. 保存文件元数据。
4. 保存原始文件到对象存储。
5. 防止重复上传。

不负责：

1. 判断会计科目。
2. 修改模板。
3. 生成导出文件。

### 4.2 Parser Service

职责：

1. 读取 Excel、CSV 文件。
2. 识别 Sheet、表头行、数据起始行。
3. 根据银行模板解析原始行。
4. 生成标准流水记录。

不负责：

1. 公司模板映射。
2. 会计规则判断。

### 4.3 Template Service

职责：

1. 管理银行模板。
2. 管理公司日记账模板。
3. 管理模板版本。
4. 比较模板差异。

模板版本一经使用，不允许物理修改。界面上的修改动作实际创建新版本。

### 4.4 Mapping Service

职责：

1. 管理标准流水字段到公司模板字段的映射。
2. 管理映射版本。
3. 执行字段转换、固定值、拼接、简单条件映射。

### 4.5 Rule Service

职责：

1. 管理规则和规则版本。
2. 按优先级执行规则。
3. 输出规则命中详情。
4. 标记冲突。

规则引擎必须返回解释信息：

1. 命中的规则 ID。
2. 命中的规则版本。
3. 命中的条件。
4. 被写入的字段。
5. 写入前值和写入后值。

### 4.6 Conversion Service

职责：

1. 创建处理批次。
2. 串联解析、标准化、映射、规则匹配。
3. 生成预览记录。
4. 统计处理结果。

### 4.7 Confirmation Service

职责：

1. 管理待确认项。
2. 保存人工修改。
3. 保存确认动作。
4. 支持批量确认。

### 4.8 Export Service

职责：

1. 根据公司模板生成 Excel 或 CSV。
2. 校验必填字段和字段格式。
3. 生成处理报告。
4. 保存导出记录。

### 4.9 Audit Service

职责：

1. 记录关键操作。
2. 记录变更前后快照。
3. 提供审计检索 API。

## 5. 核心数据模型

### 5.1 users

```text
id
email
name
password_hash
status
created_at
updated_at
```

### 5.2 roles

```text
id
code
name
description
```

### 5.3 companies

```text
id
name
code
status
created_at
updated_at
```

### 5.4 bank_accounts

```text
id
company_id
bank_name
account_name
account_no_encrypted
currency
status
created_at
updated_at
```

### 5.5 source_files

```text
id
company_id
uploaded_by
original_filename
file_type
file_size
sha256
storage_key
status
error_message
created_at
```

### 5.6 bank_templates

```text
id
company_id
name
bank_name
bank_account_id
status
created_at
updated_at
```

### 5.7 bank_template_versions

```text
id
bank_template_id
version_no
file_type
sheet_selector_json
header_row_index
data_start_row_index
field_aliases_json
date_formats_json
amount_mode
amount_config_json
unique_key_config_json
sample_file_id
created_by
created_at
```

### 5.8 company_journal_templates

```text
id
company_id
name
status
created_at
updated_at
```

### 5.9 company_journal_template_versions

```text
id
company_journal_template_id
version_no
file_type
sheet_name
header_row_index
data_start_row_index
columns_json
required_columns_json
format_rules_json
sample_file_id
created_by
created_at
```

### 5.10 mapping_profiles

```text
id
company_id
name
bank_template_id
company_journal_template_id
status
created_at
updated_at
```

### 5.11 mapping_profile_versions

```text
id
mapping_profile_id
version_no
bank_template_version_id
company_journal_template_version_id
mappings_json
created_by
created_at
```

### 5.12 rules

```text
id
company_id
name
scope_type
scope_id
status
created_at
updated_at
```

### 5.13 rule_versions

```text
id
rule_id
version_no
priority
conditions_json
actions_json
allow_auto_confirm
created_by
created_at
```

### 5.14 conversion_runs

```text
id
company_id
bank_account_id
period_start
period_end
status
bank_template_version_id
company_journal_template_version_id
mapping_profile_version_id
created_by
created_at
completed_at
summary_json
```

### 5.15 conversion_run_files

```text
id
conversion_run_id
source_file_id
status
row_count
error_message
created_at
```

### 5.16 bank_transactions

```text
id
conversion_run_id
source_file_id
source_sheet_name
source_row_index
transaction_date
posting_date
bank_account_id
currency
direction
debit_amount
credit_amount
net_amount
balance
counterparty_name
counterparty_account_no_encrypted
counterparty_bank_name
summary
purpose
transaction_type
bank_transaction_id
receipt_no
raw_row_json
row_hash
created_at
```

### 5.17 journal_preview_rows

```text
id
conversion_run_id
bank_transaction_id
row_index
output_values_json
status
exception_codes_json
matched_rule_versions_json
rule_trace_json
created_at
updated_at
```

### 5.18 manual_adjustments

```text
id
journal_preview_row_id
field_name
old_value
new_value
reason
adjusted_by
created_at
```

### 5.19 confirmations

```text
id
journal_preview_row_id
confirmation_type
confirmed_by
confirmed_at
comment
```

### 5.20 exports

```text
id
conversion_run_id
exported_by
file_type
storage_key
report_storage_key
row_count
only_confirmed
created_at
```

### 5.21 audit_logs

```text
id
company_id
actor_id
action
entity_type
entity_id
before_json
after_json
ip_address
user_agent
created_at
```

## 6. 标准流水模型

Parser Service 输出统一结构：

```json
{
  "transaction_date": "2026-06-01",
  "posting_date": "2026-06-01",
  "bank_account_id": "uuid",
  "currency": "CNY",
  "direction": "credit",
  "debit_amount": null,
  "credit_amount": "12000.00",
  "net_amount": "12000.00",
  "balance": "98000.00",
  "counterparty_name": "某客户有限公司",
  "counterparty_account_no": "encrypted",
  "counterparty_bank_name": "某银行某支行",
  "summary": "货款",
  "purpose": "6月服务费",
  "transaction_type": "转账",
  "bank_transaction_id": "202606010001",
  "receipt_no": null,
  "raw_row": {}
}
```

金额规则：

1. `direction=debit` 表示银行账户资金减少。
2. `direction=credit` 表示银行账户资金增加。
3. `net_amount` 收入为正，支出为负。
4. 借贷金额保留银行原始含义，导出时再按公司模板映射。

## 7. 规则引擎设计

### 7.1 规则 JSON 示例

```json
{
  "conditions": {
    "all": [
      {"field": "direction", "op": "eq", "value": "credit"},
      {"field": "counterparty_name", "op": "contains", "value": "客户"},
      {"field": "summary", "op": "contains_any", "value": ["货款", "服务费"]}
    ]
  },
  "actions": [
    {"field": "journal_summary", "value": "收到客户款项"},
    {"field": "account_subject", "value": "银行存款"},
    {"field": "income_category", "value": "主营业务收入"}
  ],
  "allow_auto_confirm": false
}
```

### 7.2 执行顺序

1. 读取当前批次绑定的规则版本集合。
2. 按 `priority` 从小到大排序，数字越小优先级越高。
3. 对每条标准流水执行规则条件。
4. 规则命中后写入目标字段。
5. 记录规则执行轨迹。
6. 如果同一字段出现不同值，标记 `RULE_CONFLICT`。
7. 执行必填字段校验。
8. 计算确认状态。

### 7.3 确认状态计算

```text
if parse_failed:
    status = PARSE_FAILED
elif has_rule_conflict:
    status = CONFLICT
elif has_required_missing:
    status = NEEDS_CONFIRMATION
elif all_matched_rules_allow_auto_confirm:
    status = AUTO_CONFIRMED
else:
    status = NEEDS_CONFIRMATION
```

## 8. 模板版本策略

### 8.1 不可变版本

以下记录一经被批次引用，不允许修改：

1. `bank_template_versions`
2. `company_journal_template_versions`
3. `mapping_profile_versions`
4. `rule_versions`

界面上的编辑操作创建新版本。

### 8.2 批次快照

`conversion_runs` 必须保存当次使用的版本 ID：

1. 银行模板版本 ID。
2. 公司模板版本 ID。
3. 映射版本 ID。
4. 规则版本集合。

规则版本集合可保存到 `summary_json` 或单独建 `conversion_run_rule_versions` 表。生产建议单独建表：

```text
conversion_run_rule_versions
id
conversion_run_id
rule_version_id
created_at
```

## 9. 解析策略

### 9.1 表头识别

启发式规则：

1. 扫描前 30 行。
2. 计算每行非空单元格数量。
3. 计算该行命中银行字段别名的数量。
4. 命中数量最高且后续行有金额和日期的行作为候选表头。
5. 用户确认后保存到模板版本。

### 9.2 金额模式识别

支持四类：

1. 单金额列 + 收支方向列。
2. 借方金额列 + 贷方金额列。
3. 收入金额列 + 支出金额列。
4. 金额列正负号表示方向。

无法确定时要求用户在模板识别页确认。

### 9.3 日期解析

支持常见格式：

1. `YYYY-MM-DD`
2. `YYYY/MM/DD`
3. `YYYY.MM.DD`
4. `YYYYMMDD`
5. Excel date serial

日期无法解析时标记 `INVALID_DATE`。

### 9.4 去重策略

优先使用银行流水号。缺失时使用组合哈希：

```text
bank_account_id
transaction_date
net_amount
balance
counterparty_name
summary
source_row_normalized_text
```

同一批次内重复标记 `DUPLICATE_IN_BATCH`。

跨批次重复标记 `DUPLICATE_HISTORY`，但不自动删除。

## 10. 异常代码

```text
MISSING_REQUIRED_FIELD
INVALID_DATE
INVALID_AMOUNT
UNKNOWN_DIRECTION
AMOUNT_DIRECTION_MISMATCH
RULE_CONFLICT
NO_RULE_MATCH
DUPLICATE_IN_BATCH
DUPLICATE_HISTORY
BALANCE_DISCONTINUITY
TEMPLATE_NOT_MATCHED
UNSUPPORTED_FILE_TYPE
```

## 11. API 草案

### 11.1 文件

```text
POST /api/files/upload
GET  /api/files/{id}
```

### 11.2 银行模板

```text
POST /api/bank-templates/detect
POST /api/bank-templates
GET  /api/bank-templates
GET  /api/bank-templates/{id}
POST /api/bank-templates/{id}/versions
GET  /api/bank-templates/{id}/versions
```

### 11.3 公司模板

```text
POST /api/journal-templates
GET  /api/journal-templates
POST /api/journal-templates/{id}/versions
GET  /api/journal-templates/{id}/versions
```

### 11.4 映射

```text
POST /api/mapping-profiles
GET  /api/mapping-profiles
POST /api/mapping-profiles/{id}/versions
GET  /api/mapping-profiles/{id}/versions
```

### 11.5 规则

```text
POST /api/rules
GET  /api/rules
POST /api/rules/{id}/versions
PATCH /api/rules/{id}/status
POST /api/rules/reorder
```

### 11.6 转换批次

```text
POST /api/conversion-runs
GET  /api/conversion-runs
GET  /api/conversion-runs/{id}
POST /api/conversion-runs/{id}/start
GET  /api/conversion-runs/{id}/preview-rows
```

### 11.7 确认

```text
PATCH /api/preview-rows/{id}
POST  /api/preview-rows/{id}/confirm
POST  /api/preview-rows/bulk-confirm
```

### 11.8 导出

```text
POST /api/conversion-runs/{id}/exports
GET  /api/exports/{id}/download
GET  /api/exports/{id}/report
```

### 11.9 审计

```text
GET /api/audit-logs
```

## 12. 前端页面设计

### 12.1 批次列表

展示：

1. 批次号。
2. 公司。
3. 银行账号。
4. 期间。
5. 状态。
6. 文件数。
7. 总行数。
8. 异常数。
9. 创建人。
10. 创建时间。

### 12.2 上传页

能力：

1. 多文件上传。
2. 自动显示文件解析状态。
3. 选择银行账号、银行模板、公司模板、映射方案。
4. 发起处理。

### 12.3 模板识别页

能力：

1. 展示前 50 行原始数据。
2. 高亮系统猜测的表头。
3. 手动选择表头行和数据起始行。
4. 配置字段别名和金额模式。
5. 保存为新模板或新版本。

### 12.4 转换预览页

能力：

1. 左侧显示原始流水字段。
2. 右侧显示生成的日记账字段。
3. 支持按异常类型、确认状态、规则命中筛选。
4. 支持批量确认。
5. 支持单行编辑。
6. 支持查看规则命中轨迹。

### 12.5 规则管理页

能力：

1. 列表展示规则、优先级、适用范围、状态。
2. 支持拖拽调整优先级。
3. 支持启用、停用、复制、创建新版本。
4. 支持在规则编辑页配置条件和动作。

## 13. 测试策略

### 13.1 单元测试

覆盖：

1. 日期解析。
2. 金额解析。
3. 表头识别。
4. 金额模式识别。
5. 规则条件匹配。
6. 规则冲突检测。
7. 必填字段校验。
8. 去重哈希计算。

### 13.2 集成测试

覆盖：

1. 上传文件到解析成功。
2. 创建银行模板版本。
3. 创建公司模板版本。
4. 执行完整转换批次。
5. 人工确认后导出。
6. 历史批次仍引用旧模板版本。

### 13.3 样本回归测试

每个银行模板至少保留一个脱敏样本文件。模板解析逻辑修改后，应对所有样本执行回归测试。

## 14. MVP 里程碑

### 14.1 M1：基础框架和文件解析

1. 用户登录和基础权限。
2. 文件上传。
3. Excel/CSV 解析。
4. 表头识别。
5. 标准流水生成。

### 14.2 M2：模板和映射

1. 银行模板管理。
2. 银行模板版本管理。
3. 公司模板管理。
4. 公司模板版本管理。
5. 映射配置。

### 14.3 M3：规则和预览

1. 规则管理。
2. 规则执行。
3. 转换批次。
4. 预览表格。
5. 异常标识。

### 14.4 M4：人工确认和导出

1. 人工修改。
2. 批量确认。
3. Excel/CSV 导出。
4. 处理报告。
5. 审计日志。

## 15. 风险和缓解

### 15.1 银行流水格式不稳定

缓解：

1. 模板版本不可变。
2. 上传样本时做模板差异检测。
3. 提供人工确认表头和金额模式。

### 15.2 规则误判导致错误入账

缓解：

1. 默认不自动确认。
2. 自动确认需要显式开启。
3. 多规则冲突强制人工确认。
4. 导出前校验必填字段。

### 15.3 历史处理不可追溯

缓解：

1. 保存原始文件。
2. 保存原始行快照。
3. 保存模板、映射、规则版本。
4. 保存人工修改记录。

### 15.4 文件数据敏感

缓解：

1. 银行账号加密存储。
2. 展示时脱敏。
3. 文件下载受权限控制。
4. 关键操作记录审计日志。

## 16. 后续扩展

1. 支持 PDF、OFD、图片 OCR。
2. 支持 CAMT.053、BAI2、OFX、QFX 等结构化银行报文。
3. 支持银行电子回单、银行电子对账单的 XBRL/XML 解析。
4. 支持金蝶、用友、SAP、Oracle、NetSuite 导入格式。
5. 支持银行流水和总账现金科目的完整对账。
6. 支持基于人工确认历史的规则推荐。
7. 支持规则效果分析和命中率统计。

## 17. 外部实践参考

1. QuickBooks Online 银行规则：规则按条件自动分类银行交易，规则有优先级，命中后仍进入待复核视图。来源：https://quickbooks.intuit.com/learn-support/en-us/help-article/banking/set-bank-rules-categorize-online-banking-online/L0mjJl0nD_US_en_US
2. Odoo Accounting 对账模型：使用 reconciliation models 自动或手动处理高频重复银行交易。来源：https://www.odoo.com/documentation/19.0/applications/finance/accounting/bank/reconciliation.html
3. Dynamics 365 Finance 银行对账匹配规则：通过条件筛选银行流水和账务交易，多匹配时要求人工匹配。来源：https://learn.microsoft.com/en-us/dynamics365/finance/cash-bank-management/set-up-bank-reconciliation-matching-rules
4. NetSuite 银行数据导入：CSV 必须符合模板约束，并支持 CSV、OFX、QFX、BAI2、CAMT.053 等默认解析器。来源：https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1508962727.html
5. ISO 20022 现金管理报文：后续支持 CAMT.053 等结构化银行对账单时应参考官方消息定义。来源：https://www.iso20022.org/iso-20022-message-definitions
6. 财政部电子凭证会计数据标准：XML、XBRL 等结构化数据应支持接收、验签或验真、解析、报销、入账、归档等全流程处理。来源：https://fgk.chinatax.gov.cn/zcfgk/c102416/c5240524/content.html
