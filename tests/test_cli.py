import io

from tiviss.cli.main import build_agent, build_parser, load_config, run_loop, run_once
from tiviss.configuration import TIVISSConfig
from tiviss.permissions import DefaultDenyPolicy


def _config(**overrides):
    data = {
        "agent": {"name": "tiv", "owner_id": "kishir"},
        "permissions": {"allow": ["conversation.generate"]},
    }
    data.update(overrides)
    return TIVISSConfig.load(data)


def test_version(capsys):
    assert build_parser().parse_args(["--version"])
    from tiviss.cli.main import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip()


def test_message_roundtrip(capsys):
    from tiviss.cli.main import main

    assert main(["--message", "hello"]) == 0
    out = capsys.readouterr().out
    assert "hello" in out


def test_message_empty_is_usage_error(capsys):
    from tiviss.cli.main import main

    assert main(["--message", "   "]) == 2


def test_run_loop_quit():
    agent = build_agent(_config())
    agent.start()
    stdin = io.StringIO("/quit\n")
    stdout = io.StringIO()
    assert run_loop(agent, stdin=stdin, stdout=stdout) == 0
    assert "T.I.V.I.S.S." in stdout.getvalue()


def test_run_loop_help_and_status():
    agent = build_agent(_config())
    agent.start()
    stdin = io.StringIO("/help\n/status\n/quit\n")
    stdout = io.StringIO()
    assert run_loop(agent, stdin=stdin, stdout=stdout) == 0
    text = stdout.getvalue()
    assert "/quit" in text
    assert "state=running" in text


def test_run_loop_sends_request():
    agent = build_agent(_config())
    agent.start()
    stdin = io.StringIO("hello there\n/quit\n")
    stdout = io.StringIO()
    assert run_loop(agent, stdin=stdin, stdout=stdout) == 0
    assert "hello there" in stdout.getvalue()
    assert agent.requests_handled == 1


def test_run_once_denied_without_permission(capsys):
    config = TIVISSConfig.load(
        {"agent": {"name": "t", "owner_id": "k"}, "permissions": {"allow": []}}
    )
    agent = build_agent(config)
    # build_agent grants generate for the shell; strip it to test denial.
    agent.policy = DefaultDenyPolicy()
    agent.start()
    assert run_once(agent, "hi") == 1
    assert "denied" in capsys.readouterr().out


def test_bad_config_file(tmp_path, capsys):
    from tiviss.cli.main import main

    assert main(["--config", str(tmp_path / "missing.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert main(["--config", str(bad)]) == 2


def test_load_config_defaults():
    config = load_config(None)
    assert config.validate() == []
