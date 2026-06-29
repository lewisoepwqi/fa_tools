from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import session as db_session
from app.db.base import Base
from app.main import app

# Import all models so their tables register on Base.metadata before create_all.
# 共享层模型 + 工具层模型（bank_journal）。
from app.models import audit, company, file, user  # noqa: F401
from app.models.company import BankAccount, Company
from app.models.file import SourceFile
from app.models.user import User
from app.tools.bank_journal import models  # noqa: F401  bank_journal 工具模型
from app.tools.bank_journal.models.mapping import MappingProfile, MappingProfileVersion
from app.tools.bank_journal.models.rule import Rule, RuleVersion
from app.tools.bank_journal.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)


def _seed_test_parents(session_local: sessionmaker) -> None:  # type: ignore[type-arg]
    """集成测试所需的父表行（FK 约束开启后子表必须先有父行才能插入）。

    按 FK 依赖分层 flush，确保每层插入时其父行已落库：
    - Layer 1: companies、users（无 FK 依赖）
    - Layer 2: bank_accounts、source_files（依赖 companies/users）
    - Layer 3: bank_templates、company_journal_templates、rules、mapping_profiles（依赖 companies）
    - Layer 4: bank_template_versions、journal_template_versions、rule_versions、
               mapping_profile_versions（依赖 Layer 3）

    所有集成测试共用这些固定 ID，无需在各测试里单独创建。
    """
    db = session_local()
    try:
        # Layer 1
        db.add(Company(id="company-1", name="测试公司一", status="active"))
        db.add(Company(id="company-2", name="测试公司二", status="active"))
        db.add(
            User(
                id="user-1",
                email="tester@example.com",
                name="测试用户",
                password_hash="placeholder",
                status="active",
            )
        )
        db.flush()

        # Layer 2
        db.add(
            BankAccount(
                id="bank-account-1",
                company_id="company-1",
                bank_name="中国银行",
                account_name="测试账户",
                account_no_encrypted="encrypted-placeholder",
                currency="CNY",
                status="active",
            )
        )
        # source_files 行供 bank_template_versions.sample_file_id 引用
        db.add(
            SourceFile(
                id="file-1",
                company_id="company-1",
                original_filename="sample.csv",
                file_type="csv",
                storage_key="file-1.csv",
                status="active",
            )
        )
        db.flush()

        # Layer 3：各类模板/规则父行
        db.add(
            BankTemplate(id="bt-1", company_id="company-1", name="测试银行模板", status="active")
        )
        db.add(
            CompanyJournalTemplate(
                id="cjt-1", company_id="company-1", name="测试日记账模板", status="active"
            )
        )
        db.add(
            MappingProfile(id="mp-1", company_id="company-1", name="测试映射配置", status="active")
        )
        # 规则父行（三组，对应测试中使用的不同 rule_id）
        db.add(Rule(id="rule-1", company_id="company-1", name="规则一", status="active"))
        db.add(Rule(id="r1", company_id="company-1", name="规则 r1", status="active"))
        db.add(Rule(id="rule-auto", company_id="company-1", name="自动确认规则", status="active"))
        db.flush()

        # Layer 4：各类版本行（依赖 Layer 3 的父行）
        db.add(
            BankTemplateVersion(
                id="btv-1",
                bank_template_id="bt-1",
                version_no=1,
                file_type="csv",
                amount_mode="income_expense_columns",
            )
        )
        db.add(
            BankTemplateVersion(
                id="btv-snapshot-1",
                bank_template_id="bt-1",
                version_no=2,
                file_type="csv",
                amount_mode="income_expense_columns",
            )
        )
        db.add(
            CompanyJournalTemplateVersion(
                id="cjtv-1",
                company_journal_template_id="cjt-1",
                version_no=1,
                file_type="csv",
            )
        )
        db.add(
            CompanyJournalTemplateVersion(
                id="cjtv-snapshot-1",
                company_journal_template_id="cjt-1",
                version_no=2,
                file_type="csv",
            )
        )
        db.add(
            MappingProfileVersion(
                id="mpv-1",
                mapping_profile_id="mp-1",
                version_no=1,
            )
        )
        db.add(
            MappingProfileVersion(
                id="mpv-snapshot-1",
                mapping_profile_id="mp-1",
                version_no=2,
            )
        )
        db.add(RuleVersion(id="rule-version-1", rule_id="rule-1", version_no=1))
        db.add(RuleVersion(id="rv1", rule_id="r1", version_no=1))
        db.add(RuleVersion(id="rule-version-auto", rule_id="rule-auto", version_no=1))
        db.commit()
    finally:
        db.close()


def _create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _seed_test_parents(test_session_local)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client_with_db() -> Generator[tuple[TestClient, Session], None, None]:
    """Yields (test_client, db_session) sharing the same in-memory SQLite engine.

    Use when a test needs to query the DB directly after an API call to assert
    on persisted rows (e.g., verifying no orphan BankTransaction rows exist).
    """
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _seed_test_parents(test_session_local)

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session.get_db] = override_get_db
    probe_db = test_session_local()
    try:
        with TestClient(app) as test_client:
            yield test_client, probe_db
    finally:
        probe_db.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
