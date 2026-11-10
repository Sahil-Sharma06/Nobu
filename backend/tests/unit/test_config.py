import pytest

from nobu.config import Settings


def test_dry_run_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOBU_DRY_RUN", raising=False)
    s = Settings(_env_file=None)
    assert s.dry_run is True
    assert s.daily_cap == 15
    assert s.dedupe_days == 60
    assert s.llm_provider == "stub"


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOBU_DRY_RUN", "false")
    monkeypatch.setenv("NOBU_LLM_MODEL", "some-model")
    s = Settings(_env_file=None)
    assert s.dry_run is False
    assert s.llm_model == "some-model"


def test_data_dir_is_anchored_to_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    from nobu.config import REPO_ROOT

    monkeypatch.setenv("NOBU_DATA_DIR", "../data")
    monkeypatch.chdir(REPO_ROOT.parent)  # run from somewhere else entirely
    assert Settings(_env_file=None).data_dir == REPO_ROOT / "data"
