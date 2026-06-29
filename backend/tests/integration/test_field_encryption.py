"""集成测试：account_no_encrypted / counterparty_account_no_encrypted 列透明加密验证。

测试策略：
- ORM 写入明文 → ORM 读取得到明文（透明解密）
- 原始 SQL 读取同一行 → 得到密文（非明文），证明入库时已加密
"""

from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.models.company import BankAccount, Company
from app.tools.bank_journal.models.conversion import BankTransaction, ConversionRun


def test_account_no_encrypted_at_rest(client_with_db):
    """BankAccount.account_no_encrypted 入库为密文，ORM 读回为明文。"""
    _, db = client_with_db
    company = Company(id=str(uuid4()), name="甲")
    db.add(company)
    db.flush()  # 先落库 company，满足 bank_accounts.company_id FK 约束
    acct = BankAccount(
        id=str(uuid4()),
        company_id=company.id,
        bank_name="工行",
        account_name="甲账户",
        account_no_encrypted="6222021234567890",
    )
    db.add(acct)
    db.commit()
    # ORM 读取 → 明文
    db.refresh(acct)
    assert acct.account_no_encrypted == "6222021234567890"
    # 原始 SQL 读取 → 密文（非明文）
    raw = db.execute(
        text("SELECT account_no_encrypted FROM bank_accounts WHERE id = :i"),
        {"i": acct.id},
    ).scalar()
    assert raw != "6222021234567890"


def test_counterparty_account_no_encrypted_at_rest(client_with_db):
    """BankTransaction.counterparty_account_no_encrypted 入库为密文，ORM 读回为明文。"""
    _, db = client_with_db
    # 借用 conftest 中已 seed 的 company-1、bank-account-1、source_file file-1
    run = ConversionRun(
        id=str(uuid4()),
        company_id="company-1",
        bank_account_id="bank-account-1",
        status="pending",
    )
    db.add(run)
    db.flush()

    txn = BankTransaction(
        id=str(uuid4()),
        conversion_run_id=run.id,
        source_file_id="file-1",
        transaction_date=date(2024, 1, 15),
        currency="CNY",
        counterparty_account_no_encrypted="9999888877776666",
    )
    db.add(txn)
    db.commit()

    # ORM 读取 → 明文
    db.refresh(txn)
    assert txn.counterparty_account_no_encrypted == "9999888877776666"

    # 原始 SQL 读取 → 密文（非明文）
    raw = db.execute(
        text(
            "SELECT counterparty_account_no_encrypted FROM bank_transactions WHERE id = :i"
        ),
        {"i": txn.id},
    ).scalar()
    assert raw != "9999888877776666"


def test_counterparty_account_no_encrypted_nullable(client_with_db):
    """counterparty_account_no_encrypted 为 None 时 ORM 读回仍为 None（透传）。"""
    _, db = client_with_db
    run = ConversionRun(
        id=str(uuid4()),
        company_id="company-1",
        bank_account_id="bank-account-1",
        status="pending",
    )
    db.add(run)
    db.flush()

    txn = BankTransaction(
        id=str(uuid4()),
        conversion_run_id=run.id,
        source_file_id="file-1",
        transaction_date=date(2024, 1, 15),
        currency="CNY",
        counterparty_account_no_encrypted=None,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    assert txn.counterparty_account_no_encrypted is None
