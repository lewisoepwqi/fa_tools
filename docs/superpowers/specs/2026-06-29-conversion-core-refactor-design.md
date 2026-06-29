# 设计:转换核心重构(W0 领域模型 + W1 转换管道)

> 日期:2026-06-29 · 状态:已通过头脑风暴评审,待用户复核
> 范围:**仅 W0 + W1**。W2(API 健壮性)、W3(安全/多租户)、W4(数据运维)、W5(前端)各自后续单独 spec。
> 背景依据:`docs/code-review-2026-06-29.md`、`docs/technical-design-bank-statement-journal.md`、`docs/gap-analysis.md`。

## 0. 战略定位(已确认)

- **总体策略:深度重构**——既有架构(工具隔离 / 版本化 / 批次快照 / 服务层纯函数 / 数据模型)在设计上是扎实的,
  审查发现的几乎都是实现层 bug 与缺口,不是架构错误。保留架构骨架,系统性重建薄弱子系统。
- **目标成熟度:准生产硬化**——财务正确性与健壮性做到生产级。
- 本 spec 是六工作流(W0–W5)中的前两个,执行顺序 **W0 → W1 → W2 →(W3 ∥ W5)→ W4**。

## 1. 问题根因(为何不是打补丁)

bug #1(规则只认 `all`,`any` 被静默忽略 → 匹配所有行)与 #2(自定义扩展字段在规则/映射中不可用,
注释却声称可用)**同源**:规则/映射引擎看到的"求值上下文"是隐式、临时用 `model_dump()` 拼的,
自定义字段埋在嵌套 `extra_fields` 里,引擎不会遍历。bug #3(单行错误炸整批)源于大循环无错误隔离结构。
bug #4(负数→方向与符号矛盾)源于金额方向无统一值对象。

架构最优解:引入显式的领域层,把"求值上下文""条件 AST""金额方向"升级为一等公民,
把转换流程重构为纯阶段管道。

## 2. W0 领域模型与契约基座

新增纯领域层 `app/tools/bank_journal/domain/`(无 DB、无 IO);`services/` 退化为薄编排层。

### 2.1 字段命名空间 + 求值上下文(治本 #2)

```python
# domain/fields.py
class FieldType(StrEnum): STRING; DECIMAL; DATE; BOOL
@dataclass(frozen=True)
class FieldDef:
    key: str
    type: FieldType
    origin: Literal["standard", "custom"]

class EvaluationContext:
    """标准字段 + 自定义字段拍平进单一命名空间,带类型化访问。"""
    def get(self, key: str) -> Decimal | date | str | bool | None: ...
    def has(self, key: str) -> bool: ...
```

- 标准字段与自定义字段**同权**:`context.get("cost_center")` 与 `context.get("amount")` 一视同仁。
- **取舍(已确认)**:单一扁平命名空间 + 自定义字段 key 创建时**校验不与标准字段冲突**
  (收口 `custom_field_service`),而非加 `custom.` 前缀——对现有配置最友好,不改配置格式。
- 类型随字段元数据携带 → 操作符做类型感知比较。

### 2.2 条件 AST(治本 #1,顺带补 gap P1-5 日期区间)

```python
# domain/conditions.py —— 递归结构,Pydantic 判别联合 + 纯求值器
AllNode  = {"all":  [Condition, ...]}     # AND
AnyNode  = {"any":  [Condition, ...]}     # OR  ← 当前被静默忽略
NotNode  = {"not":  Condition}
Leaf     = {"field": str, "op": Operator, "value": Any}
# Operator: eq ne gt gte lt lte contains contains_any in between is_empty regex
def evaluate(node: Condition, ctx: EvaluationContext) -> bool: ...
```

- **向后兼容**:旧 `{"all":[...]}` 是新 AST 合法子集,历史规则不受影响。
- 未知结构 → **校验期报错**,绝不退化成"匹配全部"。
- **操作符集合(已确认)**:上列集合作为基线;`between` 覆盖日期/数值区间。

### 2.3 强类型 Rule / Mapping 契约(治本 #9 的根)

```python
# domain/contracts.py
class Rule(BaseModel):
    id: str; version_id: str; priority: int
    conditions: Condition
    actions: list[Action]
    allow_auto_confirm: bool
class Mapping(BaseModel):
    target: str
    source: FieldRef | Concat | Conditional | Constant   # 判别联合,含 conditional(补 gap P1-6)
```

把 `ConversionRunCreate.mappings/rules` 的 `list[dict[str, Any]]` 替换为以上模型,校验前移。

### 2.4 金额/方向值对象(治本 #4)

```python
# domain/amounts.py
class Direction(StrEnum): DEBIT; CREDIT
@dataclass(frozen=True)
class SignedAmount:
    magnitude: Decimal      # 恒 >= 0
    direction: Direction
    # 工厂:从单栏带符号 / 双栏收支 / 双栏借贷构造,统一处理负数翻转方向;
    # 负数导致方向矛盾 → 产出 AMOUNT_DIRECTION_MISMATCH(启用已定义未用的异常码)。
```

### 2.5 W0 产物
`domain/{fields,conditions,contracts,amounts}.py` + 各自单测;
`schemas/standard.py` 写反的注释删除/更正。

## 3. W1 转换管道重构

把 `conversion_service` 从"大循环临时拼"重构为纯阶段序列,逐行独立流过,错误隔离成结构性保证。

### 3.1 Result 类型(治本 #3)

```python
# domain/pipeline.py
@dataclass
class RowOutcome:
    value: PreviewRow | None
    errors: list[ExceptionCode]      # 非空即异常行,绝不中断批次
```

每阶段签名 `(input, ctx) -> RowOutcome`;阶段内部捕获自身异常 → 转 `ExceptionCode`,**永不向上抛**。

### 3.2 阶段序列

```
原始文件
 └─[S1 解码读取]→ 原始行列表
   └─[S2 解析行]→ StandardTransaction | ParseError    (逐行)
     └─[S3 去重/余额]→ 打 DUPLICATE_*/BALANCE_*        (跨行)
       └─[S4 映射]→ 日记账输出 dict                     (逐行)
         └─[S5 规则求值]→ 科目/方向/确认标志            (逐行)
           └─[S6 组装预览行]→ PreviewRow + 异常码 + 状态
```

| 阶段 | 职责 | 修复项 |
|------|------|--------|
| S1 解码读取 | 编码探测(UTF-8/GBK/GB18030);Excel/CSV 统一为行数组;合并单元格、重复表头处理 | #5,表头覆盖 |
| S2 解析行 | 表头映射→标准字段;金额清洗(`¥/$`、全角、会计括号负数、`DR/CR`);日期解析**保留 `date` 对象**;经 `SignedAmount` 定方向 | #4,#6,#7 |
| S3 去重/余额 | 按 `unique_key_config` 算 `row_hash`,批内 + 历史查重;余额连续性 | gap P1-3,实装 `row_hash` |
| S4 映射 | 经 `EvaluationContext` + 类型化 `Mapping` 产出输出列(含 conditional) | #2,gap P1-6 |
| S5 规则求值 | 经条件 AST + 上下文;优先级解析 + 冲突检测(`RULE_CONFLICT`) | #1,#2 |
| S6 组装 | 汇总输出 + 异常码 + 计算行状态 | — |

### 3.3 纯编排 + 薄持久化

```python
# domain/pipeline.py —— 纯函数,无 DB;S3 历史去重经注入的查询函数
def run_pipeline(raw_file, config_snapshot, history_lookup=...) -> list[RowOutcome]: ...

# services/conversion_service.py —— 薄层:取版本快照 → run_pipeline → 落库
```

- **取舍(已确认)**:S3 历史去重用"注入查询函数"保持 domain 纯净(domain 接口多一回调参数),
  而非把去重整段放进 service 层。
- `config_snapshot` 是已解析的版本快照(模板/映射版本/规则版本),沿用现有批次快照机制。

### 3.4 边界约束

- **只影响新转换**:历史批次 `output_values_json` 快照原样可读,版本不可变性保持。
- **大文件**:S1/S2 设计成可迭代(generator),为 W4 异步/流式留口;W1 先同步实现。

## 4. 测试策略

W0/W1 当前测试空白,最高优先补。

- **W0 纯单测**:条件求值器(`all/any/not` 嵌套、每操作符、类型强制、未知结构报错);
  EvaluationContext(标准+自定义同权、缺失、冲突校验);SignedAmount(三种构造、负数翻向、矛盾→异常码)。
- **W1 阶段测 + 黄金文件端到端**:每阶段独立测含错误路径;fixtures 覆盖 **GBK 编码**、
  **会计括号负数**、**自定义字段驱动的科目规则**、**`any` 规则**、重复行、余额跳变;
  断言单行坏数据**不影响**同批其他行(错误隔离回归)。
- **回归护栏**:重构期间现有 138 后端测试 + 7 e2e 全程保持绿;每工作流 TDD(先红后绿)。

## 5. 向后兼容(硬约束)

- 历史批次 `output_values_json` / 各 `*_version` 快照**只读不动**,版本不可变性保持。
- 旧配置 `conditions_json = {"all":[...]}` 是新 AST 合法子集 → 历史规则继续工作。
- API 契约形状尽量保持;入参从 `dict[str,Any]` 收紧为强类型属**收紧而非破坏**(非法输入本就该 422)。

## 6. 模块布局与迁移

```
tools/bank_journal/
  domain/                 # 新增,纯领域层(无 DB/IO)
    fields.py             # FieldDef + EvaluationContext
    conditions.py         # 条件 AST + evaluate()
    contracts.py          # Rule/Mapping/Action/Condition 强类型
    amounts.py            # SignedAmount / Direction
    pipeline.py           # RowOutcome + run_pipeline()(注入 history_lookup)
    parsing.py            # S1/S2 解码、金额/日期清洗
  services/               # 退化为薄编排层
    conversion_service.py # 取快照 → run_pipeline → 落库
    rule_service.py / mapping_service.py / parser_service.py  # 迁移到 domain,旧入口保留转调
  schemas/standard.py     # 删除/更正写反的注释
```

迁移策略:`domain/` 先建并单测 → `services/` 旧函数改为转调 domain(保持现有测试绿)→ 逐步删薄。

## 7. 验收标准

- [ ] 规则支持 `all/any/not` 嵌套;`any` 规则按 OR 正确匹配;空/未知条件**不再**匹配全部(#1)。
- [ ] 自定义字段可作为规则条件与映射来源正常工作;`standard.py` 注释更正(#2)。
- [ ] 单行解析/映射/规则错误**不中断**整批,产出带异常码的预览行(#3)。
- [ ] 负数金额正确翻转方向或标记 `AMOUNT_DIRECTION_MISMATCH`(#4)。
- [ ] GBK/GB18030 CSV 正常解析(#5);货币符号、全角、会计括号负数、`DR/CR` 正确识别(#6)。
- [ ] 扩展 `date` 字段以 `date` 对象落库,PostgreSQL 不报类型错(#7)。
- [ ] `row_hash` 计算并落库;批内/历史去重与余额连续性产出对应异常码(gap P1-3)。
- [ ] `conditional` 映射类型可用(gap P1-6)。
- [ ] 现有 138 后端测试 + 7 e2e 全绿;新增 W0/W1 单测与黄金文件测试通过。
- [ ] 历史批次详情与导出不受影响(版本不可变性回归通过)。

## 8. 不在本 spec 范围(后续工作流)

W2 分页/索引/422 收口 · W3 鉴权/RBAC/租户/加密/FK pragma · W4 迁移契约/PG 实测/异步 · W5 前端重构。
