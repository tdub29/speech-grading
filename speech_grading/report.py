"""Render a graded :class:`Report` to JSON and to a self-contained HTML page.

The HTML highlights the transcript inline -- fillers, hedges, repetitions, and
tripped-up moments are color-coded with hover text explaining each flag and the
suggested stronger word -- above a per-dimension breakdown and a flat metric bag.
No external assets: a single file you can open in any browser.
"""

from __future__ import annotations

import html
import json

from jinja2 import Template

from .schema import Finding, Report

# Per-word coloring priority (first match wins for the word's class).
_KIND_PRIORITY = ["tripped_up", "filler", "hedge", "weasel", "intensifier", "weak_word",
                  "repetition", "false_start"]

_KIND_CLASS = {
    "tripped_up": "f-tripped",
    "filler": "f-filler",
    "hedge": "f-weak",
    "weasel": "f-weak",
    "intensifier": "f-weak",
    "weak_word": "f-weak",
    "repetition": "f-repeat",
    "false_start": "f-repeat",
}

_PAGE = Template(
    """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>orator report</title>
<style>
  :root { --ink:#1c1c1e; --muted:#6b7280; --line:#e5e7eb; --bg:#fbfbfa; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:40px 24px 80px; }
  h1 { font-size:22px; margin:0 0 2px; letter-spacing:-.01em; }
  .sub { color:var(--muted); margin:0 0 28px; }
  .score { display:flex; align-items:baseline; gap:12px; margin:0 0 24px; }
  .score .big { font-size:54px; font-weight:700; letter-spacing:-.02em; }
  .score .of { color:var(--muted); font-size:18px; }
  .summary { background:#fff; border:1px solid var(--line); border-radius:12px;
             padding:14px 16px; margin:0 0 28px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em;
       color:var(--muted); margin:30px 0 12px; }
  .dim { display:grid; grid-template-columns:140px 1fr 64px; align-items:center;
         gap:12px; margin:8px 0; }
  .dim .name { font-weight:600; }
  .bar { height:10px; background:#eef0f2; border-radius:6px; overflow:hidden; }
  .bar > i { display:block; height:100%; border-radius:6px; }
  .pts { text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); }
  .b-excellent { background:#16a34a; } .b-good { background:#65a30d; }
  .b-fair { background:#d97706; } .b-poor { background:#dc2626; }
  .transcript { background:#fff; border:1px solid var(--line); border-radius:12px;
                padding:18px 20px; line-height:2.1; }
  .transcript span { border-radius:4px; padding:1px 1px; }
  .f-filler  { background:#fde68a; }
  .f-weak    { background:#dbeafe; border-bottom:2px solid #3b82f6; }
  .f-tripped { background:#fecaca; border-bottom:2px solid #dc2626; }
  .f-repeat  { background:#ede9fe; border-bottom:2px solid #8b5cf6; }
  .pause { color:#dc2626; font-size:11px; font-weight:600; opacity:.8;
           padding:0 4px; white-space:nowrap; }
  .legend { display:flex; flex-wrap:wrap; gap:14px; color:var(--muted);
            font-size:12px; margin:14px 0 0; }
  .legend i { display:inline-block; width:11px; height:11px; border-radius:3px;
              margin-right:5px; vertical-align:-1px; }
  table.metrics { width:100%; border-collapse:collapse; font-size:13px; }
  table.metrics td { padding:6px 8px; border-bottom:1px solid var(--line); }
  table.metrics td:first-child { color:var(--muted); width:55%; }
  table.metrics td:last-child { text-align:right; font-variant-numeric:tabular-nums; }
  .findings li { margin:4px 0; }
  .findings .sg { color:#16a34a; }
  code { background:#f3f4f6; padding:1px 5px; border-radius:4px; }
</style></head>
<body><div class="wrap">
  <h1>orator &mdash; speech report</h1>
  <p class="sub">engine: {{ engine }} &nbsp;&middot;&nbsp; word-choice: {{ mode }}
     &nbsp;&middot;&nbsp; {{ total_words }} words / {{ duration }}s</p>

  <div class="score"><span class="big">{{ overall }}</span><span class="of">/ 100</span></div>
  <div class="summary">{{ summary }}</div>

  <h2>Dimensions</h2>
  {% for d in dims %}
  <div class="dim">
    <span class="name">{{ d.label }}</span>
    <span class="bar"><i class="b-{{ d.band }}" style="width:{{ d.pct }}%"></i></span>
    <span class="pts">{{ d.points }}</span>
  </div>
  {% endfor %}

  <h2>Transcript</h2>
  <div class="transcript">{{ transcript_html }}</div>
  <div class="legend">
    <span><i class="f-filler"></i>filler</span>
    <span><i class="f-weak"></i>weak / hedge</span>
    <span><i class="f-tripped"></i>tripped up</span>
    <span><i class="f-repeat"></i>repetition</span>
    <span class="pause">&#10629;pause&#10630;</span>
  </div>

  {% if suggestions %}
  <h2>Stronger word suggestions</h2>
  <ul class="findings">
    {% for s in suggestions %}
    <li><code>{{ s.original }}</code>
        {% if s.suggestion %}&rarr; <span class="sg">{{ s.suggestion }}</span>{% else %}(cut it){% endif %}
        &nbsp;<span class="sub">{{ s.rationale }}</span></li>
    {% endfor %}
  </ul>
  {% endif %}

  {% if visual %}
  <h2>Video cues (counts, not scored)</h2>
  <ul class="findings">
    {% for f in visual %}
    <li><code>{{ "%d:%02d"|format(f.start // 60, f.start % 60) }}</code> {{ f.kind.replace("_", " ") }}
        &nbsp;<span class="sub">{{ f.rationale }}</span></li>
    {% endfor %}
  </ul>
  {% endif %}

  <h2>Metrics</h2>
  <table class="metrics">
    {% for k, v in metrics %}<tr><td>{{ k }}</td><td>{{ v }}</td></tr>{% endfor %}
  </table>
</div></body></html>"""
)

_DIM_LABELS = {
    "fillers": "Fillers", "pace": "Pace", "pauses": "Pauses / fluency",
    "word_choice": "Word choice", "vocabulary": "Vocabulary",
    "hedging": "Hedging", "readability": "Readability", "prosody": "Prosody",
}


def highlight_transcript_html(report: Report) -> str:
    """Build the inline-highlighted transcript HTML (spans + pause markers)."""
    t = report.transcript
    n = len(t.words)

    # Map each word index to the findings that color it.
    per_word: dict[int, list[Finding]] = {i: [] for i in range(n)}
    pause_before: dict[int, Finding] = {}
    for f in report.findings:
        if f.kind == "long_pause":
            pause_before[f.word_index] = f
            continue
        a, b = f.resolved_span()
        for i in range(max(0, a), min(n - 1, b) + 1):
            per_word[i].append(f)

    out: list[str] = []
    for i, w in enumerate(t.words):
        if i in pause_before:
            pf = pause_before[i]
            secs = pf.end - pf.start
            out.append(
                f'<span class="pause" title="{html.escape(pf.rationale)}">'
                f'&#10629;{secs:.1f}s&#10630;</span> '
            )
        text = html.escape(w.text)
        fs = per_word.get(i, [])
        if fs:
            kind = _primary_kind(fs)
            cls = _KIND_CLASS.get(kind, "")
            title = " | ".join(
                html.escape(x.rationale or x.kind) for x in fs if x.rationale
            )
            sug = next((x.suggestion for x in fs if x.suggestion), None)
            if sug:
                title = (title + f"  -> {html.escape(sug)}").strip(" |")
            out.append(f'<span class="{cls}" title="{title}">{text}</span> ')
        else:
            out.append(text + " ")
    return "".join(out).strip()


def _primary_kind(findings: list[Finding]) -> str:
    kinds = {f.kind for f in findings}
    for k in _KIND_PRIORITY:
        if k in kinds:
            return k
    return next(iter(kinds))


def render_html(report: Report, out_path: str) -> None:
    dims = [
        {
            "label": _DIM_LABELS.get(d.dimension, d.dimension),
            "band": d.band,
            "points": round(d.points),
            "pct": round(d.points),
        }
        for d in report.dimensions
    ]
    suggestions = []
    _seen_sug: set[str] = set()
    for f in report.findings:
        if f.kind not in ("tripped_up", "weak_word", "hedge") or f.suggestion is None:
            continue
        key = f.original.strip().lower()
        if key in _seen_sug:
            continue
        _seen_sug.add(key)
        suggestions.append(
            {"original": f.original, "suggestion": f.suggestion or "", "rationale": f.rationale}
        )
        if len(suggestions) >= 25:
            break
    html_doc = _PAGE.render(
        engine=report.metadata.get("engine", "?"),
        mode=report.metadata.get("word_choice_mode", "?"),
        total_words=report.transcript.total_words,
        duration=round(report.transcript.duration_sec, 1),
        overall=report.overall_score,
        summary=report.summary,
        dims=dims,
        transcript_html=highlight_transcript_html(report),
        suggestions=suggestions,
        visual=[f for f in report.findings if f.word_index < 0],
        metrics=sorted(report.metrics.items()),
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)


def render_json(report: Report, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report.model_dump_json(indent=2))


# --------------------------------------------------------------------------- #
# Group report (one page for a multi-speaker run; per-speaker pages use render_html)
# --------------------------------------------------------------------------- #

_WEAK_DIMS = ("pace", "pauses")

_GROUP_PAGE = Template(
    """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>orator group report</title>
<style>
  :root { --ink:#1c1c1e; --muted:#6b7280; --line:#e5e7eb; --bg:#fbfbfa; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width:960px; margin:0 auto; padding:40px 16px 80px; }
  h1 { font-size:22px; margin:0 0 2px; }
  .sub { color:var(--muted); margin:0 0 24px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em;
       color:var(--muted); margin:30px 0 12px; }
  .scroll { overflow-x:auto; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  td, th { padding:6px 8px; border-bottom:1px solid var(--line); text-align:right;
           font-variant-numeric:tabular-nums; white-space:nowrap; }
  td:first-child, th:first-child, td.l, th.l { text-align:left; }
  th { color:var(--muted); font-weight:600; }
  .share { display:grid; grid-template-columns:140px 1fr 56px; gap:12px; align-items:center; margin:6px 0; }
  .bar { height:10px; background:#eef0f2; border-radius:6px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:#2563eb; border-radius:6px; }
  .muted { color:var(--muted); }
  .note { background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 16px; font-size:13px; }
  dl { font-size:13px; } dt { font-weight:600; margin-top:8px; } dd { margin:2px 0 0 0; color:var(--muted); }
</style></head>
<body><div class="wrap">
  <h1>orator: group report</h1>
  <p class="sub">{{ g.speakers }} speakers &middot; share basis: {{ g.share_basis }}
     &middot; word timing: {{ "yes" if g.timing else "no (timing metrics n/a)" }}</p>

  <h2>Leaderboard</h2>
  <div class="scroll"><table>
    <tr><th>#</th><th class="l">speaker</th><th>overall</th><th>words</th><th>talk share</th>
        <th>floor turns</th><th>longest turn s</th><th>latency median s</th>
        <th>overlaps made / received</th><th>backchannels</th></tr>
    {% for r in leaderboard %}{% set p = per[r.speaker] %}
    <tr><td>{{ loop.index }}</td><td class="l"><a href="{{ r.file }}">{{ r.speaker }}</a></td>
        <td>{{ r.overall }}</td><td>{{ r.words }}</td><td>{{ "%.0f"|format(p.share * 100) }}%</td>
        <td>{{ p.floor_turns }}</td><td>{{ na(p.longest_turn_s) }}</td><td>{{ na(p.response_latency_median_s) }}</td>
        <td>{{ na(p.overlaps_made) }} / {{ na(p.overlaps_received) }}</td><td>{{ p.backchannels }}</td></tr>
    {% endfor %}
    {% for s, n in not_graded.items() %}{% set p = per[s] %}
    <tr class="muted"><td>-</td><td class="l">{{ s }}</td><td>not graded</td><td>{{ n }} (&lt; {{ min_words }})</td>
        <td>{{ "%.0f"|format(p.share * 100) }}%</td><td>{{ p.floor_turns }}</td><td>{{ na(p.longest_turn_s) }}</td>
        <td>{{ na(p.response_latency_median_s) }}</td><td>{{ na(p.overlaps_made) }} / {{ na(p.overlaps_received) }}</td>
        <td>{{ p.backchannels }}</td></tr>
    {% endfor %}
  </table></div>
  <p class="muted" style="font-size:12px">Scores from short samples are noisy: compare word counts before comparing scores.</p>

  <h2>Talk share</h2>
  {% for s, p in per.items() %}
  <div class="share"><span>{{ s }}</span><span class="bar"><i style="width:{{ "%.1f"|format(p.share * 100) }}%"></i></span>
    <span class="muted">{{ "%.0f"|format(p.share * 100) }}%</span></div>
  {% endfor %}
  <p class="muted" style="font-size:12px">Balance (normalized entropy, 1 = even): {{ na(g.balance) }}
     &middot; floor turns {{ g.floor_turns }} &middot; backchannels {{ g.backchannels }}
     &middot; overlapping starts {{ na(g.overlapping_starts) }}
     &middot; median response latency {{ na(g.response_latency_median_s) }} s</p>

  {% if spread %}
  <h2>Spread per dimension</h2>
  <div class="scroll"><table>
    <tr><th class="l">dimension</th><th class="l">lowest</th><th>pts</th><th class="l">highest</th><th>pts</th><th>spread</th></tr>
    {% for d in spread %}
    <tr><td>{{ d.dimension }}{% if d.weak %} *{% endif %}</td><td class="l">{{ d.low }}</td><td>{{ d.low_pts }}</td>
        <td class="l">{{ d.high }}</td><td>{{ d.high_pts }}</td><td>{{ d.spread }}</td></tr>
    {% endfor %}
  </table></div>
  {% endif %}
  {% for n in notes %}<p class="note">* {{ n }}</p>{% endfor %}

  <h2>Definitions</h2>
  <dl>{% for k, v in definitions.items() %}<dt>{{ k }}</dt><dd>{{ v }}</dd>{% endfor %}</dl>
</div></body></html>""",
    autoescape=True,
)


def group_summary(res: dict) -> dict:
    """JSON-safe view of a grade_group result (Reports reduced to scores)."""
    per = res["per_speaker"]
    board = sorted(res["reports"].items(), key=lambda kv: -kv[1].overall_score)
    leaderboard = [
        {"speaker": s, "file": res["files"][s] + ".html", "overall": r.overall_score,
         "words": per[s]["words"], "share": per[s]["share"],
         "dimensions": {d.dimension: round(d.points, 1) for d in r.dimensions}}
        for s, r in board
    ]
    spread = []
    for d in sorted({d for row in leaderboard for d in row["dimensions"]}):
        pts = [(row["dimensions"][d], row["speaker"]) for row in leaderboard if d in row["dimensions"]]
        lo, hi = min(pts), max(pts)
        spread.append({"dimension": d, "low": lo[1], "low_pts": lo[0], "high": hi[1],
                       "high_pts": hi[0], "spread": round(hi[0] - lo[0], 1), "weak": d in _WEAK_DIMS})
    return {
        "leaderboard": leaderboard,
        "not_graded": res["not_graded"],
        "min_words": res["min_words"],
        "spread": spread,
        "per_speaker": per,
        "group": res["group"],
        "definitions": res["definitions"],
        "notes": res["notes"],
    }


def render_group_json(res: dict, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(group_summary(res), fh, indent=2)


def render_group_html(res: dict, out_path: str) -> None:
    s = group_summary(res)
    html_doc = _GROUP_PAGE.render(
        g=s["group"], per=s["per_speaker"], na=lambda v: "n/a" if v is None else v,
        leaderboard=s["leaderboard"], not_graded=s["not_graded"], min_words=s["min_words"],
        spread=s["spread"], notes=s["notes"], definitions=s["definitions"],
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
