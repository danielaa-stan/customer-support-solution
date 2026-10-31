import pytest

from agent.settings import Settings, load_settings


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """Real settings.toml, but logs go to a temp dir and no real key is needed."""
    return load_settings(env={"GEMINI_API_KEY": "test-key", "LOGGING_DIR": str(tmp_path),
                              "TRANSCRIPTS_DIR": str(tmp_path / "transcripts")})
