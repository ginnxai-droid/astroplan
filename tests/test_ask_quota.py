from datetime import date

from app.db.repo import PrivacyRepo


def _repo() -> PrivacyRepo:
    return PrivacyRepo("sqlite+pysqlite:///:memory:")


def test_quota_allows_three_then_blocks() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    results = [repo.consume_ask_quota(user_id="U1", week_start=week, limit=3) for _ in range(4)]
    assert results == [True, True, True, False]


def test_quota_is_per_user_and_per_week() -> None:
    repo = _repo()
    assert repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 16), limit=1)
    assert not repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 16), limit=1)
    assert repo.consume_ask_quota(user_id="U2", week_start=date(2026, 11, 16), limit=1)
    assert repo.consume_ask_quota(user_id="U1", week_start=date(2026, 11, 23), limit=1)


def test_zero_limit_is_unlimited_and_writes_nothing() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    for _ in range(5):
        assert repo.consume_ask_quota(user_id="U1", week_start=week, limit=0)


def test_quota_rows_are_purged_on_user_deletion() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    assert repo.consume_ask_quota(user_id="U1", week_start=week, limit=1)
    assert not repo.consume_ask_quota(user_id="U1", week_start=week, limit=1)
    repo.delete_user(user_id="U1")
    assert repo.consume_ask_quota(user_id="U1", week_start=week, limit=1)
