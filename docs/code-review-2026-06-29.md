# 全面代码审查报告 —— FA Tools

> 日期:2026-06-29 · 范围:整个仓库(后端 FastAPI + 前端 React)
> 方法:按"平台/安全""bank_journal 业务逻辑""API/迁移/测试""前端"四个领域并行审查,
> 最严重的财务正确性与安全断言已由审查者逐条在源码中核实(标 ✅已验证)。

## 总评

工程骨架质量在原型里属上乘:分层清晰(route→service→model)、版本化 + 软删除 + 引用拦截(409)
把"历史可追溯"落得扎实、金额计算使用 `Decimal`(避开 float 精度陷阱)、统一错误拦截器、
注册表驱动的工具/路由架构、详尽中文注释。

但存在若干**会直接导致财务数据错误**的硬伤,且其中两条与代码注释 / 验收文档的承诺相反。
注意区分:许多"安全/合规"类问题(无鉴权、明文存账号、未去重、ip/UA)团队**已在
`docs/mvp-acceptance-checklist.md` 第 68–76 行标记为非 MVP 待办**——本报告不重复苛责,
重点是**清单之外的新发现**。

---

## 🔴 严重 —— 财务数据正确性(清单未覆盖)

### 1. 规则引擎只认 `all`(AND),`any`(OR) 被静默忽略 → 规则匹配所有行 ✅已验证
`rule_service.py:60`:`return all(_match_condition(...) for c in conditions.get("all", []))`。
若规则 `conditions_json` 用 `{"any":[...]}` 或任何非 `all` 结构,条件集为空,`all([])==True`,
→ 该规则**匹配每一笔流水**,把其会计科目/借贷方向强行套到全部交易。
验收清单声称"规则健壮性已实现并测试",但此缺口仍在。

### 2. 自定义扩展字段在规则/映射中根本不可用,且注释写反 ✅已验证
`schemas/standard.py:27-29` 注释称"`extra_fields` 进入 `model_dump()` 后规则/映射可用
`field_key` 引用,零代码改动"——错的。`extra_fields` 是嵌套 dict,`model_dump()` 产出
`{"extra_fields": {...}}`,`field_key` 不在顶层。后果:
- 规则按扩展字段取值恒为 `None` → 条件**静默不匹配**,科目规则全失效;
- 映射引用扩展字段时 `mapping_service.py:21` `source not in transaction_data` → **抛错炸整批**。

修法:取值前拍平 `data = txn.model_dump(); data.update(data.pop("extra_fields", {}))`。

### 3. 单行/单配置错误炸掉整批转换
`conversion_service.py` `run_conversion` 主循环对 `build_preview_row`/映射/规则无 try/except,
任一行的 `KeyError`/`ValueError` 中断整批并 500,已解析成功的行全废。
应逐行隔离,失败行产出带异常码的预览行。

### 4. 负数金额导致"方向与净额符号矛盾"
`parser_service.py:527-575` 双栏模式只要 `income!=0` 即判 `CREDIT` 且 `net_amount=income`;
银行在收入栏填负数(冲账/退款)时产出方向与符号自相矛盾的记录,下游汇总全错。
已定义的 `AMOUNT_DIRECTION_MISMATCH` 异常码从未使用。

---

## 🟠 高 —— 健壮性 / 数据完整性(清单未覆盖)

| # | 位置 | 问题 |
|---|------|------|
| 5 | `parser_service.py:457` | CSV 仅按 UTF-8 解码,国内 **GBK/GB2312** 流水直接 `UnicodeDecodeError` 炸整批 |
| 6 | `parser_service.py:661` | 金额清洗只去逗号,不识别 `¥/$`、全角字符、**会计括号负数 `(1,000)`**、`DR/CR` 后缀 |
| 7 | `parser_service.py:225` + `conversion_service.py:592` | 扩展 `date` 字段以**字符串**写入 `Date` 列;SQLite 容忍,**PostgreSQL 会 commit 报错炸批** |
| 8 | `db/session.py` | SQLite **未 `PRAGMA foreign_keys=ON`** ✅已验证,外键形同虚设;配合 `company_id`/`uploaded_by` 由客户端表单任填,可写孤儿/伪造记录 |
| 9 | `routes` + `schemas/conversion.py:35` | 转换入参 `mappings`/`rules` 是 `list[dict[str,Any]]` 无校验;脏输入(缺 `version_id`、非法 `amount_mode`)以 **500 而非 422** 暴露 |
| 10 | `models/builtin_field_override.py` vs `migrations/0003` | **模型缺 `created_at` 而迁移有** ✅已验证;且集成测试用 `create_all` 从不跑迁移,这类漂移无自动防线 |
| 11 | `confirmation_service.py:57` | 可确认 `PARSE_FAILED`/缺必填/冲突行,绕过修正,可能导出空/垃圾分录;人工调整把金额按**字符串**落库且不清异常码/不改状态 |

---

## 🟠 高 —— 前端功能正确性(清单未覆盖)

### 12. 批次详情页写死 4 个日记账列
`ConversionRunDetailPage.tsx:29` 预览表、导出、修改弹窗全硬编码 `['日期','摘要','科目','金额']`。
用户在 `JournalColumnsEditor` 自定义的列(借方/贷方/部门等)在预览页**完全不可见、也导不出**。
应从 run 关联的日记账模板版本动态推导列。

### 13. 映射编辑页丢失字段选项
`MappingProfileDetailPage.tsx:211` 的 `<MappingEditor>` 未传 `standardFieldOptions/targetOptions/
ruleOutputOptions`(新建页有传)。编辑既有方案时扩展字段从下拉消失、`rule_output` 选不到,
→ 用户可能"看丢"甚至误删扩展字段映射。

### 14. 上传文件状态不同步
`UploadPage.tsx` `sourceFileIds` 与 `fileList` 分离:UI 删文件后 id 仍留在转换列表,
仍会送已删文件去解析;重复拖入会累积重复 id。

### 15. 多租户/操作人全站硬编码
`company-1`/`user-1` 散落 10+ 文件(`api/files.ts`、各 page)。虽与"无鉴权"(已知)相关,
但散落定义本身是维护隐患,接入登录需逐个改。建议抽 `currentCompanyId()/currentActor()` 单一来源。

---

## 🟡 中 —— 性能 / 工程质量

- **无分页 + 无索引 + 列表层 N+1**:`get_conversion_run` 一次 load 整批预览行(可达数千行);
  4 个 `list_*` 端点 N+1 取最新版本;全库零索引。真实流水体量下成瓶颈。
- **前端零代码分割**:`routes.tsx` 静态 import 全部 12 页 → 单 chunk 1.3MB(`React.lazy` 完全未用)。
- **React key 用数组下标**:`JournalColumnsEditor/MappingEditor/RuleEditor` 等**可增删重排**的列表用
  `key={i}`,删除/重排会致输入框焦点错位、显示旧值。
- **前端静默吞错**:7+ 处 `catch(()=>setRows([]))`,把网络/500 错误伪装成"暂无数据",
  浪费了已有的统一错误拦截器。
- **批量确认串行 `await`**:选 100 行 = 100 个串行往返,失败静默跳过。
- 文案 bug:`DetectResultView.tsx:59` 输出"从第 **第 5 行 行** 开始读取"
  (`rowIndexOf` 已含"第…行"又被包了一层)。

## 🟢 低(选摘)
- `audit.py` `response_model=list[Any]` 等于无 schema 保护;审计接口无分页、回吐完整快照。
- `api/conversionRuns.ts` `createConversionRun` 整段硬编码死代码(无调用方),建议删。
- `core/config.py` `secret_key` 定义后**全库零引用**;`enums.py` `RecordStatus` 死代码,模型 status 用裸字符串。
- 颜色十六进制散落绕过 `theme.ts` palette(含非品牌色 `#ff4d4f`)。
- `reorder_rules` 审计粒度粗(`entity_id` 把所有 rule_id 拼一串)。

---

## 已知且已记录为非 MVP(不另计入)
无鉴权/RBAC、账号字段明文(命名却叫 `*_encrypted`)、去重哈希/余额连续性未实现
(`row_hash` ✅已验证从不赋值)、大文件异步、ip/UA 捕获、PostgreSQL 实测、bundle 拆分——
均在 `mvp-acceptance-checklist.md` 第 68–76 行列明。

---

## 测试覆盖缺口
- 解析引擎已定义未实现的异常码(去重/余额)无实现亦无测试。
- 脏输入 → 422 路径(非法 amount_mode、缺 version_id)无测试(目前 500)。
- 磁盘文件缺失、并发确认/调整竞态、对已导出批次/PARSE_FAILED 行确认,均无测试。
- 版本不可变性只测了"编辑=建新版本",未断言旧版本行不被改动。
- 迁移**从不真实执行**(集成测试用 `create_all`);契约测试只抽查 0001 少数列,
  未覆盖 `custom_fields`/`builtin_field_overrides`。

---

## 建议修复优先级
1. **立即**(财务正确性,改动小影响大):#1 规则 `any`、#2 扩展字段拍平(并修正错误注释)、
   #3 逐行隔离、#4 负数方向。
2. **近期**:#5 GBK、#6 金额清洗、#7 date 类型、#8 SQLite 外键、#9 入参强类型校验、
   #12/#13 前端列与编辑选项。
3. **排期**:分页 + 索引、代码分割、key 修复、吞错处理、迁移契约测试升级为 `compare_metadata`。
