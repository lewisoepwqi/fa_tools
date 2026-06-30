"""本地演示主数据种子脚本（仅用于本地体验，不进迁移链）。

前端 createConversionRun 写死 company_id="company-1"、bank_account_id="bank-account-1"，
而 ConversionRun.company_id 是指向 companies.id 的外键。当前 dev DB 没有这两条主数据，
仅靠 SQLite 默认不强制外键才没报错。本脚本幂等地插入这些主数据，让批次列表能产生真实数据。

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/seed_demo.py

清库后重跑即可重建。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 `app` 包可导入（脚本从 backend/ 目录直接运行）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.company import BankAccount, Company  # noqa: E402

DEMO_COMPANY_ID = "company-1"
DEMO_BANK_ACCOUNT_ID = "bank-account-1"


def seed() -> None:
    db = SessionLocal()
    try:
        company = db.get(Company, DEMO_COMPANY_ID)
        if company is None:
            company = Company(
                id=DEMO_COMPANY_ID,
                name="示例科技有限公司",
                code="DEMO-001",
                status="active",
            )
            db.add(company)
            # 先 flush 落库公司，否则 SQLite 强制外键下 SQLAlchemy 可能把银行账号
            # INSERT 排在公司之前，触发 FOREIGN KEY constraint failed。
            db.flush()
            print(f"[+] 创建公司: {DEMO_COMPANY_ID} ({company.name})")
        else:
            print(f"[=] 公司已存在: {DEMO_COMPANY_ID}")

        account = db.get(BankAccount, DEMO_BANK_ACCOUNT_ID)
        if account is None:
            account = BankAccount(
                id=DEMO_BANK_ACCOUNT_ID,
                company_id=DEMO_COMPANY_ID,
                bank_name="中国银行",
                account_name="示例科技有限公司",
                # MVP 明文存储（见验收清单已知后续项：账号字段加密留待后续）。
                account_no_encrypted="6222000000000000000",
                currency="CNY",
                status="active",
            )
            db.add(account)
            print(f"[+] 创建银行账号: {DEMO_BANK_ACCOUNT_ID} ({account.bank_name})")
        else:
            print(f"[=] 银行账号已存在: {DEMO_BANK_ACCOUNT_ID}")

        db.commit()
        print("[done] 种子数据就绪")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
