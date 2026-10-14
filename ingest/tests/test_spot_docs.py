"""docs/SPOT_DATA.md must cover every field and the key instructions (AC-7)."""

import pytest

from shakka.config import REPO_ROOT
from shakka.domain.spot import SPOT_COLUMNS

DOC = REPO_ROOT / "docs" / "SPOT_DATA.md"


def test_doc_exists():
    assert DOC.is_file()


@pytest.mark.parametrize("column", SPOT_COLUMNS)
def test_doc_mentions_column(column: str):
    assert f"`{column}`" in DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "needle", ["270", "verified: true", "shakka tides stations", "shakka spots validate", "NKV"]
)
def test_doc_mentions(needle: str):
    assert needle in DOC.read_text(encoding="utf-8")
