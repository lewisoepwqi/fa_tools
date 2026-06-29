from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import audit, company, file, user  # noqa: F401
from app.tools.bank_journal import models  # noqa: F401


def _indexed_columns(insp, table):
    cols = set()
    for ix in insp.get_indexes(table):
        if len(ix["column_names"]) > 1:
            cols.add(tuple(ix["column_names"]))
        else:
            cols.update(ix["column_names"])
    return cols


def test_hot_path_indexes_present():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    # 预览行/交易按 run 过滤
    assert "conversion_run_id" in _indexed_columns(insp, "journal_preview_rows")
    assert "conversion_run_id" in _indexed_columns(insp, "bank_transactions")
    # 去重历史查询热点
    assert "row_hash" in _indexed_columns(insp, "bank_transactions")
    # 版本表复合索引(parent_id, version_no)其一列出现即可
    assert ("bank_template_id", "version_no") in _indexed_columns(insp, "bank_template_versions")
