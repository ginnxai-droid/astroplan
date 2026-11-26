from app.config import Settings


def test_ask_is_dark_by_default() -> None:
    settings = Settings(env="test")
    assert settings.ask_enabled is False
    assert settings.ask_weekly_free_quota == 7
    assert settings.ask_daily_free_quota == 1
    assert settings.ask_lexicon_path == "rules/ask_lexicon.yaml"


def test_ask_can_be_enabled_for_tests() -> None:
    settings = Settings(
        env="test",
        ask_enabled=True,
        ask_weekly_free_quota=1,
        ask_daily_free_quota=2,
    )
    assert settings.ask_enabled is True
    assert settings.ask_weekly_free_quota == 1
    assert settings.ask_daily_free_quota == 2
