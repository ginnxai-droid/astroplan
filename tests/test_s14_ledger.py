import pytest

from app.db.session import make_engine_and_session
from app.interpretation.errors import GuardrailViolation
from app.ledger.service import PredictionLedgerService

pytestmark = pytest.mark.s14


def test_ledger_register_and_calibrate_in_memory() -> None:
    s = PredictionLedgerService()
    s.register(
        entry_id="L1",
        user_id="U1",
        statement_id="S1",
        rule_id="RULE_PARASHARI_CAREER_10H",
        statement_text="Structured career progress supported.",
        confidence_grade="supported",
        time_window="Q1 2027",
        observable_outcome_criteria="Completed planned milestone.",
    )
    s.mark_outcome("L1", "hit")
    summary = s.calibration_summary(user_id="U1")
    assert summary["scope_user_id"] == "U1"
    assert summary["total_pre_registered"] == 1
    assert summary["counts"]["hit"] == 1  # type: ignore[index]
    assert summary["brier_calibration_score"] is not None


def test_ledger_sql_persistence_survives_across_service_instances() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    writer = PredictionLedgerService(session_factory=sf)
    writer.register(
        entry_id="SQL_L1",
        user_id="U_SQL",
        statement_id="S_SQL",
        rule_id="RULE_PARASHARI_FIN_2H_11H",
        statement_text="Disciplined budget allocation supported.",
        confidence_grade="likely",
        time_window="Q2 2027",
        observable_outcome_criteria="Maintained savings rate.",
    )
    writer.mark_outcome("SQL_L1", "hit")

    reader = PredictionLedgerService(session_factory=sf)
    summary = reader.calibration_summary(user_id="U_SQL")
    assert summary["total_pre_registered"] == 1
    assert summary["counts"]["hit"] == 1  # type: ignore[index]
    assert summary["brier_calibration_score"] == 0.0625


def test_ledger_blocks_fear_text() -> None:
    s = PredictionLedgerService()
    with pytest.raises(GuardrailViolation):
        s.register(
            entry_id="L2",
            user_id="U1",
            statement_id="S2",
            rule_id="R",
            statement_text="You will face death.",
            confidence_grade="likely",
            time_window="Q1",
            observable_outcome_criteria="X",
        )
