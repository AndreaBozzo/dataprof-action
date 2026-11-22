"""GitHub Action runner for ``python -m dataprof.check``.

Builds the ``dataprof.check`` command from action inputs, invokes it once,
writes ``GITHUB_OUTPUT`` and ``GITHUB_STEP_SUMMARY``, and translates the
dataprof exit code into the step exit code without recomputing any verdict,
score, weight, or threshold.
"""

from __future__ import annotations

import glob
import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DIMENSION_SCORE_OUTPUTS: tuple[tuple[str, str], ...] = (
    ("completeness", "completeness-score"),
    ("uniqueness", "uniqueness-score"),
    ("validity", "validity-score"),
    ("consistency", "consistency-score"),
    ("timeliness", "timeliness-score"),
    ("accuracy", "accuracy-score"),
    ("precision", "precision-score"),
)

SKIP_REASON_LABELS: dict[str, str] = {
    "format_not_inferred": "format could not be inferred",
    "not_a_regular_file": "not a regular file",
}

_STATUS_LABELS: dict[str, str] = {
    "passed": "passed",
    "failed": "failed",
    "not_evaluated": "unevaluated",
    "not_applicable": "not applicable",
}


class ActionInputError(ValueError):
    """Raised when an action input cannot be parsed before invoking dataprof."""


def parse_bool(value: str | None, *, name: str, default: bool) -> bool:
    """Parse a GitHub Actions boolean input strictly."""
    if value is None:
        return default
    cleaned = value.strip().lower()
    if not cleaned:
        return default
    if cleaned == "true":
        return True
    if cleaned == "false":
        return False
    raise ActionInputError(f"input {name!r} must be 'true' or 'false', got {value!r}")


@dataclass(frozen=True)
class ActionConfig:
    """Inputs for one invocation of the dataprof action."""

    file: str
    recursive: bool = False
    quality_threshold: str = ""
    policy: str = ""
    scope: str = ""
    max_rows: str = ""
    source_version: str = ""
    baseline: str = ""
    allow_missing_baseline: bool = False
    promote: str = ""
    fail_on_issues: bool = True
    fail_on_inconclusive: bool = True
    export_json_path: str = ""
    dataprof_version: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ActionConfig:
        file_input = env.get("INPUT_FILE", "").strip()
        if not file_input:
            raise ActionInputError("input 'file' is required and cannot be empty")
        return cls(
            file=file_input,
            recursive=parse_bool(env.get("INPUT_RECURSIVE"), name="recursive", default=False),
            quality_threshold=env.get("INPUT_QUALITY_THRESHOLD", "").strip(),
            policy=env.get("INPUT_POLICY", "").strip(),
            scope=env.get("INPUT_SCOPE", "").strip(),
            max_rows=env.get("INPUT_MAX_ROWS", "").strip(),
            source_version=env.get("INPUT_SOURCE_VERSION", "").strip(),
            baseline=env.get("INPUT_BASELINE", "").strip(),
            allow_missing_baseline=parse_bool(
                env.get("INPUT_ALLOW_MISSING_BASELINE"),
                name="allow-missing-baseline",
                default=False,
            ),
            promote=env.get("INPUT_PROMOTE", "").strip(),
            fail_on_issues=parse_bool(
                env.get("INPUT_FAIL_ON_ISSUES"), name="fail-on-issues", default=True
            ),
            fail_on_inconclusive=parse_bool(
                env.get("INPUT_FAIL_ON_INCONCLUSIVE"),
                name="fail-on-inconclusive",
                default=True,
            ),
            export_json_path=env.get("INPUT_EXPORT_JSON_PATH", "").strip(),
            dataprof_version=env.get("INPUT_DATAPROF_VERSION", "").strip(),
        )


def _strip_matching_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def split_file_tokens(raw: str) -> list[str]:
    """Split a space- or newline-separated ``file`` input into path/glob tokens.

    A whole line that already exists on disk is kept intact so unquoted paths
    containing spaces work on their own line. ``shlex.split(..., posix=False)``
    preserves Windows backslashes while respecting quotes.
    """
    tokens: list[str] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if Path(line).exists():
            tokens.append(line)
            continue
        try:
            parts = shlex.split(line, posix=False)
        except ValueError as exc:
            raise ActionInputError(f"invalid quoting in 'file' input: {exc}") from exc
        for part in parts:
            unquoted = _strip_matching_quotes(part).strip()
            if unquoted:
                tokens.append(unquoted)
    return tokens


def expand_sources(raw_file: str) -> tuple[list[str], list[str]]:
    """Expand glob patterns into files while passing literal paths through verbatim.

    Returns ``(sources, unmatched_globs)``. Directories and literal files are
    not expanded so dataprof handles directory scanning and missing-file errors.
    """
    tokens = split_file_tokens(raw_file)
    sources: list[str] = []
    unmatched_globs: list[str] = []
    for token in tokens:
        if glob.has_magic(token):
            matches = sorted(glob.glob(token, recursive=True))
            wants_dirs = token.endswith(("/", "\\"))
            if not wants_dirs:
                matches = [match for match in matches if not os.path.isdir(match)]
            if not matches:
                unmatched_globs.append(token)
            else:
                sources.extend(matches)
        else:
            sources.append(token)
    return sources, unmatched_globs


def is_single_source_invocation(sources: Sequence[str]) -> bool:
    """Return True when dataprof will run in single-source mode."""
    return len(sources) == 1 and not Path(sources[0]).is_dir()


def build_check_command(
    config: ActionConfig,
    sources: Sequence[str],
    *,
    python_executable: str,
    report_path: Path | None = None,
) -> list[str]:
    """Build the ``python -m dataprof.check`` argument vector."""
    cmd = [python_executable, "-m", "dataprof.check", "--json"]
    if config.recursive:
        cmd.append("-r")
    if config.quality_threshold:
        cmd.extend(["--min-quality", config.quality_threshold])
    if config.policy:
        cmd.extend(["--policy", config.policy])
    if config.scope:
        cmd.extend(["--scope", config.scope])
    if config.max_rows:
        cmd.extend(["--max-rows", config.max_rows])
    if config.source_version:
        cmd.extend(["--source-version", config.source_version])
    if config.baseline:
        cmd.extend(["--baseline", config.baseline])
    if config.allow_missing_baseline:
        cmd.append("--allow-missing-baseline")
    if config.promote:
        cmd.extend(["--promote", config.promote])
    if report_path is not None:
        cmd.extend(["--report", str(report_path)])
    cmd.append("--")
    cmd.extend(sources)
    return cmd


def _format_score(value: Any) -> str:
    """Format a score value as a string, returning '' when absent or not numeric."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def empty_scores() -> dict[str, str]:
    """Return all score output keys mapped to empty strings."""
    scores = {"quality-score": ""}
    for _, output_name in DIMENSION_SCORE_OUTPUTS:
        scores[output_name] = ""
    return scores


def extract_report_scores(report_doc: Mapping[str, Any] | None) -> dict[str, str]:
    """Extract quality and dimension scores from a saved ``--report`` profile JSON."""
    scores = empty_scores()
    if not isinstance(report_doc, Mapping):
        return scores
    quality = report_doc.get("quality")
    if not isinstance(quality, Mapping):
        return scores
    score_block = quality.get("scores")
    if not isinstance(score_block, Mapping):
        return scores

    scores["quality-score"] = _format_score(score_block.get("overall_score"))
    dimension_scores = score_block.get("dimension_scores")
    if isinstance(dimension_scores, Mapping):
        for dim_name, output_name in DIMENSION_SCORE_OUTPUTS:
            scores[output_name] = _format_score(dimension_scores.get(dim_name))
    return scores


def _count_checks(checks: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    violations = sum(1 for check in checks if check.get("status") == "failed")
    unevaluated = sum(1 for check in checks if check.get("status") == "not_evaluated")
    return violations, unevaluated


@dataclass(frozen=True)
class ParsedResult:
    """Normalized metrics and action outputs derived from dataprof's JSON output."""

    kind: str  # "single", "multi", or "error"
    verdict: str
    files_analyzed: int
    violations_count: int
    unevaluated_count: int
    errors_count: int
    skipped_count: int
    scores: dict[str, str]
    outputs: dict[str, str]


def parse_check_document(
    doc: Mapping[str, Any],
    *,
    report_doc: Mapping[str, Any] | None = None,
    file_input: str = "",
    export_json_path: str = "",
    report_path: str = "",
    analysis_summary: str = "",
) -> ParsedResult:
    """Parse a ``dataprof.check --json`` document into action outputs.

    The verdict is always read directly from dataprof (or ``"error"`` for a
    top-level error document). Scores are populated only for single-source runs
    when a saved profile report is available; absent scores are empty strings.
    """
    if "error" in doc and "verdict" not in doc:
        kind = "error"
        verdict = "error"
        files_analyzed = 0
        violations_count = 0
        unevaluated_count = 0
        errors_count = 1
        skipped_count = 0
        scores = empty_scores()
        effective_report_path = ""
    elif "sources" in doc:
        kind = "multi"
        verdict = str(doc.get("verdict", "error"))
        sources_list = doc.get("sources") or []
        skipped_list = doc.get("skipped") or []
        files_analyzed = 0
        violations_count = 0
        unevaluated_count = 0
        errors_count = 0
        for entry in sources_list:
            if not isinstance(entry, Mapping):
                continue
            if "result" in entry and isinstance(entry["result"], Mapping):
                files_analyzed += 1
                v, u = _count_checks(entry["result"].get("checks") or [])
                violations_count += v
                unevaluated_count += u
            elif "error" in entry:
                errors_count += 1
        skipped_count = len(skipped_list)
        scores = empty_scores()
        effective_report_path = ""
    else:
        kind = "single"
        verdict = str(doc.get("verdict", "error"))
        checks = doc.get("checks") or []
        violations_count, unevaluated_count = _count_checks(checks)
        files_analyzed = 1
        errors_count = 0
        skipped_count = 0
        scores = extract_report_scores(report_doc)
        effective_report_path = report_path

    outputs: dict[str, str] = {
        "verdict": verdict,
        **scores,
        "violations-count": str(violations_count),
        "unevaluated-count": str(unevaluated_count),
        "errors-count": str(errors_count),
        "skipped-count": str(skipped_count),
        "file-path": file_input,
        "files-analyzed": str(files_analyzed),
        "json-export-path": export_json_path,
        "report-path": effective_report_path,
        "analysis-summary": analysis_summary,
    }
    return ParsedResult(
        kind=kind,
        verdict=verdict,
        files_analyzed=files_analyzed,
        violations_count=violations_count,
        unevaluated_count=unevaluated_count,
        errors_count=errors_count,
        skipped_count=skipped_count,
        scores=scores,
        outputs=outputs,
    )


def determine_step_exit_code(
    dataprof_exit_code: int,
    *,
    fail_on_issues: bool,
    fail_on_inconclusive: bool,
) -> int:
    """Map dataprof's exit code to the GitHub Action step exit code.

    - 0 (pass): always 0
    - 1 (fail): 1 when ``fail_on_issues`` is true, else 0
    - 2 (inconclusive): 2 when ``fail_on_inconclusive`` is true, else 0
    - 3 (error) or any other code: always non-zero
    """
    if dataprof_exit_code == 0:
        return 0
    if dataprof_exit_code == 1:
        return 1 if fail_on_issues else 0
    if dataprof_exit_code == 2:
        return 2 if fail_on_inconclusive else 0
    return dataprof_exit_code


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def format_expected(expected: Mapping[str, Any] | None) -> str:
    """Format a check's ``expected`` object for Markdown display."""
    if not isinstance(expected, Mapping):
        return "-"
    comparison = expected.get("comparison", "")
    value = expected.get("value")
    if comparison == "at_least" and value is not None:
        return f">= {value}"
    if comparison == "at_most" and value is not None:
        return f"<= {value}"
    if comparison == "change_at_least" and value is not None:
        return f"change >= {value}"
    if comparison == "change_at_most" and value is not None:
        return f"change <= {value}"
    if comparison == "relative_change_at_least" and value is not None:
        return f"relative change >= {value}%"
    if comparison == "relative_change_at_most" and value is not None:
        return f"relative change <= {value}%"
    if comparison == "analyzed":
        return "analyzed"
    if comparison == "present":
        return "present"
    if comparison == "in_baseline":
        return "in baseline"
    if value is not None:
        return f"{comparison} {value}"
    return str(comparison) if comparison else "-"


def format_check_target(check: Mapping[str, Any]) -> str:
    """Format the column, dimension, or finding target of a check."""
    if check.get("column") is not None:
        return f"column `{check['column']}`"
    if check.get("dimension") is not None:
        return f"dimension `{check['dimension']}`"
    if check.get("finding") is not None:
        return f"finding `{check['finding']}`"
    return "-"


def format_check_status(check: Mapping[str, Any]) -> str:
    """Format a check status without ever substituting 0 for unevaluated."""
    raw = str(check.get("status", ""))
    label = _STATUS_LABELS.get(raw, raw or "unknown")
    if raw == "not_evaluated":
        parts = [str(check[key]) for key in ("reason", "gap") if check.get(key)]
        if parts:
            return f"{label} ({': '.join(parts)})"
    return label


def format_check_observed(check: Mapping[str, Any]) -> str:
    """Format the observed value of a check. Absent values never show as 0."""
    observed = check.get("observed")
    baseline = check.get("baseline")
    if observed is None:
        status = check.get("status")
        if status == "not_evaluated":
            return "unevaluated"
        if status == "not_applicable":
            return "not applicable"
        return "-"
    text = str(observed)
    if isinstance(baseline, Mapping) and baseline.get("change") is not None:
        text = f"{text} (change: {baseline['change']})"
    return text


def _format_evidence(evidence: Mapping[str, Any] | None) -> str:
    if not isinstance(evidence, Mapping):
        return "-"
    coverage = str(evidence.get("coverage", ""))
    reason = evidence.get("reason")
    if coverage and reason:
        return f"`{coverage}` ({reason})"
    if coverage:
        return f"`{coverage}`"
    return "-"


def _render_source_section(path_label: str, result: Mapping[str, Any]) -> list[str]:
    lines = [
        f"### Source: `{_md_escape(path_label)}`",
        "",
        f"- **Verdict**: `{result.get('verdict', 'unknown')}`",
        f"- **Scope**: `{result.get('scope', '-')}`",
        f"- **Evidence**: {_format_evidence(result.get('evidence'))}",
    ]
    if result.get("baseline_missing"):
        lines.append("- **Baseline**: none (missing baseline allowed)")
    elif isinstance(result.get("baseline"), Mapping):
        reports = result["baseline"].get("reports") or {}
        base_info = reports.get("a") if isinstance(reports, Mapping) else None
        if isinstance(base_info, Mapping) and base_info.get("source"):
            lines.append(f"- **Baseline**: `{_md_escape(str(base_info['source']))}`")
        else:
            lines.append("- **Baseline**: compared against baseline report")

    checks = result.get("checks") or []
    lines.append("")
    if checks:
        lines.append("| Check | Target | Status | Observed | Expected | Detail |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            code = _md_escape(str(check.get("code", "")))
            target = _md_escape(format_check_target(check))
            status = _md_escape(format_check_status(check))
            observed = _md_escape(format_check_observed(check))
            expected = _md_escape(format_expected(check.get("expected")))
            message = _md_escape(str(check.get("message", "")))
            lines.append(
                f"| `{code}` | {target} | {status} | {observed} | {expected} | {message} |"
            )
    else:
        lines.append("No checks reported.")

    baseline_obj = result.get("baseline")
    if isinstance(baseline_obj, Mapping):
        diagnostics = baseline_obj.get("diagnostics") or []
        if diagnostics:
            lines.append("")
            lines.append("**Baseline diagnostics:**")
            lines.append("")
            for diag in diagnostics:
                if not isinstance(diag, Mapping):
                    continue
                code = diag.get("code", "diagnostic")
                col = diag.get("column")
                col_suffix = f" [`{col}`]" if col else ""
                msg = diag.get("message", "")
                lines.append(f"- `{code}`{col_suffix}: {msg}")

    return lines


def _render_scores_section(scores: Mapping[str, str]) -> list[str]:
    lines = [
        "### Profile Scores",
        "",
        "| Metric | Score |",
        "| --- | --- |",
    ]
    overall = scores.get("quality-score", "")
    lines.append(f"| Overall quality | {overall if overall != '' else 'not analyzed'} |")
    for dim_name, output_name in DIMENSION_SCORE_OUTPUTS:
        val = scores.get(output_name, "")
        label = dim_name.capitalize()
        lines.append(f"| {label} | {val if val != '' else 'not analyzed'} |")
    return lines


def _extract_generator_version(doc: Mapping[str, Any]) -> str:
    generator = doc.get("generator")
    if isinstance(generator, Mapping) and generator.get("version"):
        return str(generator["version"])
    sources = doc.get("sources")
    if isinstance(sources, list):
        for entry in sources:
            if isinstance(entry, Mapping) and isinstance(entry.get("result"), Mapping):
                gen = entry["result"].get("generator")
                if isinstance(gen, Mapping) and gen.get("version"):
                    return str(gen["version"])
    return ""


def render_step_summary(
    parsed: ParsedResult,
    doc: Mapping[str, Any],
    *,
    file_label: str = "",
    report_doc: Mapping[str, Any] | None = None,
    installed_version: str = "",
) -> str:
    """Render the Markdown job summary for ``GITHUB_STEP_SUMMARY``."""
    lines = [
        f"## DataProf Quality Gate: `{parsed.verdict}`",
        "",
        f"- **Verdict**: `{parsed.verdict}`",
        f"- **Files analyzed**: {parsed.files_analyzed}",
        (
            f"- **Violations**: {parsed.violations_count} | "
            f"**Unevaluated**: {parsed.unevaluated_count} | "
            f"**Errors**: {parsed.errors_count} | "
            f"**Skipped**: {parsed.skipped_count}"
        ),
    ]
    version = installed_version or _extract_generator_version(doc)
    if version:
        lines.append(f"- **dataprof**: `{version}`")
    if parsed.outputs.get("json-export-path"):
        lines.append(f"- **JSON export**: `{parsed.outputs['json-export-path']}`")

    if parsed.kind == "error":
        error = doc.get("error") if isinstance(doc.get("error"), Mapping) else {}
        lines.extend(["", "### Error", ""])
        if error.get("kind"):
            lines.append(f"- **Kind**: `{error['kind']}`")
        if error.get("path"):
            lines.append(f"- **Path**: `{_md_escape(str(error['path']))}`")
        raw_msg = str(error.get("message", "Unknown error"))
        clean_msg = " ".join(part.strip() for part in raw_msg.splitlines() if part.strip())
        lines.append(f"- **Message**: {clean_msg or 'Unknown error'}")
        return "\n".join(lines) + "\n"

    if parsed.kind == "single":
        if report_doc is not None:
            lines.append("")
            lines.extend(_render_scores_section(parsed.scores))
        source_path = file_label or parsed.outputs.get("file-path", "") or "(source)"
        lines.append("")
        lines.extend(_render_source_section(source_path, doc))
        return "\n".join(lines) + "\n"

    # Multi-source document
    error_entries: list[tuple[str, Mapping[str, Any]]] = []
    for entry in doc.get("sources") or []:
        if not isinstance(entry, Mapping):
            continue
        path = str(entry.get("path", "(unknown)"))
        if isinstance(entry.get("result"), Mapping):
            lines.append("")
            lines.extend(_render_source_section(path, entry["result"]))
        elif isinstance(entry.get("error"), Mapping):
            error_entries.append((path, entry["error"]))

    if error_entries:
        lines.extend(
            [
                "",
                "### Source Errors",
                "",
                "| Path | Kind | Message |",
                "| --- | --- | --- |",
            ]
        )
        for path, err in error_entries:
            kind = _md_escape(str(err.get("kind", "error")))
            msg = _md_escape(str(err.get("message", "")))
            lines.append(f"| `{_md_escape(path)}` | `{kind}` | {msg} |")

    skipped = doc.get("skipped") or []
    if skipped:
        lines.extend(
            [
                "",
                "### Skipped Files",
                "",
                "| Path | Reason |",
                "| --- | --- |",
            ]
        )
        for item in skipped:
            if not isinstance(item, Mapping):
                continue
            path = _md_escape(str(item.get("path", "")))
            raw_reason = str(item.get("reason", ""))
            reason = _md_escape(SKIP_REASON_LABELS.get(raw_reason, raw_reason))
            lines.append(f"| `{path}` | {reason} |")

    return "\n".join(lines) + "\n"


def build_text_summary(parsed: ParsedResult, doc: Mapping[str, Any], stderr: str) -> str:
    """Build the compact plain-text value for the ``analysis-summary`` output."""
    cleaned_stderr = stderr.strip()
    if cleaned_stderr:
        return cleaned_stderr
    if parsed.kind == "error":
        err = doc.get("error") if isinstance(doc.get("error"), Mapping) else {}
        return f"error ({err.get('kind', 'error')}): {err.get('message', 'Unknown error')}"
    return (
        f"verdict: {parsed.verdict} "
        f"(files_analyzed={parsed.files_analyzed}, "
        f"violations={parsed.violations_count}, "
        f"unevaluated={parsed.unevaluated_count}, "
        f"errors={parsed.errors_count}, "
        f"skipped={parsed.skipped_count})"
    )


def write_github_output(output_file: Path, outputs: Mapping[str, str]) -> None:
    """Append key-value pairs to ``GITHUB_OUTPUT``, using heredocs for multiline values."""
    with output_file.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in outputs.items():
            if "\n" in value or "\r" in value:
                delimiter = f"EOF_{uuid.uuid4().hex}"
                handle.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                handle.write(f"{key}={value}\n")


def write_step_summary(summary_file: Path, markdown: str) -> None:
    """Append the Markdown summary to ``GITHUB_STEP_SUMMARY``."""
    with summary_file.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown)


def _export_json(export_path: Path, raw_text: str) -> None:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(raw_text, encoding="utf-8")


def _emit_error_run(
    *,
    kind: str,
    message: str,
    file_input: str,
    export_json_path: str,
    env: Mapping[str, str],
    installed_version: str = "",
) -> int:
    doc: dict[str, Any] = {"error": {"kind": kind, "message": message}}
    raw_json = json.dumps(doc, indent=2) + "\n"
    written_export = ""
    if export_json_path:
        _export_json(Path(export_json_path), raw_json)
        written_export = export_json_path

    analysis_summary = f"error ({kind}): {message}"
    parsed = parse_check_document(
        doc,
        file_input=file_input,
        export_json_path=written_export,
        analysis_summary=analysis_summary,
    )
    summary_md = render_step_summary(
        parsed,
        doc,
        file_label=file_input,
        installed_version=installed_version,
    )
    if env.get("GITHUB_OUTPUT"):
        write_github_output(Path(env["GITHUB_OUTPUT"]), parsed.outputs)
    if env.get("GITHUB_STEP_SUMMARY"):
        write_step_summary(Path(env["GITHUB_STEP_SUMMARY"]), summary_md)
    print(f"::error::dataprof check failed ({kind}): {message}", file=sys.stderr)
    return 3


def run_action(
    env: Mapping[str, str] | None = None,
    *,
    python_executable: str | None = None,
) -> int:
    """Execute the action end to end using environment variables."""
    active_env = os.environ if env is None else env
    py = python_executable or sys.executable

    try:
        config = ActionConfig.from_env(active_env)
    except ActionInputError as exc:
        return _emit_error_run(
            kind="argument",
            message=str(exc),
            file_input=active_env.get("INPUT_FILE", "").strip(),
            export_json_path=active_env.get("INPUT_EXPORT_JSON_PATH", "").strip(),
            env=active_env,
            installed_version=active_env.get("INPUT_DATAPROF_VERSION", "").strip(),
        )

    try:
        sources, unmatched_globs = expand_sources(config.file)
    except ActionInputError as exc:
        return _emit_error_run(
            kind="argument",
            message=str(exc),
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    if unmatched_globs:
        patterns = ", ".join(unmatched_globs)
        return _emit_error_run(
            kind="input",
            message=f"no files matched glob pattern(s): {patterns}",
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    if not sources:
        return _emit_error_run(
            kind="argument",
            message="no source paths provided",
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    single = is_single_source_invocation(sources)
    report_path: Path | None = None
    if single:
        temp_root = Path(active_env.get("RUNNER_TEMP") or tempfile.gettempdir())
        temp_root.mkdir(parents=True, exist_ok=True)
        report_path = temp_root / f"dataprof-report-{uuid.uuid4().hex}.json"

    cmd = build_check_command(
        config,
        sources,
        python_executable=py,
        report_path=report_path,
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if proc.stderr:
        sys.stderr.write(proc.stderr)
        if not proc.stderr.endswith("\n"):
            sys.stderr.write("\n")

    stdout_text = proc.stdout.strip()
    if not stdout_text:
        detail = proc.stderr.strip() or f"dataprof.check exited with code {proc.returncode}"
        return _emit_error_run(
            kind="runtime",
            message=detail,
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    try:
        doc = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        return _emit_error_run(
            kind="runtime",
            message=f"invalid JSON from dataprof.check: {exc}",
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    if not isinstance(doc, Mapping):
        return _emit_error_run(
            kind="runtime",
            message="unexpected non-object JSON document from dataprof.check",
            file_input=config.file,
            export_json_path=config.export_json_path,
            env=active_env,
            installed_version=config.dataprof_version,
        )

    written_export = ""
    if config.export_json_path:
        _export_json(Path(config.export_json_path), proc.stdout)
        written_export = config.export_json_path

    report_doc: Mapping[str, Any] | None = None
    effective_report_path = ""
    if report_path is not None and report_path.is_file():
        report_doc = json.loads(report_path.read_text(encoding="utf-8"))
        effective_report_path = str(report_path)

    provisional = parse_check_document(
        doc,
        report_doc=report_doc,
        file_input=config.file,
        export_json_path=written_export,
        report_path=effective_report_path,
    )
    analysis_summary = build_text_summary(provisional, doc, proc.stderr)
    parsed = parse_check_document(
        doc,
        report_doc=report_doc,
        file_input=config.file,
        export_json_path=written_export,
        report_path=effective_report_path,
        analysis_summary=analysis_summary,
    )

    file_label = sources[0] if single else config.file
    summary_md = render_step_summary(
        parsed,
        doc,
        file_label=file_label,
        report_doc=report_doc,
        installed_version=config.dataprof_version,
    )

    if active_env.get("GITHUB_OUTPUT"):
        write_github_output(Path(active_env["GITHUB_OUTPUT"]), parsed.outputs)
    if active_env.get("GITHUB_STEP_SUMMARY"):
        write_step_summary(Path(active_env["GITHUB_STEP_SUMMARY"]), summary_md)

    step_exit = determine_step_exit_code(
        proc.returncode,
        fail_on_issues=config.fail_on_issues,
        fail_on_inconclusive=config.fail_on_inconclusive,
    )
    if proc.returncode == 1 and step_exit == 0:
        print("::warning::dataprof reported a policy violation (fail-on-issues is false)")
    elif proc.returncode == 2 and step_exit == 0:
        print("::warning::dataprof reported an inconclusive gate (fail-on-inconclusive is false)")
    return step_exit


def main() -> int:
    return run_action()


if __name__ == "__main__":
    raise SystemExit(main())
