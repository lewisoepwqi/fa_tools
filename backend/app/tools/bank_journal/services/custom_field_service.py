"""公司级标准字段业务逻辑：扩展字段 CRUD + 内置字段覆盖。

- 扩展字段 CRUD（槽位分配/占用校验、唯一性校验、引用拦截）
- 内置字段覆盖 CRUD（label / 识别关键词 / 规则类型，公司级）
- load_custom_field_defs / load_builtin_keyword_overrides：供 conversion_service / detect 复用
- get_standard_schema：合并内置字段（含覆盖）+ 公司扩展字段，供前端下拉
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import RecordStatus
from app.tools.bank_journal.models.builtin_field_override import BuiltinFieldOverride
from app.tools.bank_journal.models.custom_field import (
    AMOUNT_SLOTS,
    DATE_SLOTS,
    SLOTS_BY_TYPE,
    TEXT_SLOTS,
    CustomField,
)
from app.tools.bank_journal.schemas.custom_field import (
    ALLOWED_TYPES,
    BUILTIN_FIELD_KEYS,
    BUILTIN_KEYWORDS,
    BUILTIN_LABELS,
    BUILTIN_STANDARD_FIELDS,
    BUILTIN_TYPES,
    BuiltinFieldOverrideResponse,
    BuiltinFieldOverrideUpsert,
    CustomFieldCreate,
    CustomFieldResponse,
    CustomFieldUpdate,
    StandardFieldDef,
    StandardSchemaResponse,
)
from app.tools.bank_journal.services.parser_service import CustomFieldDef

ALLOWED_DATA_TYPES = {"text", "amount", "date"}
ALLOWED_STATUSES = {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}

# 每种 data_type 的预分配槽位总数（用于配额计算）
SLOT_TOTALS = {
    "text": len(TEXT_SLOTS),
    "amount": len(AMOUNT_SLOTS),
    "date": len(DATE_SLOTS),
}


def _to_response(cf: CustomField) -> CustomFieldResponse:
    return CustomFieldResponse(
        id=cf.id,
        company_id=cf.company_id,
        field_key=cf.field_key,
        name=cf.name,
        slot_key=cf.slot_key,
        data_type=cf.data_type,
        header_keywords=list(cf.header_keywords_json or []),
        status=cf.status,
    )


def list_custom_fields(
    db: Session, company_id: str | None = None
) -> list[CustomFieldResponse]:
    query = db.query(CustomField)
    if company_id is not None:
        query = query.filter(CustomField.company_id == company_id)
    query = query.filter(CustomField.status != RecordStatus.DELETED.value)
    return [_to_response(r) for r in query.all()]


def _get_or_404(db: Session, field_id: str) -> CustomField:
    cf = db.query(CustomField).filter(CustomField.id == field_id).first()
    if cf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    return cf


def _used_slots(db: Session, company_id: str, data_type: str) -> set[str]:
    """该公司某类型已被占用的槽位（含软删除行——删除不回收槽位，符合强类型列约束）。

    与方案边界一致：删除扩展字段不回收预分配列，只清业务数据/引用。
    因此即使软删除，slot_key 仍占用该槽位的唯一约束，重建会分配到下一个空闲槽位。
    """
    allowed = SLOTS_BY_TYPE[data_type]
    rows = (
        db.query(CustomField.slot_key)
        .filter(
            CustomField.company_id == company_id,
            CustomField.data_type == data_type,
        )
        .all()
    )
    return {r[0] for r in rows if r[0] in allowed}


def _allocate_slot(db: Session, company_id: str, data_type: str) -> str:
    """分配一个空闲槽位；无空闲则 409。"""
    used = _used_slots(db, company_id, data_type)
    for slot in SLOTS_BY_TYPE[data_type]:
        if slot not in used:
            return slot
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        detail=f"No free {data_type} slots (cap {SLOT_TOTALS[data_type]}). "
        "Delete an existing custom field or extend the schema.",
    )


def create_custom_field(db: Session, payload: CustomFieldCreate) -> CustomFieldResponse:
    # 1) field_key 公司内唯一 + 不与内置字段冲突。
    # 注意：唯一性含软删除行（与 DB 约束一致）——field_key 历史不可复用，
    # 否则同 field_key 在历史行（ext_text_1）与新行（ext_text_2）语义错乱。
    if payload.field_key in BUILTIN_FIELD_KEYS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"field_key '{payload.field_key}' conflicts with a built-in field",
        )
    existing = (
        db.query(CustomField)
        .filter(
            CustomField.company_id == payload.company_id,
            CustomField.field_key == payload.field_key,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="field_key already exists in this company (incl. deleted; "
            "field keys are not reusable for data-safety)",
        )
    # 2) name 公司内唯一（仅看非删除行——name 可复用，仅展示用）
    name_dup = (
        db.query(CustomField)
        .filter(
            CustomField.company_id == payload.company_id,
            CustomField.name == payload.name,
            CustomField.status != RecordStatus.DELETED.value,
        )
        .first()
    )
    if name_dup is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="name already exists in this company")
    # 3) 分配槽位
    slot = _allocate_slot(db, payload.company_id, payload.data_type)
    cf = CustomField(
        id=str(uuid.uuid4()),
        company_id=payload.company_id,
        field_key=payload.field_key,
        name=payload.name,
        slot_key=slot,
        data_type=payload.data_type,
        header_keywords_json=payload.header_keywords,
        status=RecordStatus.ACTIVE.value,
        created_by=payload.created_by,
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return _to_response(cf)


def update_custom_field(
    db: Session, field_id: str, payload: CustomFieldUpdate
) -> CustomFieldResponse:
    cf = _get_or_404(db, field_id)
    if payload.name is not None:
        # name 唯一性（排除自身）
        dup = (
            db.query(CustomField)
            .filter(
                CustomField.company_id == cf.company_id,
                CustomField.name == payload.name,
                CustomField.id != field_id,
                CustomField.status != RecordStatus.DELETED.value,
            )
            .first()
        )
        if dup is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="name already exists")
        cf.name = payload.name
    if payload.header_keywords is not None:
        cf.header_keywords_json = payload.header_keywords
    if payload.status is not None:
        if payload.status.value not in ALLOWED_STATUSES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        cf.status = payload.status.value
    db.commit()
    db.refresh(cf)
    return _to_response(cf)


def delete_custom_field(db: Session, field_id: str) -> None:
    """软删除。被规则/映射引用时拦截（409）。

    规则/映射的引用检测较复杂（JSON 内 field 名），这里做保守的字符串包含检测：
    若任何 active 规则的 conditions_json/actions_json 文本、或映射的 mappings_json 文本
    包含该 field_key，则视为被引用。宁可误拦（保守）。
    """
    cf = _get_or_404(db, field_id)
    if _is_field_referenced(db, cf):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Custom field '{cf.field_key}' is referenced by rules/mappings; "
            "remove references before deleting",
        )
    cf.status = RecordStatus.DELETED.value
    db.commit()


def _is_field_referenced(db: Session, cf: CustomField) -> bool:
    """保守检测：扫描该公司规则/映射的 JSON 文本是否含 field_key。

    扩展字段数量少、版本数据量可控，按公司扫描 JSON 文本可接受。
    宁可误拦（保守）——若 field_key 作为子串出现在别处，也会被拦，但避免误删。
    """
    import json

    from app.tools.bank_journal.models.mapping import (
        MappingProfile,
        MappingProfileVersion,
    )
    from app.tools.bank_journal.models.rule import Rule, RuleVersion

    key = cf.field_key

    # 规则版本：仅扫该公司规则
    rule_ids = [
        r[0]
        for r in db.query(Rule.id).filter(Rule.company_id == cf.company_id).all()
    ]
    if rule_ids:
        for row in db.query(RuleVersion).filter(RuleVersion.rule_id.in_(rule_ids)).all():
            data = {k: getattr(row, k, None) for k in row.__table__.columns.keys()}
            try:
                text = json.dumps(data, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                continue
            if key in text:
                return True

    # 映射版本：仅扫该公司映射
    mapping_ids = [
        m[0]
        for m in db.query(MappingProfile.id)
        .filter(MappingProfile.company_id == cf.company_id)
        .all()
    ]
    if mapping_ids:
        for row in (
            db.query(MappingProfileVersion)
            .filter(MappingProfileVersion.mapping_profile_id.in_(mapping_ids))
            .all()
        ):
            data = {k: getattr(row, k, None) for k in row.__table__.columns.keys()}
            try:
                text = json.dumps(data, default=str, ensure_ascii=False)
            except (TypeError, ValueError):
                continue
            if key in text:
                return True
    return False


# ---------------------------------------------------------------------------
# 解析期加载 + 合并 schema（供 conversion_service / detect / 前端复用）
# ---------------------------------------------------------------------------


def load_custom_field_defs(db: Session, company_id: str) -> list[CustomFieldDef]:
    """加载公司级扩展字段为解析期轻量视图。"""
    rows = (
        db.query(CustomField)
        .filter(
            CustomField.company_id == company_id,
            CustomField.status == RecordStatus.ACTIVE.value,
        )
        .all()
    )
    return [
        CustomFieldDef(
            field_key=r.field_key,
            slot_key=r.slot_key,
            data_type=r.data_type,
            header_keywords=list(r.header_keywords_json or []),
        )
        for r in rows
    ]


def get_standard_schema(db: Session, company_id: str) -> StandardSchemaResponse:
    """返回内置标准字段（含公司覆盖）+ 公司扩展字段的合并视图，供前端字段下拉。"""
    overrides = load_builtin_overrides(db, company_id)
    fields: list[StandardFieldDef] = []
    for f in BUILTIN_STANDARD_FIELDS:
        key = f["key"]
        ov = overrides.get(key)
        # 关键词：内置默认 ∪ 公司覆盖（union，保留默认不失效）
        base_kws = list(f["keywords"])
        effective_kws = base_kws
        if ov and ov.get("header_keywords_override"):
            extra = [k for k in ov["header_keywords_override"] if k not in base_kws]
            effective_kws = base_kws + extra
        fields.append(
            StandardFieldDef(
                key=key,
                label=(ov["label_override"] if ov and ov.get("label_override") else f["label"]),
                type=(ov["type_override"] if ov and ov.get("type_override") else f["type"]),
                builtin=True,
                keywords=effective_kws,
                overridden=bool(ov),
            )
        )
    # 公司扩展字段
    rows = (
        db.query(CustomField)
        .filter(
            CustomField.company_id == company_id,
            CustomField.status != RecordStatus.DELETED.value,
        )
        .all()
    )
    for r in rows:
        fields.append(
            StandardFieldDef(
                key=r.field_key,
                label=r.name,
                type=r.data_type,
                builtin=False,
                keywords=list(r.header_keywords_json or []),
            )
        )
    # 配额：各扩展字段类型已用/总数（内置字段不占扩展槽位）
    slot_quota: dict[str, dict[str, int]] = {}
    for dt, total in SLOT_TOTALS.items():
        used = len(_used_slots(db, company_id, dt))
        slot_quota[dt] = {"used": used, "total": total}
    return StandardSchemaResponse(fields=fields, slot_quota=slot_quota)


# ---------------------------------------------------------------------------
# 内置字段覆盖
# ---------------------------------------------------------------------------


def load_builtin_overrides(db: Session, company_id: str) -> dict[str, dict]:
    """加载公司级内置字段覆盖。

    返回 {field_key: {label_override, header_keywords_override, type_override}}。
    """
    rows = (
        db.query(BuiltinFieldOverride)
        .filter(BuiltinFieldOverride.company_id == company_id)
        .all()
    )
    return {
        r.field_key: {
            "label_override": r.label_override,
            "header_keywords_override": list(r.header_keywords_override or []),
            "type_override": r.type_override,
        }
        for r in rows
    }


def load_builtin_keyword_overrides(
    db: Session, company_id: str
) -> dict[str, list[str]]:
    """加载公司级内置字段的【识别关键词覆盖】（与内置默认 union），供 parser detect 使用。

    返回 {field_key: 完整关键词列表（内置默认 + 覆盖）}。parser 据此叠加识别。
    """
    overrides = load_builtin_overrides(db, company_id)
    result: dict[str, list[str]] = {}
    for key, base in BUILTIN_KEYWORDS.items():
        ov = overrides.get(key, {})
        extra = ov.get("header_keywords_override") or []
        merged = list(base)
        for k in extra:
            if k not in merged:
                merged.append(k)
        result[key] = merged
    return result


def list_builtin_overrides(
    db: Session, company_id: str
) -> list[BuiltinFieldOverrideResponse]:
    rows = (
        db.query(BuiltinFieldOverride)
        .filter(BuiltinFieldOverride.company_id == company_id)
        .all()
    )
    return [_override_to_response(r) for r in rows]


def _override_to_response(r: BuiltinFieldOverride) -> BuiltinFieldOverrideResponse:
    return BuiltinFieldOverrideResponse(
        id=r.id,
        company_id=r.company_id,
        field_key=r.field_key,
        label_override=r.label_override,
        header_keywords_override=list(r.header_keywords_override or []),
        type_override=r.type_override,
    )


def upsert_builtin_override(
    db: Session, payload: BuiltinFieldOverrideUpsert
) -> BuiltinFieldOverrideResponse:
    # 校验 field_key 必须是内置字段（不是扩展字段）
    if payload.field_key not in BUILTIN_FIELD_KEYS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"'{payload.field_key}' is not a built-in field; use custom-fields API instead",
        )
    # 校验 type_override
    if payload.type_override is not None and payload.type_override not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"type_override must be one of {sorted(ALLOWED_TYPES)}",
        )
    existing = (
        db.query(BuiltinFieldOverride)
        .filter(
            BuiltinFieldOverride.company_id == payload.company_id,
            BuiltinFieldOverride.field_key == payload.field_key,
        )
        .first()
    )
    if existing is None:
        existing = BuiltinFieldOverride(
            id=str(uuid.uuid4()),
            company_id=payload.company_id,
            field_key=payload.field_key,
            label_override=payload.label_override,
            header_keywords_override=payload.header_keywords_override,
            type_override=payload.type_override,
        )
        db.add(existing)
    else:
        existing.label_override = payload.label_override
        existing.header_keywords_override = payload.header_keywords_override
        existing.type_override = payload.type_override
    db.commit()
    db.refresh(existing)
    return _override_to_response(existing)


def delete_builtin_override(db: Session, company_id: str, field_key: str) -> None:
    """删除覆盖即恢复内置默认。"""
    if field_key not in BUILTIN_FIELD_KEYS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"'{field_key}' is not a built-in field"
        )
    row = (
        db.query(BuiltinFieldOverride)
        .filter(
            BuiltinFieldOverride.company_id == company_id,
            BuiltinFieldOverride.field_key == field_key,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Override not found")
    db.delete(row)
    db.commit()


# 抑制未使用 import 警告（BUILTIN_LABELS / BUILTIN_TYPES 保留供未来扩展查询）
_ = BUILTIN_LABELS, BUILTIN_TYPES
