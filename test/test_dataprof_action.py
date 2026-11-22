"""Unit tests for scripts/dataprof_action.py over recorded dataprof fixtures.

Runs with pytest and the Python standard library only, without a dataprof wheel.
"""

from __future__ import annotations

import errno
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import dataprof_action as da

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Input parsing and command construction
# ---------------------------------------------------------------------------


def test_build_command_single_source_with_all_flags(tmp_path: Path) -> None:
    cfg = da.ActionConfig(
        file="data/orders.csv",
        recursive=False,
        quality_threshold="85",
        policy="policies/orders.json",
        scope="observed",
        max_rows="1000",
        source_version="2026-11-22",
        baseline="baselines/orders.json",
        allow_missing_baseline=True,
        promote="baselines/orders.json",
    )
    report_path = tmp_path / "report.json"
    cmd = da.build_check_command(
        cfg,
        ["data/orders.csv"],
        python_executable="/venv/bin/python",
        report_path=report_path,
    )
    assert cmd == [
        "/venv/bin/python",
        "-m",
        "dataprof.check",
        "--json",
        "--min-quality",
        "85",
        "--policy",
        "policies/orders.json",
        "--scope",
        "observed",
        "--max-rows",
        "1000",
        "--source-version",
        "2026-11-22",
        "--baseline",
        "baselines/orders.json",
        "--allow-missing-baseline",
        "--promote",
        "baselines/orders.json",
        "--report",
        str(report_path),
        "--",
        "data/orders.csv",
    ]


def test_build_command_defaults_omit_optional_flags() -> None:
    cfg = da.ActionConfig.from_env({"INPUT_FILE": "data/orders.csv"})
    cmd = da.build_check_command(cfg, ["data/orders.csv"], python_executable="python")
    assert cmd == ["python", "-m", "dataprof.check", "--json", "--", "data/orders.csv"]
    assert "--min-quality" not in cmd
    assert "-r" not in cmd
    assert "--report" not in cmd


def test_build_command_directory_with_recursive() -> None:
    cfg = da.ActionConfig.from_env(
        {
            "INPUT_FILE": "data/batch/",
            "INPUT_RECURSIVE": "true",
            "INPUT_QUALITY_THRESHOLD": "80",
        }
    )
    cmd = da.build_check_command(cfg, ["data/batch/"], python_executable="python")
    assert cmd == [
        "python",
        "-m",
        "dataprof.check",
        "--json",
        "-r",
        "--min-quality",
        "80",
        "--",
        "data/batch/",
    ]


def test_expand_sources_handles_globs_directories_and_multiple_tokens(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    a = sub / "a.csv"
    b = sub / "b.csv"
    a.write_text("id\n1\n", encoding="utf-8")
    b.write_text("id\n2\n", encoding="utf-8")

    # Glob expands to sorted files, not directories
    glob_pattern = str(tmp_path / "**" / "*")
    sources, unmatched = da.expand_sources(glob_pattern)
    assert unmatched == []
    assert sources == [str(a), str(b)]

    # Directory goes straight through without expansion
    dir_sources, dir_unmatched = da.expand_sources(str(sub))
    assert dir_unmatched == []
    assert dir_sources == [str(sub)]
    assert not da.is_single_source_invocation(dir_sources)

    # Space- and newline-separated sources
    multi_input = f"{a}\n{b}"
    multi_sources, multi_unmatched = da.expand_sources(multi_input)
    assert multi_unmatched == []
    assert multi_sources == [str(a), str(b)]
    assert not da.is_single_source_invocation(multi_sources)


def test_expand_sources_reports_unmatched_glob(tmp_path: Path) -> None:
    pattern = str(tmp_path / "*.parquet")
    sources, unmatched = da.expand_sources(pattern)
    assert sources == []
    assert unmatched == [pattern]


def test_from_env_rejects_invalid_boolean_and_empty_file() -> None:
    with pytest.raises(da.ActionInputError, match="file"):
        da.ActionConfig.from_env({"INPUT_FILE": "   "})
    with pytest.raises(da.ActionInputError, match="fail-on-issues"):
        da.ActionConfig.from_env({"INPUT_FILE": "a.csv", "INPUT_FAIL_ON_ISSUES": "yes"})


# ---------------------------------------------------------------------------
# Exit code mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rc", "fail_issues", "fail_inconc", "expected"),
    [
        (0, True, True, 0),
        (0, False, False, 0),
        (1, True, True, 1),
        (1, False, True, 0),
        (2, True, True, 2),
        (2, True, False, 0),
        (3, True, True, 3),
        (3, False, False, 3),
    ],
)
def test_determine_step_exit_code(
    rc: int, fail_issues: bool, fail_inconc: bool, expected: int
) -> None:
    assert (
        da.determine_step_exit_code(
            rc, fail_on_issues=fail_issues, fail_on_inconclusive=fail_inconc
        )
        == expected
    )


# ---------------------------------------------------------------------------
# Single-source fixtures and absent scores
# ---------------------------------------------------------------------------


def test_single_pass_with_report_and_absent_dimension() -> None:
    gate_doc = load_fixture("single_pass.json")
    report_doc = load_fixture("single_pass_report.json")

    parsed = da.parse_check_document(
        gate_doc,
        report_doc=report_doc,
        file_input="test/data/csv/clean_data.csv",
        report_path="/tmp/report.json",
    )
    assert parsed.kind == "single"
    assert parsed.verdict == "pass"
    assert parsed.files_analyzed == 1
    assert parsed.violations_count == 0
    assert parsed.unevaluated_count == 0
    assert parsed.errors_count == 0
    assert parsed.skipped_count == 0
    assert parsed.outputs["quality-score"] == "89.47"
    assert parsed.outputs["completeness-score"] == "100.0"
    assert parsed.outputs["uniqueness-score"] == "100.0"
    assert parsed.outputs["validity-score"] == "100.0"
    assert parsed.outputs["consistency-score"] == "100.0"
    assert parsed.outputs["accuracy-score"] == "100.0"
    # Timeliness was analyzed as 0.0 (real zero), whereas precision is null (absent -> empty)
    assert parsed.outputs["timeliness-score"] == "0.0"
    assert parsed.outputs["precision-score"] == ""
    assert parsed.outputs["report-path"] == "/tmp/report.json"

    summary = da.render_step_summary(
        parsed, gate_doc, file_label="test/data/csv/clean_data.csv", report_doc=report_doc
    )
    assert "## DataProf Quality Gate: `pass`" in summary
    assert "| Precision | not analyzed |" in summary
    assert "| Timeliness | 0.0 |" in summary
    assert "`min_quality_score`" in summary
    assert ">= 80.0" in summary


def test_absent_quality_block_produces_empty_outputs_never_zero() -> None:
    gate_doc = load_fixture("single_no_quality.json")
    report_doc = load_fixture("single_no_quality_report.json")

    parsed = da.parse_check_document(
        gate_doc,
        report_doc=report_doc,
        file_input="test/data/csv/clean_data.csv",
        report_path="/tmp/no_quality.json",
    )
    assert parsed.verdict == "pass"
    assert parsed.outputs["quality-score"] == ""
    for _, output_key in da.DIMENSION_SCORE_OUTPUTS:
        assert parsed.outputs[output_key] == ""

    summary = da.render_step_summary(
        parsed, gate_doc, file_label="test/data/csv/clean_data.csv", report_doc=report_doc
    )
    assert "| Overall quality | not analyzed |" in summary


def test_single_fail_counts_violations_and_renders_targets() -> None:
    gate_doc = load_fixture("single_fail.json")
    report_doc = load_fixture("single_fail_report.json")

    parsed = da.parse_check_document(
        gate_doc,
        report_doc=report_doc,
        file_input="test/data/csv/dirty_data.csv",
        report_path="/tmp/dirty_report.json",
    )
    assert parsed.verdict == "fail"
    assert parsed.files_analyzed == 1
    assert parsed.violations_count == 3
    assert parsed.unevaluated_count == 0
    assert parsed.outputs["quality-score"] == "77.82"
    assert parsed.outputs["completeness-score"] == "65.93"

    summary = da.render_step_summary(
        parsed, gate_doc, file_label="test/data/csv/dirty_data.csv", report_doc=report_doc
    )
    assert "## DataProf Quality Gate: `fail`" in summary
    assert "column `missing_col`" in summary
    assert "dimension `completeness`" in summary
    assert "| `require_column` | column `missing_col` | failed | - | present |" in summary


def test_single_inconclusive_truncated_and_unevaluated_missing_metric() -> None:
    truncated_doc = load_fixture("single_inconclusive.json")
    truncated_report = load_fixture("single_inconclusive_report.json")
    parsed_trunc = da.parse_check_document(
        truncated_doc,
        report_doc=truncated_report,
        file_input="test/data/csv/large_dataset.csv",
    )
    assert parsed_trunc.verdict == "inconclusive"
    assert parsed_trunc.violations_count == 0
    assert parsed_trunc.unevaluated_count == 1
    summary_trunc = da.render_step_summary(
        parsed_trunc, truncated_doc, file_label="test/data/csv/large_dataset.csv"
    )
    assert "unevaluated (evidence_incomplete: truncated)" in summary_trunc
    assert "`incomplete` (truncated)" in summary_trunc

    metric_doc = load_fixture("single_unevaluated_metric.json")
    parsed_metric = da.parse_check_document(metric_doc, file_input="test/data/csv/clean_data.csv")
    assert parsed_metric.verdict == "inconclusive"
    assert parsed_metric.unevaluated_count == 1
    summary_metric = da.render_step_summary(
        parsed_metric, metric_doc, file_label="test/data/csv/clean_data.csv"
    )
    assert (
        "| `min_dimension_score` | dimension `precision` | unevaluated (not_assessed) "
        "| unevaluated | >= 80.0 |"
    ) in summary_metric


def test_single_top_level_error_document() -> None:
    err_doc = load_fixture("single_error.json")
    parsed = da.parse_check_document(err_doc, file_input="test/data/invalid/malformed.json")
    assert parsed.kind == "error"
    assert parsed.verdict == "error"
    assert parsed.files_analyzed == 0
    assert parsed.errors_count == 1
    assert parsed.violations_count == 0
    assert parsed.outputs["quality-score"] == ""
    assert parsed.outputs["report-path"] == ""

    summary = da.render_step_summary(parsed, err_doc, file_label="test/data/invalid/malformed.json")
    assert "## DataProf Quality Gate: `error`" in summary
    assert "### Error" in summary
    assert "`input`" in summary
    assert "malformed.json" in summary


# ---------------------------------------------------------------------------
# Multi-source fixtures
# ---------------------------------------------------------------------------


def test_multi_source_pass_has_empty_scores_and_counts_all_files() -> None:
    doc = load_fixture("multi_pass.json")
    parsed = da.parse_check_document(doc, file_input="test/data/batch/")
    assert parsed.kind == "multi"
    assert parsed.verdict == "pass"
    assert parsed.files_analyzed == 5
    assert parsed.violations_count == 0
    assert parsed.unevaluated_count == 0
    assert parsed.errors_count == 0
    assert parsed.skipped_count == 0
    assert parsed.outputs["quality-score"] == ""
    assert parsed.outputs["report-path"] == ""
    for _, output_key in da.DIMENSION_SCORE_OUTPUTS:
        assert parsed.outputs[output_key] == ""


def test_multi_source_with_failure() -> None:
    doc = load_fixture("multi_fail.json")
    parsed = da.parse_check_document(doc, file_input="test/data/csv/clean_data.csv ...")
    assert parsed.kind == "multi"
    assert parsed.verdict == "fail"
    assert parsed.files_analyzed == 2
    assert parsed.violations_count == 1
    assert parsed.errors_count == 0
    assert parsed.outputs["quality-score"] == ""

    summary = da.render_step_summary(parsed, doc)
    assert "## DataProf Quality Gate: `fail`" in summary
    assert "clean_data.csv" in summary
    assert "dirty_data.csv" in summary
    assert "### Source Errors" not in summary


def test_multi_source_with_error_and_skipped_files() -> None:
    doc = load_fixture("multi_error_and_skipped.json")
    parsed = da.parse_check_document(doc, file_input="mixed")
    assert parsed.kind == "multi"
    assert parsed.verdict == "error"
    assert parsed.files_analyzed == 2
    assert parsed.violations_count == 1
    assert parsed.errors_count == 1
    assert parsed.skipped_count == 1
    assert parsed.outputs["verdict"] == "error"
    assert parsed.outputs["quality-score"] == ""

    summary = da.render_step_summary(parsed, doc)
    assert "## DataProf Quality Gate: `error`" in summary
    assert "### Source Errors" in summary
    assert "malformed.json" in summary
    assert "### Skipped Files" in summary
    assert "README.md" in summary
    assert "format could not be inferred" in summary


# ---------------------------------------------------------------------------
# Baseline first-run and second-run fixtures
# ---------------------------------------------------------------------------


def test_baseline_first_and_second_run_fixtures() -> None:
    first_doc = load_fixture("baseline_first_run.json")
    first_parsed = da.parse_check_document(first_doc, file_input="test/data/csv/clean_data.csv")
    assert first_parsed.verdict == "pass"
    assert first_parsed.violations_count == 0
    assert first_parsed.unevaluated_count == 0
    first_md = da.render_step_summary(
        first_parsed, first_doc, file_label="test/data/csv/clean_data.csv"
    )
    assert "none (missing baseline allowed)" in first_md
    assert (
        "| `max_quality_score_drop` | - | not applicable | not applicable | change >= -5.0 |"
        in first_md
    )

    second_doc = load_fixture("baseline_second_run.json")
    second_parsed = da.parse_check_document(second_doc, file_input="test/data/csv/clean_data.csv")
    assert second_parsed.verdict == "pass"
    second_md = da.render_step_summary(
        second_parsed, second_doc, file_label="test/data/csv/clean_data.csv"
    )
    assert "89.47 (change: 0.0)" in second_md


# ---------------------------------------------------------------------------
# GITHUB_OUTPUT writing and end-to-end runner with a fake subprocess
# ---------------------------------------------------------------------------


def test_write_github_output_uses_heredoc_for_multiline(tmp_path: Path) -> None:
    out_file = tmp_path / "github_output.txt"
    da.write_github_output(
        out_file,
        {
            "verdict": "pass",
            "quality-score": "",
            "analysis-summary": "line one\nline two",
        },
    )
    text = out_file.read_text(encoding="utf-8")
    assert "verdict=pass\n" in text
    assert "quality-score=\n" in text
    assert "analysis-summary<<EOF_" in text
    assert "line one\nline two\n" in text


def test_run_action_unmatched_glob_exits_3_and_writes_outputs(tmp_path: Path) -> None:
    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"
    export = tmp_path / "export.json"
    rc = da.run_action(
        env={
            "INPUT_FILE": str(tmp_path / "*.parquet"),
            "INPUT_EXPORT_JSON_PATH": str(export),
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )
    assert rc == 3
    out_text = gh_out.read_text(encoding="utf-8")
    assert "verdict=error\n" in out_text
    assert "errors-count=1\n" in out_text
    assert "files-analyzed=0\n" in out_text
    assert "quality-score=\n" in out_text
    assert export.is_file()
    assert json.loads(export.read_text(encoding="utf-8"))["error"]["kind"] == "input"
    assert "no files matched glob pattern" in gh_sum.read_text(encoding="utf-8")


def test_run_action_exit_2_respects_fail_on_inconclusive_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_text = (FIXTURES / "single_inconclusive.json").read_text(encoding="utf-8")

    class FakeProc:
        returncode = 2
        stdout = fixture_text
        stderr = "dataprof 0.14.0: inconclusive: 1 checks, 0 violations, 1 unevaluated\n"

    monkeypatch.setattr(da.subprocess, "run", lambda *a, **kw: FakeProc())
    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"
    rc = da.run_action(
        env={
            "INPUT_FILE": "test/data/csv/large_dataset.csv",
            "INPUT_QUALITY_THRESHOLD": "80",
            "INPUT_MAX_ROWS": "5",
            "INPUT_SCOPE": "full_source",
            "INPUT_FAIL_ON_INCONCLUSIVE": "false",
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )
    assert rc == 0
    out_text = gh_out.read_text(encoding="utf-8")
    assert "verdict=inconclusive\n" in out_text
    assert "unevaluated-count=1\n" in out_text
    assert "unevaluated (evidence_incomplete: truncated)" in gh_sum.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Review fixes: literal glob paths, ENAMETOOLONG, cmd limit, aliasing, export
# failure, and summary size cap
# ---------------------------------------------------------------------------


def test_expand_sources_keeps_existing_path_with_glob_characters_verbatim(tmp_path: Path) -> None:
    literal = tmp_path / "data[1].csv"
    glob_target = tmp_path / "data1.csv"
    other = tmp_path / "other.csv"
    literal.write_text("id\n1\n", encoding="utf-8")
    glob_target.write_text("id\n2\n", encoding="utf-8")
    other.write_text("id\n3\n", encoding="utf-8")

    # Alone on a line: kept verbatim, never expanded to data1.csv
    sources, unmatched = da.expand_sources(str(literal))
    assert unmatched == []
    assert sources == [str(literal)]

    # Together with another path on the same line (whole-line probe is False)
    multi_sources, multi_unmatched = da.expand_sources(f"{literal} {other}")
    assert multi_unmatched == []
    assert multi_sources == [str(literal), str(other)]

    # Non-existent token with glob magic still expands via glob
    pattern = str(tmp_path / "data[12].csv")
    globbed, glob_unmatched = da.expand_sources(pattern)
    assert glob_unmatched == []
    assert globbed == [str(glob_target)]


def test_split_file_tokens_and_expand_sources_handle_enametoolong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id\n1\n", encoding="utf-8")
    b.write_text("id\n2\n", encoding="utf-8")

    # Long space-separated line exceeding typical path-length limits
    many = [tmp_path / f"dataset_{i:03d}.csv" for i in range(40)]
    for path in many:
        path.write_text("id\n1\n", encoding="utf-8")
    long_line = " ".join(str(p) for p in many)
    assert len(long_line) > 500
    assert da.split_file_tokens(long_line) == [str(p) for p in many]

    # Explicit OSError(ENAMETOOLONG) on both whole-line probe and per-token probe
    real_exists = Path.exists

    def flaky_exists(self: Path) -> bool:
        text = str(self)
        if " " in text or "overlong" in text:
            raise OSError(errno.ENAMETOOLONG, "File name too long")
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", flaky_exists)

    assert da.split_file_tokens(f"{a} {b}") == [str(a), str(b)]
    overlong_literal = str(tmp_path / ("overlong_" + "x" * 300 + ".csv"))
    sources, unmatched = da.expand_sources(f"{a} {overlong_literal}")
    assert unmatched == []
    assert sources == [str(a), overlong_literal]


@pytest.mark.parametrize(
    "error_kind",
    ["winerror_206", "e2big", "file_not_found_overlong"],
)
def test_run_action_command_line_too_long_emits_invocation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_kind: str,
) -> None:
    if error_kind == "file_not_found_overlong":
        # Generate enough paths so the command line exceeds 32,767 characters
        files = [tmp_path / f"batch_source_file_name_padding_{i:04d}.csv" for i in range(450)]
        file_input = "\n".join(str(p) for p in files)
    else:
        file_input = str(tmp_path / "a.csv")

    calls = 0

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if error_kind == "winerror_206":
            exc = FileNotFoundError(errno.ENOENT, "The filename or extension is too long")
            exc.winerror = 206  # type: ignore[attr-defined]
            raise exc
        if error_kind == "e2big":
            raise OSError(errno.E2BIG, "Argument list too long")
        raise FileNotFoundError(errno.ENOENT, "No such file or directory")

    monkeypatch.setattr(da.subprocess, "run", fake_run)

    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"
    export = tmp_path / "export.json"
    rc = da.run_action(
        env={
            "INPUT_FILE": file_input,
            "INPUT_QUALITY_THRESHOLD": "80",
            "INPUT_EXPORT_JSON_PATH": str(export),
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )

    assert rc == 3
    assert calls == 1  # Never splits the run
    out_text = gh_out.read_text(encoding="utf-8")
    assert "verdict=error\n" in out_text
    assert "errors-count=1\n" in out_text
    exported = json.loads(export.read_text(encoding="utf-8"))
    assert exported["error"]["kind"] == "invocation"
    msg = exported["error"]["message"].lower()
    assert "too long" in msg
    assert "directory" in msg
    assert "invocation" in gh_sum.read_text(encoding="utf-8")
    assert "::error::" in capsys.readouterr().err


def test_run_action_rejects_export_path_aliasing_baseline_or_promote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        nonlocal called
        called = True
        raise AssertionError("subprocess.run must not be called on path aliasing")

    monkeypatch.setattr(da.subprocess, "run", fail_if_called)

    # Case 1: export-json-path aliases an existing baseline via relative traversal
    base_dir = tmp_path / "baselines"
    base_dir.mkdir()
    baseline = base_dir / "orders.json"
    baseline.write_text('{"keep": true}\n', encoding="utf-8")
    aliased_export = str(base_dir / ".." / "baselines" / "orders.json")

    gh_out = tmp_path / "out1.txt"
    gh_sum = tmp_path / "sum1.md"
    rc = da.run_action(
        env={
            "INPUT_FILE": "data/orders.csv",
            "INPUT_BASELINE": str(baseline),
            "INPUT_EXPORT_JSON_PATH": aliased_export,
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )
    assert rc == 3
    assert not called
    assert baseline.read_text(encoding="utf-8") == '{"keep": true}\n'
    out1 = gh_out.read_text(encoding="utf-8")
    assert "verdict=error\n" in out1
    assert "errors-count=1\n" in out1
    assert "json-export-path=\n" in out1
    sum1 = gh_sum.read_text(encoding="utf-8")
    assert "`argument`" in sum1
    assert "baseline" in sum1

    # Case 2: export-json-path aliases a non-existent promote path
    promote_nonexistent = tmp_path / "future" / "promoted.json"
    aliased_promote_export = str(tmp_path / "other" / ".." / "future" / "promoted.json")

    gh_out2 = tmp_path / "out2.txt"
    gh_sum2 = tmp_path / "sum2.md"
    rc2 = da.run_action(
        env={
            "INPUT_FILE": "data/orders.csv",
            "INPUT_PROMOTE": str(promote_nonexistent),
            "INPUT_EXPORT_JSON_PATH": aliased_promote_export,
            "GITHUB_OUTPUT": str(gh_out2),
            "GITHUB_STEP_SUMMARY": str(gh_sum2),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )
    assert rc2 == 3
    assert not called
    assert not promote_nonexistent.exists()
    assert "`argument`" in gh_sum2.read_text(encoding="utf-8")
    assert "promote" in gh_sum2.read_text(encoding="utf-8")


def test_run_action_export_write_failure_preserves_verdict_and_reports_promote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_text = (FIXTURES / "single_pass.json").read_text(encoding="utf-8")
    promote_file = tmp_path / "promoted.json"
    export_dir = tmp_path / "not_a_file"
    export_dir.mkdir()

    class FakeProc:
        returncode = 0
        stdout = fixture_text
        stderr = "dataprof 0.14.1: pass: 1 checks, 0 violations, 0 unevaluated\n"

    def fake_run(*args: Any, **kwargs: Any) -> FakeProc:
        promote_file.write_text('{"promoted": true}\n', encoding="utf-8")
        return FakeProc()

    monkeypatch.setattr(da.subprocess, "run", fake_run)

    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"
    rc = da.run_action(
        env={
            "INPUT_FILE": "test/data/csv/clean_data.csv",
            "INPUT_QUALITY_THRESHOLD": "80",
            "INPUT_PROMOTE": str(promote_file),
            "INPUT_EXPORT_JSON_PATH": str(export_dir),
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )

    assert rc == 3
    out_text = gh_out.read_text(encoding="utf-8")
    assert "verdict=pass\n" in out_text
    assert "errors-count=1\n" in out_text
    assert "json-export-path=\n" in out_text

    summary_text = gh_sum.read_text(encoding="utf-8")
    assert "## DataProf Quality Gate: `pass`" in summary_text
    assert "**Errors**: 1" in summary_text
    assert "Export error" in summary_text
    assert "promoted baseline was already saved" in summary_text

    stderr_text = capsys.readouterr().err
    assert "::error::" in stderr_text
    assert "export-json-path" in stderr_text
    assert "promoted baseline was already saved" in stderr_text


def test_emit_error_run_survives_export_write_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export_dir = tmp_path / "existing_dir"
    export_dir.mkdir()
    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"

    rc = da.run_action(
        env={
            "INPUT_FILE": str(tmp_path / "*.parquet"),
            "INPUT_EXPORT_JSON_PATH": str(export_dir),
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )

    assert rc == 3
    out_text = gh_out.read_text(encoding="utf-8")
    assert "verdict=error\n" in out_text
    assert "errors-count=2\n" in out_text
    assert "json-export-path=\n" in out_text
    summary_text = gh_sum.read_text(encoding="utf-8")
    assert "no files matched glob pattern" in summary_text
    assert "Export error" in summary_text
    stderr_text = capsys.readouterr().err
    assert "::error::dataprof check failed (input):" in stderr_text
    assert "::error::failed to write export-json-path" in stderr_text


def test_render_step_summary_caps_large_multi_source_and_keeps_json_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    total_sources = 3200
    sources_payload = [
        {
            "path": f"data/café_batch_{i:04d}.csv",
            "result": {
                "verdict": "pass",
                "scope": "full_source",
                "evidence": {"coverage": "complete"},
                "checks": [
                    {
                        "code": "min_quality_score",
                        "status": "passed",
                        "observed": 95.0,
                        "expected": {"comparison": "at_least", "value": 80.0},
                        "message": "overall quality score meets the required minimum for café",
                    }
                ],
            },
        }
        for i in range(total_sources)
    ]
    big_doc: dict[str, Any] = {
        "verdict": "pass",
        "sources": sources_payload,
        "skipped": [],
    }
    raw_json = json.dumps(big_doc) + "\n"

    class FakeProc:
        returncode = 0
        stdout = raw_json
        stderr = ""

    monkeypatch.setattr(da.subprocess, "run", lambda *a, **kw: FakeProc())

    gh_out = tmp_path / "out.txt"
    gh_sum = tmp_path / "summary.md"
    export = tmp_path / "complete_export.json"
    rc = da.run_action(
        env={
            "INPUT_FILE": "data/",
            "INPUT_QUALITY_THRESHOLD": "80",
            "INPUT_EXPORT_JSON_PATH": str(export),
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(gh_sum),
            "RUNNER_TEMP": str(tmp_path),
        },
        python_executable=sys.executable,
    )

    assert rc == 0
    summary_bytes = gh_sum.read_bytes()
    assert len(summary_bytes) <= da.MAX_STEP_SUMMARY_BYTES
    assert len(summary_bytes) > 800 * 1024  # Substantially filled before capping

    summary_text = summary_bytes.decode("utf-8")
    assert "## DataProf Quality Gate: `pass`" in summary_text
    assert f"- **Files analyzed**: {total_sources}" in summary_text
    assert "### Source: `data/café_batch_0000.csv`" in summary_text
    assert f"### Source: `data/café_batch_{total_sources - 1:04d}.csv`" not in summary_text

    included_count = summary_text.count("### Source: `data/café_batch_")
    omitted_count = total_sources - included_count
    assert omitted_count > 0
    assert f"{omitted_count} source(s) omitted" in summary_text
    assert str(export) in summary_text
    assert "`--json`" in summary_text

    # Exported JSON stays complete with every source
    exported_doc = json.loads(export.read_text(encoding="utf-8"))
    assert len(exported_doc["sources"]) == total_sources
    assert exported_doc["sources"][-1]["path"] == f"data/café_batch_{total_sources - 1:04d}.csv"


# ---------------------------------------------------------------------------
# Inline policy JSON
# ---------------------------------------------------------------------------


def _run_with_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy: str
) -> tuple[int, list[list[str]], str]:
    source = tmp_path / "orders.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    calls: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stdout = json.dumps(load_fixture("single_pass.json"))
        stderr = ""

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(da.subprocess, "run", fake_run)
    gh_out = tmp_path / "out.txt"
    rc = da.run_action(
        env={
            "INPUT_FILE": str(source),
            "INPUT_POLICY": policy,
            "GITHUB_OUTPUT": str(gh_out),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "RUNNER_TEMP": str(tmp_path / "runner"),
        },
        python_executable=sys.executable,
    )
    return rc, calls, gh_out.read_text(encoding="utf-8")


def test_inline_policy_json_is_written_to_a_file_and_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = '{\n  "min_rows": 1,\n  "max_null_count": {"id": 0}\n}\n'
    rc, calls, _ = _run_with_policy(tmp_path, monkeypatch, policy)

    assert rc == 0
    assert len(calls) == 1
    cmd = calls[0]
    policy_arg = Path(cmd[cmd.index("--policy") + 1])
    assert policy_arg.parent == tmp_path / "runner"
    assert json.loads(policy_arg.read_text(encoding="utf-8")) == {
        "min_rows": 1,
        "max_null_count": {"id": 0},
    }


def test_policy_path_is_passed_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text('{"min_rows": 1}', encoding="utf-8")
    rc, calls, _ = _run_with_policy(tmp_path, monkeypatch, str(policy_file))

    assert rc == 0
    cmd = calls[0]
    assert cmd[cmd.index("--policy") + 1] == str(policy_file)


@pytest.mark.parametrize(
    "policy, message",
    [
        ('{"min_rows": 1', "does not parse"),
        ('{"min_rows": 1} [1]', "does not parse"),
    ],
)
def test_inline_policy_that_does_not_parse_is_an_argument_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy: str, message: str
) -> None:
    rc, calls, out_text = _run_with_policy(tmp_path, monkeypatch, policy)

    assert rc == 3
    assert calls == []
    assert "verdict=error\n" in out_text
    assert message in out_text
