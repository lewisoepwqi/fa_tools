from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook


def export_preview_rows_to_csv(
    rows: list[dict[str, object]],
    columns: list[str],
    output_dir: Path,
    filename: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def export_preview_rows_to_xlsx(
    rows: list[dict[str, object]],
    columns: list[str],
    output_dir: Path,
    filename: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column) for column in columns])
    workbook.save(path)
    return path


def export_report_to_json(report: dict[str, object], output_dir: Path, filename: str) -> Path:
    """生成处理报告（JSON）。PRD §6.9.7 处理报告 11 项字段。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return path


def validate_required_columns(
    rows: list[dict[str, object]], required_columns: list[str]
) -> list[int]:
    """P0-5: 校验必填字段完整性（PRD §6.9.4）。返回缺失必填字段的行号（1-based）。

    缺失任一必填字段（值为 None 或空串）的行计入违规。
    """
    violations: list[int] = []
    for index, row in enumerate(rows, start=1):
        for column in required_columns:
            value = row.get(column)
            if value is None or value == "":
                violations.append(index)
                break
    return violations
