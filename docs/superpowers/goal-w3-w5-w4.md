# Goal 启动提示词：按 W3 → W5 → W4 顺序收口 FA Tools

> 用法：把下面「---」之间的整段作为 goal 的启动提示词。它是自包含的，goal 应据此自行
> 走 brainstorm → spec → plan → execute 全流程，按指定顺序推进三个工作流。

---

你是 FA Tools（FastAPI 后端 + React 前端的财务自动化工具包）的资深工程师。请按
**W3 收尾 → W5 → W4** 的顺序，完整收口本项目的三个工作流。

## 背景：六工作流方案（W0–W5）

项目按六个工作流推进，执行顺序为 `W0 → W1 → W2 →（W3 ∥ W5）→ W4`：

- **W0+W1 转换核心重构**（domain 层 + 转换管道）— 已合并
- **W2 API 健壮性**（422 契约、N+1、preview-rows 分页、索引、审计 schema）— 已合并
- **W3 安全加固**（JWT 鉴权、五角色 RBAC、租户隔离、字段加密、审计脱敏、SQLite FK pragma、前端 RBAC UI）— 已随 PR #13 合并到 main
- **W5 前端**（分页接入、扁平 list 分页、动态列；**本轮额外并入「模板/映射/规则编辑能力」**，见下）— 无 spec/plan，待你设计
- **W4 数据运维**（迁移真实执行+契约测试、PostgreSQL 实测、异步任务）— 无 spec/plan，待你设计

**关键约束（用户已拍板）：** gap-analysis 里 P0-1（编辑=新版本端点）/ P2-4（启停、规则重排端点）
及其前端 UI，**统一归入 W5 前端工作流**，不要放进 W4。W4 只做数据运维。

## 必读文档（开工前逐份读，建立全局观）

- `CLAUDE.md` / `AGENTS.md` — 命令、约定、接线点、语言规范（一律中文）
- `docs/handover.md` — 交接现状、W3 安全模型、生产部署须知、已知后续项
- `docs/gap-analysis.md` — PRD 合规缺口（P0/P1/P2 分级 + 代码证据 + 性质标注）
- `docs/superpowers/specs/2026-06-29-w3-security-hardening-design.md` 与对应 `plans/` — W3 设计与逐任务计划
- `docs/superpowers/specs/2026-06-29-api-hardening-design.md` — W2 设计（含 W5/W4 范围注脚：W5 前端分页接入/扁平 list 分页/动态列；W4 迁移契约/PG 实测/异步）
- `.impeccable.md` — 全站视觉基准（前端改动须遵守：品牌红 `#b5141d`、品牌蓝 `#133f8e`、楷体标题，在 AntD v5 上叠 token）

## 工作纪律（贯穿全程，不可省）

- **流程技能**：每个工作流先 `superpowers:brainstorming` 厘清意图/边界 →（W5/W4 无计划）
  `superpowers:writing-plans` 产出 spec+plan → `superpowers:subagent-driven-development`
  或 `superpowers:executing-plans` 逐任务实施。
- **TDD**：先写失败测试 → 实现 → 验证（`superpowers:test-driven-development`）。
- **验证门禁**：每个任务收尾必须 `cd backend && .venv/bin/pytest -q` 全绿 +
  `cd backend && ruff check .` 全绿（ruff 在 `~/.local/bin`，不在 .venv）；前端改动加
  `cd frontend && npm run build`、必要时 `npm run e2e`。
  不要在未跑验证的情况下宣称完成（`superpowers:verification-before-completion`）。
- **提交**：Conventional commits，提交信息用中文。**每个工作流用独立 feature 分支**
  （如 `feat/w5-frontend`、`feat/w4-data-ops`），不要直接在 main 上改。
- **确认边界**：`git commit`/`git push`、改迁移/数据库、合并 PR、对外发送等不可逆操作前
  先征求用户确认；普通代码改动/读取/搜索可直接执行。
- **顺带问题**：发现计划外的问题先报告用户，不要擅自扩大改动范围。
- **范围标注**：每个工作流结束更新 `docs/handover.md` 与 `docs/gap-analysis.md`，
  勾掉已完成项、标注新缺口。

## 三个工作流的范围

### 1. W3 收尾（先做，你自行盘点决定范围）

W3 主体已随 PR #13 合并。请**自行盘点残留**后决定收尾范围：

1. 对照 `plans/2026-06-29-w3-security-hardening.md` 的 checkbox 与 spec，核对哪些已落地、
   哪些是注脚里「本 spec 不强制」的项。
2. 验证现状：后端 pytest + ruff 全绿；前端 build + e2e 通过。如有未绿，先修复。
3. 评估 handover「生产部署须知 §4 已知功能缺口」里的两项是否纳入本次收尾：
   - 缺 `GET /api/companies` 列表端点（前端跨公司用户的公司选择器目前写死）；
   - 模板/规则启停 Switch 前端未做权限门控（属技术债）。
   注：其中「公司选择器/启停权限门控」与 W5 前端高度相关，若更适合并入 W5，请说明并推迟。
4. 收尾产出：更新交接/差距文档，明确 W3 已闭合、剩余项去向。

### 2. W5 前端（无 spec/plan，需 brainstorm → spec → plan → execute）

候选范围（在 brainstorming 阶段与用户敲定最终边界）：

- **接入 W2 分页端点**：前端改用 `GET /conversion-runs/{run_id}/preview-rows?limit&offset`
  分页加载预览行（W2 已加该端点，详情端点暂保留）。
- **扁平 list 分页**：批次/模板/规则/映射 list 端点后端补分页（W2 注脚明确留到 W5），前端接入。
- **动态列**：日记账预览/导出列按模板输出字段动态渲染，而非写死列。
- **编辑能力（本轮并入 W5）**：4 实体（银行模板/日记账模板/映射/规则）补
  - 后端 `POST /api/.../{id}/versions`（编辑=创建 version_no+1 新版本，旧版本不可变）、
    `PATCH /api/.../{id}/status`（启停）、规则 `POST /api/.../rules/reorder`（重排），
    并补审计事件 `*.modified` / `*.disabled` / `rule.priority_changed`；
  - 前端新建表单 / 编辑(新版本)表单 / 版本历史 / 停用按钮 / 规则拖拽排序 UI。
  - 严守「版本化记录一经批次引用不可变」（PRD §6.2 / 技术设计 §8.1）。
- **gap-analysis §5 其余前端缺口**（按价值在 brainstorming 取舍）：人工确认闭环 UI
  （若 W3 已接通则跳过）、上传页配置选择器去写死、导出记录页等。
- 视觉遵守 `.impeccable.md`。

### 3. W4 数据运维（无 spec/plan，需 brainstorm → spec → plan → execute）

候选范围（brainstorming 阶段敲定）：

- **迁移真实执行 + 契约测试**：`alembic upgrade head` 全链路跑通；补 migration 与
  `Base.metadata` 一致性的契约测试（autogenerate 无 diff）。
- **PostgreSQL 实测**：当前环境无 Docker。设计成可在有 Docker 的环境一键验证
  （`docker compose up -d postgres && alembic upgrade head` + 一组针对 PG 的集成测试），
  并在文档/CI 中固化；注意模型用通用 `JSON`，PG 建为 `JSON` 而非 `JSONB`，
  如需 JSONB 索引/性能需评估迁移。
- **异步任务**：大文件（>10000 行）解析/转换从同步改为 Celery/RQ 异步（技术设计已规划），
  含任务状态查询与前端轮询的最小接口（前端深度接入可留作后续）。
- **可选**：去重哈希 + 余额连续性（gap P1-3，handover 标非 MVP）是否纳入，brainstorming 时与用户确认。

## 交付节奏

每个工作流：brainstorm → spec → plan → 逐任务 TDD 实施 → 全量验证 →（征得确认后）提 PR →
更新 handover/gap-analysis。一个工作流闭合后再开下一个；遇到跨工作流依赖（如 P0-2 批次快照
版本 ID 依赖 W5 的版本机制）显式说明并排序。完成后给出一句话总结 + 是否验证过。

---
