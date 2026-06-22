"""Server-rendered HTML for the Radar feed. Plain Python string templates with every
dynamic value passed through ``html.escape`` — no templating engine, no new dep.

Guedes brand system: background #0A0A0A, accent #A3E635, monospace, /// separator.
Per CLAUDE.md the shared footer/favicon come from brand.js (not yet in the repo); we
do not hand-roll them here.
"""
from __future__ import annotations

from html import escape

from src.domain.entities import Lead

_BG = "#0A0A0A"
_ACCENT = "#A3E635"

_STYLE = f"""
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ background: {_BG}; color: #e6e6e6; font-family: ui-monospace, SFMono-Regular,
         Menlo, monospace; margin: 0; padding: 2rem; }}
  a {{ color: {_ACCENT}; }}
  h1, h2 {{ color: {_ACCENT}; font-weight: 600; }}
  .sep {{ color: {_ACCENT}; letter-spacing: 2px; }}
  .bar {{ display: flex; justify-content: space-between; align-items: baseline;
          border-bottom: 1px solid #222; padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  .balance {{ color: {_ACCENT}; font-size: 1.2rem; }}
  form.scan {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .6rem;
               background: #121212; padding: 1rem; border: 1px solid #222; border-radius: 8px; }}
  input, button {{ background: #0e0e0e; color: #e6e6e6; border: 1px solid #333;
                   padding: .5rem; border-radius: 6px; font-family: inherit; }}
  button {{ background: {_ACCENT}; color: {_BG}; font-weight: 700; cursor: pointer; border: 0; }}
  label.inline {{ display: flex; align-items: center; gap: .4rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
  th, td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #1d1d1d; }}
  th {{ color: #8a8a8a; font-weight: 500; }}
  .rank {{ color: {_ACCENT}; font-weight: 700; }}
  .badge {{ font-size: .7rem; padding: .1rem .4rem; border: 1px solid #444; border-radius: 4px;
            color: #b59; }}
  .pitch {{ white-space: pre-wrap; font-size: .8rem; color: #cfcfcf; max-width: 40ch; }}
  .msg {{ color: {_ACCENT}; margin-bottom: 1rem; }}
  .err {{ color: #ff6b6b; margin-bottom: 1rem; }}
  .note {{ color: #777; font-size: .8rem; margin-top: 2rem; }}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )


def render_login(error: str | None = None) -> str:
    err = f"<p class='err'>{escape(error)}</p>" if error else ""
    body = (
        "<h1>Lead<span class='sep'>///</span>Center</h1>"
        f"{err}"
        "<form method='post' action='/login'>"
        "<p><input type='password' name='password' placeholder='password' autofocus></p>"
        "<p><button type='submit'>Log in</button></p>"
        "</form>"
    )
    return _page("Login — Lead///Center", body)


def _fake_badge(source: str) -> str:
    if source == "fake":
        return " <span class='badge'>fake data</span>"
    return ""


def _pitch_cell(lead: Lead) -> str:
    """Either the drafted pitch text, or a Draft button to generate one."""
    if lead.pitch:
        return f"<div class='pitch'>{escape(lead.pitch)}</div>"
    return (
        f"<form method='post' action='/leads/{escape(lead.id)}/draft' style='margin:0'>"
        "<button type='submit'>Draft</button></form>"
    )


def render_dashboard(
    account_name: str, balance: int, leads: list[Lead],
    message: str | None = None, error: str | None = None,
) -> str:
    msg = f"<p class='msg'>{escape(message)}</p>" if message else ""
    err = f"<p class='err'>{escape(error)}</p>" if error else ""

    rows = "".join(
        "<tr>"
        f"<td class='rank'>{l.rank:.1f}</td>"
        f"<td>{'🔥 ' if l.hot_signal else ''}{escape(l.name)}{_fake_badge(l.source)}</td>"
        f"<td>{escape(l.category or '—')}</td>"
        f"<td>{l.opportunity}</td><td>{l.fit}</td><td>{l.confidence}</td>"
        f"<td>{_pitch_cell(l)}</td>"
        "</tr>"
        for l in leads
    ) or "<tr><td colspan='7'>No leads yet — run a scan above.</td></tr>"

    body = (
        "<div class='bar'>"
        f"<h1>Lead<span class='sep'>///</span>Center</h1>"
        f"<div><span class='balance'>{balance} credits</span> &nbsp; "
        f"{escape(account_name)} &nbsp; <a href='/logout'>logout</a></div>"
        "</div>"
        f"{msg}{err}"
        "<h2>Run a scan</h2>"
        "<form class='scan' method='post' action='/scan'>"
        "<input name='niche' placeholder='niche (e.g. plumbers)' required>"
        "<input name='city' placeholder='city (e.g. austin)' required>"
        "<input name='limit' type='number' min='1' value='10' required>"
        "<input name='keywords' placeholder='keywords (comma-sep)'>"
        "<label class='inline'><input type='checkbox' name='confirmed' value='1' checked> "
        "confirm spend</label>"
        "<button type='submit'>Scan</button>"
        "</form>"
        "<h2>Radar feed <span class='sep'>///</span> ranked leads</h2>"
        "<table><thead><tr>"
        "<th>rank</th><th>name</th><th>category</th><th>opp</th><th>fit</th>"
        "<th>conf</th><th>pitch</th>"
        "</tr></thead><tbody>"
        f"{rows}"
        "</tbody></table>"
        "<p class='note'>Leads marked “fake data” come from the placeholder provider. "
        "Wire the Outscraper adapter (see docs/GOLIVE.md) for real businesses.</p>"
    )
    return _page("Radar — Lead///Center", body)
