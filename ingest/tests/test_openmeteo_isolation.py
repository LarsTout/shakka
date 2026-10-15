"""Open-Meteo is only reached from shakka.openmeteo (WP-03, AC-7)."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
ALLOWED = SRC / "shakka" / "openmeteo"
HOST = "open-meteo.com"


def test_open_meteo_host_only_in_openmeteo_package() -> None:
    hits = [
        path
        for path in SRC.rglob("*")
        if path.is_file() and path.suffix in {".py", ".txt", ".toml", ".json", ".yaml", ".md"}
        if HOST in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits, "expected at least one reference to the Open-Meteo host"
    outside = [p for p in hits if ALLOWED not in p.parents]
    assert not outside, f"open-meteo.com found outside shakka/openmeteo: {outside}"
    assert any(ALLOWED in p.parents for p in hits)


def test_httpx_client_only_created_in_http_module() -> None:
    hits = [
        path.relative_to(SRC / "shakka").as_posix()
        for path in (SRC / "shakka").rglob("*.py")
        if "httpx.Client(" in path.read_text(encoding="utf-8")
    ]
    assert hits == ["http.py"]
