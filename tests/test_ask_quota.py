from datetime import date

from app.db.repo import AskQuotaStatus, PrivacyRepo


def _repo() -> PrivacyRepo:
    return PrivacyRepo("sqlite+pysqlite:///:memory:")


def _consume(
    repo: PrivacyRepo,
    *,
    user_id: str = "U1",
    week_start: date = date(2026, 11, 16),
    asked_on: date = date(2026, 11, 16),
    weekly_limit: int = 7,
    daily_limit: int = 1,
) -> AskQuotaStatus:
    return repo.consume_ask_quota(
        user_id=user_id,
        week_start=week_start,
        asked_on=asked_on,
        weekly_limit=weekly_limit,
        daily_limit=daily_limit,
    )


def test_eighth_question_in_a_week_is_refused() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    results = [
        _consume(repo, week_start=week, asked_on=week, weekly_limit=7, daily_limit=0)
        for _ in range(8)
    ]
    assert results == [AskQuotaStatus.ALLOWED] * 7 + [AskQuotaStatus.WEEKLY_EXHAUSTED]


def test_second_question_on_the_same_day_is_refused_before_the_weekly_cap() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    monday = week
    tuesday = date(2026, 11, 17)
    assert _consume(repo, week_start=week, asked_on=monday) is AskQuotaStatus.ALLOWED
    assert (
        _consume(repo, week_start=week, asked_on=monday) is AskQuotaStatus.DAILY_EXHAUSTED
    )
    assert _consume(repo, week_start=week, asked_on=tuesday) is AskQuotaStatus.ALLOWED


def test_quota_is_per_user_and_per_week() -> None:
    repo = _repo()
    this_week = date(2026, 11, 16)
    next_week = date(2026, 11, 23)
    assert (
        _consume(repo, user_id="U1", week_start=this_week, weekly_limit=1, daily_limit=0)
        is AskQuotaStatus.ALLOWED
    )
    assert (
        _consume(repo, user_id="U1", week_start=this_week, weekly_limit=1, daily_limit=0)
        is AskQuotaStatus.WEEKLY_EXHAUSTED
    )
    assert (
        _consume(repo, user_id="U2", week_start=this_week, weekly_limit=1, daily_limit=0)
        is AskQuotaStatus.ALLOWED
    )
    assert (
        _consume(repo, user_id="U1", week_start=next_week, asked_on=next_week, weekly_limit=1)
        is AskQuotaStatus.ALLOWED
    )


def test_zero_limits_are_unlimited_and_write_nothing() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    for _ in range(5):
        assert (
            _consume(repo, week_start=week, weekly_limit=0, daily_limit=0)
            is AskQuotaStatus.ALLOWED
        )


def test_quota_rows_are_purged_on_user_deletion() -> None:
    repo = _repo()
    week = date(2026, 11, 16)
    assert _consume(repo, week_start=week, weekly_limit=1, daily_limit=0) is AskQuotaStatus.ALLOWED
    assert (
        _consume(repo, week_start=week, weekly_limit=1, daily_limit=0)
        is AskQuotaStatus.WEEKLY_EXHAUSTED
    )
    repo.delete_user(user_id="U1")
    assert _consume(repo, week_start=week, weekly_limit=1, daily_limit=0) is AskQuotaStatus.ALLOWED
