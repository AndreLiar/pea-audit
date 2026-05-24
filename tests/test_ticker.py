"""Tests for audit_ticker — KID download path + error handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pea_audit import audit_ticker
from pea_audit.sources import KIDSource, register_source
from pea_audit.ticker import KIDDownloadError, _download_kid

from .conftest import FakeVisionLLM, _verdict_dict


def test_audit_ticker_unknown_returns_error(tmp_path: Path) -> None:
    fake = FakeVisionLLM(response=_verdict_dict())
    r = audit_ticker("DOES_NOT_EXIST.XX", llm=fake, kid_dir=tmp_path)
    assert r.verdict is None
    assert r.error is not None
    assert "No KID source registered" in r.error


def test_audit_ticker_known_ticker_audits(tmp_path: Path) -> None:
    """End-to-end: registered ticker → pre-supplied PDF → fake LLM → verdict."""
    kid_dir = tmp_path / "kids"
    kid_dir.mkdir()
    # Drop a PDF in place so _download_kid skips the network call
    (kid_dir / "TEST.PA.pdf").write_bytes(
        Path("samples/amundi_pea_monde_kid.pdf").read_bytes()
    )

    register_source(KIDSource(
        ticker="TEST.PA", isin="FR001400U5Q4",
        url="https://example.invalid/kid.pdf", issuer="Test",
    ))

    fake = FakeVisionLLM(response=_verdict_dict())
    r = audit_ticker("TEST.PA", llm=fake, kid_dir=kid_dir)
    assert r.verdict is not None
    assert r.error is None
    assert r.source is not None
    assert r.source.ticker == "TEST.PA"


def test_download_rejects_non_http_scheme(tmp_path: Path) -> None:
    bad = KIDSource(ticker="BAD.PA", isin="FR0000000000", url="file:///etc/passwd", issuer="x")
    with pytest.raises(KIDDownloadError, match="scheme.*not allowed"):
        _download_kid(bad, tmp_path)


def test_download_rejects_non_pdf_content_type(tmp_path: Path) -> None:
    src = KIDSource(ticker="X.PA", isin="FR0000000000", url="https://example.com/x", issuer="x")

    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()

    with patch("pea_audit.ticker.requests.get", return_value=mock_resp):
        with pytest.raises(KIDDownloadError, match="Content-Type"):
            _download_kid(src, tmp_path)


def test_download_rejects_oversized_response(tmp_path: Path) -> None:
    """Streaming download must abort when MAX_KID_BYTES is exceeded."""
    src = KIDSource(ticker="BIG.PA", isin="FR0000000000", url="https://example.com/big", issuer="x")

    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "application/pdf"}
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    # Generator producing 25 MB total (> 20 MB cap)
    mock_resp.iter_content = MagicMock(return_value=iter([b"\x00" * (1024 * 1024)] * 25))

    with patch("pea_audit.ticker.requests.get", return_value=mock_resp):
        with pytest.raises(KIDDownloadError, match="exceeds"):
            _download_kid(src, tmp_path)


def test_download_cached_file_returned_without_network(tmp_path: Path) -> None:
    """If kid_dir/{ticker}.pdf already exists and is big enough, no network call."""
    src = KIDSource(ticker="CACHED.PA", isin="FR0000000000", url="https://example.com/x", issuer="x")
    (tmp_path / "CACHED.PA.pdf").write_bytes(b"\x00" * 2048)  # > 1024 byte threshold

    with patch("pea_audit.ticker.requests.get") as mock_get:
        result = _download_kid(src, tmp_path)
        mock_get.assert_not_called()
        assert result.exists()


def test_download_force_refresh_bypasses_cache(tmp_path: Path) -> None:
    src = KIDSource(ticker="FORCE.PA", isin="FR0000000000", url="https://example.com/x", issuer="x")
    (tmp_path / "FORCE.PA.pdf").write_bytes(b"\x00" * 2048)

    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "application/pdf"}
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content = MagicMock(return_value=iter([b"NEW CONTENT"]))

    with patch("pea_audit.ticker.requests.get", return_value=mock_resp):
        _download_kid(src, tmp_path, force=True)
        assert (tmp_path / "FORCE.PA.pdf").read_bytes() == b"NEW CONTENT"
