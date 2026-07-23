"""Command-line interface for orator.

Examples:
  orator sample.json --html report.html --json report.json
  orator talk.wav --backend faster-whisper --acoustic --html report.html
  orator talk.wav --llm --effort high --html report.html
  orator talk.wav --backend crisper-whisper --allow-noncommercial
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import Config, load_config
from .pipeline import run_on_transcript
from .report import render_html, render_json


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orator", description="Grade a speech sample.")
    p.add_argument("input", help="audio (.wav/.mp3/...), Transcript JSON (.json), or text (.txt/.md/.vtt/.srt)")
    p.add_argument("--config", help="YAML/JSON config file", default=None)
    p.add_argument("--backend", default=None,
                   choices=["faster-whisper", "crisper-whisper", "vosk"],
                   help="ASR backend (default: faster-whisper)")
    p.add_argument("--allow-noncommercial", action="store_true",
                   help="permit CC BY-NC backends (CrisperWhisper)")
    p.add_argument("--llm", dest="use_llm", action="store_true",
                   help="use Claude for word-choice (needs ANTHROPIC_API_KEY); else offline")
    p.add_argument("--offline", dest="use_llm", action="store_false",
                   help="force the offline lexicon word-choice analyzer")
    p.add_argument("--effort", default=None, choices=["low", "medium", "high"],
                   help="LLM effort (default: high)")
    p.add_argument("--wordchoice-json", default=None,
                   help="agent-handoff: use word-choice findings from this JSON (no API key)")
    p.add_argument("--emit-request", nargs="?", const=True, default=None,
                   help="also write the agent word-choice request packet "
                        "(default <input>.llm-request.json)")
    p.add_argument("--acoustic", action="store_true", help="enable the prosody track")
    p.add_argument("--html", default=None, help="write an HTML report to this path")
    p.add_argument("--json", dest="json_out", default=None,
                   help="write a JSON report to this path")
    p.add_argument("--log", default=None,
                   help="append a one-line summary row to this markdown ledger "
                        "(circles every grade back to one place)")
    p.set_defaults(use_llm=None)
    return p


def _config_from_args(args) -> Config:
    cfg = load_config(args.config)
    if args.backend:
        cfg.asr_backend = args.backend
    if args.allow_noncommercial:
        cfg.allow_noncommercial = True
    if args.use_llm is not None:
        cfg.use_llm = args.use_llm
    if args.effort:
        cfg.llm_effort = args.effort
    if args.acoustic:
        cfg.enable_acoustic = True
    if args.wordchoice_json:
        cfg.wordchoice_json = args.wordchoice_json
    return cfg


_LOG_HEADER = (
    "# orator grading ledger\n\n"
    "Every transcript graded across the workspace, newest rows appended at the bottom.\n\n"
    "| date | source | overall | weakest dimensions | word-choice mode |\n"
    "|------|--------|---------|--------------------|------------------|\n"
)


def _append_log(log_path: str, source: str, report) -> None:
    """Append a one-line summary row to a markdown ledger (creating it if absent)."""
    import datetime
    import os

    weak = sorted(report.dimensions, key=lambda d: d.points)[:2]
    weak_str = ", ".join(f"{d.dimension} {round(d.points)}" for d in weak) or "n/a"
    date = datetime.date.today().isoformat()
    row = (
        f"| {date} | {os.path.basename(source)} | {report.overall_score}/100 "
        f"| {weak_str} | {report.metadata.get('word_choice_mode', '?')} |\n"
    )
    new = not os.path.exists(log_path)
    parent = os.path.dirname(log_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        if new:
            fh.write(_LOG_HEADER)
        fh.write(row)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "grade":  # tolerate an optional "grade" subcommand
        argv = argv[1:]
    args = _build_parser().parse_args(argv)
    cfg = _config_from_args(args)

    from .pipeline import load_input

    t = load_input(args.input, cfg)

    if args.emit_request is not None:
        import json as _json

        from .wordchoice.llm import build_handoff_request

        req_path = (
            args.emit_request if isinstance(args.emit_request, str)
            else args.input + ".llm-request.json"
        )
        with open(req_path, "w", encoding="utf-8") as fh:
            _json.dump(build_handoff_request(t, cfg), fh, indent=2)
        print(f"wrote word-choice request packet: {req_path}")
        print("  (an agent fills {\"findings\": [...]} -> save as a response JSON, "
              "then re-run with --wordchoice-json <response>)")

    report = run_on_transcript(t, cfg)

    if args.json_out:
        render_json(report, args.json_out)
    if args.html:
        render_html(report, args.html)
    if args.log:
        _append_log(args.log, args.input, report)

    print(report.summary)
    for d in report.dimensions:
        print(f"  {d.dimension:<12} {round(d.points):>3}/100  ({d.band})")
    if not args.html and not args.json_out:
        print("\n(tip: pass --html report.html for the highlighted transcript)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
