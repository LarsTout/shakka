import httpx
import pytest
from click.testing import CliRunner

import shakka.config
import shakka.doctor
from shakka.cli import cli
from shakka.http import USER_AGENT

SECRET = "sb_secret_TESTVALUE"
URL = "https://testref.supabase.co"


class Recorder:
    def __init__(self, status=200, error=None):
        self.requests: list[httpx.Request] = []
        self.status = status
        self.error = error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        return httpx.Response(self.status, text="secret body text")


@pytest.fixture
def rec(monkeypatch):
    def install(status=200, error=None):
        r = Recorder(status, error)
        monkeypatch.setattr(
            shakka.doctor,
            "make_client",
            lambda *, timeout=30.0: httpx.Client(
                transport=httpx.MockTransport(r), headers={"User-Agent": USER_AGENT}
            ),
        )
        return r

    return install


def env(monkeypatch, url=URL, secret=SECRET, **extra):
    if url is not None:
        monkeypatch.setenv("SUPABASE_URL", url)
    if secret is not None:
        monkeypatch.setenv("SUPABASE_SECRET_KEY", secret)
    for k, v in extra.items():
        monkeypatch.setenv(k.upper(), v)


def doctor():
    result = CliRunner().invoke(cli, ["doctor"])
    return result.exit_code, result.output


def doctor_result():
    return CliRunner().invoke(cli, ["doctor"])


OPTIONAL = (
    "APP_BASE_URL",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
    "OPERATOR_USER_ID",
)


def test_help_lists_doctor():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output


def test_version_option():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "shakka" in result.output


def test_doctor_empty_env_reports_missing(rec):
    r = rec()
    code, out = doctor()
    assert code == 1
    assert "missing SUPABASE_URL" in out
    assert "missing SUPABASE_SECRET_KEY" in out
    assert "skip" in out
    assert "doctor: failed" in out
    assert r.requests == []


def test_doctor_partial_env_does_not_leak_values(rec, monkeypatch):
    rec()
    env(
        monkeypatch,
        url="https://leakcheckref.supabase.co",
        secret=None,
        vapid_private_key="TESTVAPIDPRIV",
        supabase_publishable_key="sb_publishable_TESTPUB",
    )
    code, out = doctor()
    assert code == 1
    assert "missing SUPABASE_SECRET_KEY" in out
    for leaked in ("leakcheckref", "TESTVAPIDPRIV", "TESTPUB"):
        assert leaked not in out


def test_doctor_never_mentions_telegram(rec, monkeypatch):
    rec()
    code, out = doctor()
    assert code == 1
    assert "telegram" not in out.lower()
    env(monkeypatch)
    code, out = doctor()
    assert code == 0
    assert "telegram" not in out.lower()


def test_doctor_empty_string_counts_as_missing(rec, monkeypatch):
    rec()
    env(monkeypatch, secret="")
    code, out = doctor()
    assert code == 1
    assert "missing SUPABASE_SECRET_KEY" in out


def test_doctor_reads_env_file(rec, monkeypatch, tmp_path):
    rec()
    env_file = tmp_path / ".env"
    env_file.write_text(f"SUPABASE_URL={URL}\nSUPABASE_SECRET_KEY={SECRET}\n")
    monkeypatch.setattr(shakka.config, "ENV_FILE", env_file)
    code, out = doctor()
    assert code == 0, out


def test_doctor_success(rec, monkeypatch):
    r = rec()
    env(monkeypatch)
    code, out = doctor()
    assert code == 0
    assert "doctor: ok" in out
    assert "ok      Supabase REST API reachable (HTTP 200)" in out
    assert len(r.requests) == 1
    req = r.requests[0]
    assert req.method == "GET"
    assert str(req.url) == f"{URL}/rest/v1/"
    assert req.headers["apikey"] == SECRET
    assert "authorization" not in req.headers
    assert SECRET not in str(req.url)
    assert req.headers["user-agent"].startswith("shakka-ingest/")


def test_doctor_trailing_slash_url(rec, monkeypatch):
    r = rec()
    env(monkeypatch, url=URL + "/")
    code, _ = doctor()
    assert code == 0
    assert str(r.requests[0].url) == f"{URL}/rest/v1/"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "error   Supabase REST API rejected the key (HTTP 401)"),
        (403, "error   Supabase REST API rejected the key (HTTP 403)"),
        (404, "error   Supabase REST API returned HTTP 404; check SUPABASE_URL"),
        (500, "error   Supabase REST API returned HTTP 500"),
        (302, "error   Supabase REST API redirected (HTTP 302); check SUPABASE_URL"),
    ],
)
def test_doctor_http_status(rec, monkeypatch, status, expected):
    rec(status)
    env(monkeypatch)
    code, out = doctor()
    assert code == 1
    assert expected in out
    assert "doctor: failed" in out
    assert SECRET not in out
    assert "secret body text" not in out


def test_doctor_network_error(rec, monkeypatch):
    rec(error=httpx.ConnectError("boom testref"))
    env(monkeypatch)
    code, out = doctor()
    assert code == 1
    assert "unreachable (ConnectError)" in out
    assert "testref" not in out
    assert "boom" not in out


def test_doctor_timeout(rec, monkeypatch):
    rec(error=httpx.ReadTimeout("x"))
    env(monkeypatch)
    code, out = doctor()
    assert code == 1
    assert "timed out after 10s" in out


@pytest.mark.parametrize(
    "url",
    [
        "ftp://x.supabase.co",
        "http://testref.supabase.co",
        "https://testref.supabase.co/rest/v1",
        "https://testref.supabase.co?x=1",
    ],
)
def test_doctor_invalid_url(rec, monkeypatch, url):
    r = rec()
    env(monkeypatch, url=url)
    code, out = doctor()
    assert code == 1
    assert "invalid SUPABASE_URL" in out
    assert r.requests == []


def test_doctor_local_http_url_allowed(rec, monkeypatch):
    r = rec()
    env(monkeypatch, url="http://127.0.0.1:54321")
    code, _ = doctor()
    assert code == 0
    assert str(r.requests[0].url) == "http://127.0.0.1:54321/rest/v1/"


def test_doctor_prefix_warnings(rec, monkeypatch):
    rec()
    env(monkeypatch, secret="legacy-test-key", supabase_publishable_key="wrong-prefix")
    code, out = doctor()
    assert code == 0
    assert "warn    SUPABASE_SECRET_KEY" in out
    assert "warn    SUPABASE_PUBLISHABLE_KEY" in out
    assert "legacy-test-key" not in out
    assert "wrong-prefix" not in out


def test_doctor_publishable_unset_is_optional(rec, monkeypatch):
    rec()
    env(monkeypatch)
    code, out = doctor()
    assert code == 0
    assert "unset   SUPABASE_PUBLISHABLE_KEY (optional)" in out


def test_doctor_lists_optional_unset(rec, monkeypatch):
    rec()
    env(monkeypatch)
    for name in OPTIONAL:
        monkeypatch.delenv(name, raising=False)
    code, out = doctor()
    assert code == 0, out
    for name in OPTIONAL:
        assert f"unset   {name} (optional)" in out


def test_doctor_optional_set_without_values(rec, monkeypatch):
    rec()
    env(
        monkeypatch,
        app_base_url="TESTAPPURL",
        vapid_public_key="TESTVAPIDPUB",
        vapid_private_key="TESTVAPIDPRIV",
        vapid_subject="TESTSUBJECT",
        operator_user_id="TESTOPERATOR",
    )
    code, out = doctor()
    assert code == 0, out
    for name in OPTIONAL:
        assert f"set     {name} (optional)" in out
    for value in ("TESTAPPURL", "TESTVAPIDPUB", "TESTVAPIDPRIV", "TESTSUBJECT", "TESTOPERATOR"):
        assert value not in out


def test_doctor_blank_optional_is_unset(rec, monkeypatch):
    rec()
    env(monkeypatch, vapid_subject="   ")
    _, out = doctor()
    assert "unset   VAPID_SUBJECT (optional)" in out


@pytest.mark.parametrize("url", ["http://exa mple", "https://exa mple", "https://tëst.supabase.co"])
def test_doctor_invalid_url_no_traceback(rec, monkeypatch, url):
    r = rec()
    env(monkeypatch, url=url)
    result = doctor_result()
    out = result.output
    assert result.exit_code == 1
    assert "invalid SUPABASE_URL" in out
    assert isinstance(result.exception, SystemExit)
    assert "Traceback" not in out
    assert SECRET not in out
    assert "exa mple" not in out
    assert r.requests == []


@pytest.mark.parametrize("secret", ["sb_secret_tëst", "sb_secret_x ", "sb_secret_x\n"])
def test_doctor_secret_key_unusable_characters(rec, monkeypatch, secret):
    r = rec()
    env(monkeypatch, secret=secret)
    result = doctor_result()
    out = result.output
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "invalid SUPABASE_SECRET_KEY: contains non-ASCII, whitespace or control" in out
    assert "skip    Supabase REST check (configuration invalid)" in out
    assert "sb_secret_" not in out.replace("sb_secret_...", "")
    assert "Traceback" not in out
    assert r.requests == []


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.InvalidURL("bad testref"), "Supabase REST check failed (InvalidURL)"),
        (
            UnicodeEncodeError("ascii", "x", 0, 1, "bad"),
            "Supabase REST check failed (UnicodeEncodeError)",
        ),
    ],
)
def test_doctor_unexpected_client_error(rec, monkeypatch, error, expected):
    rec(error=error)
    env(monkeypatch)
    result = doctor_result()
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert f"error   {expected}" in result.output
    assert "testref" not in result.output


def test_doctor_settings_read_error(rec, monkeypatch):
    def raiser():
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad testref")

    rec()
    monkeypatch.setattr(shakka.doctor, "get_settings", raiser)
    result = doctor_result()
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "error   could not read settings (UnicodeDecodeError)" in result.output
    assert "testref" not in result.output
