"""Settings paths resolve against the repo root, not the working directory."""

from argus.config import REPO_ROOT, Settings

PATH_VARS = ("ARGUS_DATA_DIR", "ARGUS_REPORTS_DIR", "ARGUS_SOURCES_FILE")


def test_default_paths_do_not_depend_on_cwd(monkeypatch, tmp_path):
    """Running run_daily.py from apps/pipeline/ used to die with
    FileNotFoundError: config/sources.yaml because the defaults were
    cwd-relative and only the repo root has config/."""
    for var in PATH_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.sources_file.is_file()
    assert settings.data_dir == REPO_ROOT / "data"
    assert settings.reports_dir == REPO_ROOT / "reports"


def test_env_paths_relative_to_repo_root_absolute_unchanged(monkeypatch, tmp_path):
    """.env.example ships relative values (ARGUS_DATA_DIR=data), so fixing
    only the defaults would leave a copied .env cwd-dependent."""
    monkeypatch.setenv("ARGUS_DATA_DIR", "data")
    monkeypatch.setenv("ARGUS_REPORTS_DIR", str(tmp_path / "out"))
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.data_dir == REPO_ROOT / "data"
    assert settings.reports_dir == tmp_path / "out"
