import os

from get_env import loading_enviroment


def test_missing_env_file_does_nothing(tmp_path):
    # shouldn't crash if .env is gone
    loading_enviroment(str(tmp_path / "eee.env"))


def test_loads_simple_key_value(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'EMAIL="@example.com"\n'
        "TOOL=pubmed_research\n"
        "# comment line\n"
        "\n"
        "EMPTY_SKIP=\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("EMAIL", raising=False)
    monkeypatch.delenv("TOOL", raising=False)

    loading_enviroment(str(env_file))

    assert os.environ["EMAIL"] == "@example.com"
    assert os.environ["TOOL"] == "pubmed_research"


def test_strips_quotes_and_spaces(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("  FOO = 'bar'  \n", encoding="utf-8")

    monkeypatch.delenv("FOO", raising=False)
    loading_enviroment(str(env_file))

    assert os.environ["FOO"] == "bar"
