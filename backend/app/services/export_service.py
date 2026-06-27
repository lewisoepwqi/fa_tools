from __future__ import annotations

import csv
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
