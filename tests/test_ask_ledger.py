import pytest

from app.db.session import make_engine_and_session
from app.ledger.service import PredictionLedgerService

FIELDS = {
    "entry_id": "ASK-DEDUPE",
    "user_id": "U1",
    "statement_id": "RULE_PARASHARI_CAREER_10H_4_7",
    "rule_id": "RULE_PARASHARI_CAREER_10H",
    "statement_text": "Steady professional progress is supported through planning.",
    "confidence_grade": "supported",
    "time_window": "Active Moon-Ketu Dasha (until 2027-08-12)",
    "observable_outcome_criteria": "Role changed by window end.",
    "safety_category": "life_area",
}


def test_register_or_get_dedupes_in_memory() -> None:
    svc = PredictionLedgerService()
    first = svc.register_or_get(**FIELDS)
    assert svc.register_or_get(**FIELDS).registered_at_utc == first.registered_at_utc
    assert len(svc._all_entries(user_id="U1")) == 1


def test_register_or_get_preserves_a_logged_outcome() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    svc = PredictionLedgerService(session_factory=sf)
    svc.register_or_get(**FIELDS)
    svc.mark_outcome("ASK-DEDUPE", "hit")
    again = svc.register_or_get(**FIELDS)
    assert again.user_outcome == "hit"
    assert len(svc._all_entries(user_id="U1")) == 1


def test_register_or_get_rejects_entry_id_owned_by_another_user() -> None:
    _, sf = make_engine_and_session("sqlite+pysqlite:///:memory:")
    svc = PredictionLedgerService(session_factory=sf)
    first = svc.register_or_get(**FIELDS)
    before = {e.entry_id: e for e in svc._all_entries()}["ASK-DEDUPE"]
    with pytest.raises(ValueError, match="entry id belongs to another user"):
        svc.register_or_get(**{**FIELDS, "user_id": "U2"})
    after = {e.entry_id: e for e in svc._all_entries()}["ASK-DEDUPE"]
    assert after.user_id == first.user_id
    assert after.registered_at_utc == before.registered_at_utc
