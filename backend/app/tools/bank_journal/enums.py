from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class TransactionDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class AmountMode(StrEnum):
    SINGLE_AMOUNT_WITH_DIRECTION = "single_amount_with_direction"
    DEBIT_CREDIT_COLUMNS = "debit_credit_columns"
    INCOME_EXPENSE_COLUMNS = "income_expense_columns"
    SIGNED_AMOUNT = "signed_amount"


class PreviewStatus(StrEnum):
    NEEDS_CONFIRMATION = "needs_confirmation"
    AUTO_CONFIRMED = "auto_confirmed"
    MANUALLY_CONFIRMED = "manually_confirmed"
    CONFLICT = "conflict"
    PARSE_FAILED = "parse_failed"
    IGNORED = "ignored"


class ExceptionCode(StrEnum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_DATE = "INVALID_DATE"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    UNKNOWN_DIRECTION = "UNKNOWN_DIRECTION"
    AMOUNT_DIRECTION_MISMATCH = "AMOUNT_DIRECTION_MISMATCH"
    RULE_CONFLICT = "RULE_CONFLICT"
    NO_RULE_MATCH = "NO_RULE_MATCH"
    DUPLICATE_IN_BATCH = "DUPLICATE_IN_BATCH"
    DUPLICATE_HISTORY = "DUPLICATE_HISTORY"
    BALANCE_DISCONTINUITY = "BALANCE_DISCONTINUITY"
    TEMPLATE_NOT_MATCHED = "TEMPLATE_NOT_MATCHED"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
