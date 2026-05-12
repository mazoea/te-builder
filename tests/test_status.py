"""Tests for te_builder.status.

The legacy code relied entirely on regex-scraping `"N Error(s)"` from the
MSBuild log to decide success or failure. That works only on English Windows;
a non-English VS install (German "Fehler", French "erreur", etc.) silently
reports failed builds as successful. The replacement uses the process return
code as the authoritative signal and only uses the regex to enrich the
summary line for English output.
"""

from __future__ import annotations

from pathlib import Path

from te_builder.status import StatusRow, summarize, summarize_from_log

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_detects_success_english() -> None:
    row = summarize(
        returncode=0,
        stdout=_read("msbuild_success.txt"),
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is True
    assert "zlib" in row.line
    assert "Release|x64" in row.line


def test_detects_errors_english() -> None:
    row = summarize(
        returncode=1,
        stdout=_read("msbuild_failure.txt"),
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is False
    assert "1 Error" in row.line
    assert "!" in row.line


def test_detects_errors_when_log_is_german() -> None:
    """Regression: legacy code missed non-English errors. Return code is
    the authoritative source of truth now."""
    row = summarize(
        returncode=1,
        stdout=_read("msbuild_failure_de.txt"),
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is False
    assert "!" in row.line


def test_zero_returncode_with_unparseable_log_still_succeeds() -> None:
    row = summarize(
        returncode=0,
        stdout="some compiler output we cannot parse",
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is True


def test_nonzero_returncode_with_unparseable_log_still_fails() -> None:
    row = summarize(
        returncode=2,
        stdout="some compiler output we cannot parse",
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is False


def test_statusrow_is_pickle_friendly_dataclass() -> None:
    row = StatusRow(ok=True, line="example")
    assert row.ok is True
    assert row.line == "example"


def test_summarize_from_log_reads_file_and_enriches_line(tmp_path) -> None:
    log = tmp_path / "zlib.Release-x64.log"
    log.write_text(_read("msbuild_failure.txt"), encoding="utf-8")
    row = summarize_from_log(
        returncode=1,
        log_file=log,
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is False
    assert "1 Error" in row.line


def test_summarize_from_log_tolerates_missing_file(tmp_path) -> None:
    row = summarize_from_log(
        returncode=0,
        log_file=tmp_path / "never-written.log",
        project_name="zlib",
        configuration="Release|x64",
    )
    assert row.ok is True
    assert "OK" in row.line
