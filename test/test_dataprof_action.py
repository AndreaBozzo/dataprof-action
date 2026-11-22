"""Unit tests for scripts/dataprof_action.py over recorded dataprof fixtures.

Runs with pytest and the Python standard library only, without a dataprof wheel.
"""

from __future__ import annotations

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
