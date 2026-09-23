"""Shared look for the Streamlit surface. Tokens and anatomy from DESIGN.md,
identical to the landing-page demo so the two read as one product.

Fonts are served from ./static (Streamlit's static serving), never from a CDN:
the laptop build has to look right with the wifi off.
"""
from __future__ import annotations

import html

FONTS = ["ibm-plex-sans-400", "ibm-plex-sans-500", "ibm-plex-sans-600",
         "ibm-plex-mono-400", "ibm-plex-mono-500", "instrument-serif-400"]

TIER_CLASS = {"Ready now": "t-ready", "Ready in 1–2 years": "t-soon", "Emerging": "t-emerging"}
RISK_TONE = {"High": "risk", "Medium": "caution", "Low": "ready", "Leaving": "leaving"}


def _faces() -> str:
    out = []
    for f in FONTS:
        fam = ("IBM Plex Sans" if "sans" in f else
               "IBM Plex Mono" if "mono" in f else "Instrument Serif")
        weight = f.rsplit("-", 1)[1]
        out.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;"
                   "font-display:swap;src:url('app/static/fonts/%s.woff2') format('woff2');}"
                   % (fam, weight, f))
    return "".join(out)


CSS = """<style>
__FACES__
:root {
  --paper:#F7F5F1; --card:#FFFFFF; --ink:#16181C; --ink-2:#5A5F66; --ink-3:#8A8F97;
  --rule:#DED9D0; --rule-2:#EDE9E2; --graph:#14433E; --graph-soft:#E7EFEC;
  --ready:#1F6F4A; --caution:#8A6A16; --risk:#9B2C22; --leaving:#7A7F87;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --display:"Instrument Serif",Georgia,serif;
}

/* strip the framework's own furniture */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
[data-testid="stAppViewContainer"] { background:var(--paper); }
.block-container { padding:22px 30px 60px !important; max-width:1240px; }
html, body, [class*="css"] { font-family:var(--sans); color:var(--ink); }
p, li, label, .stMarkdown { font-size:15px; }

/* masthead */
.pg-mast { display:flex; align-items:center; gap:14px; border-bottom:1px solid var(--rule);
  padding-bottom:12px; margin-bottom:16px; }
.pg-mast .mark { font-family:var(--display); font-size:24px; }
.pg-mast .sub { color:var(--ink-2); font-size:13.5px; }
.pg-mast .right { margin-left:auto; display:flex; gap:10px; align-items:center; }
.pg-local { display:inline-flex; align-items:center; gap:6px; font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--graph); border:1px solid var(--graph); padding:3px 8px; }

/* tabs as a hairline rail */
[data-baseweb="tab-list"] { gap:2px !important; border-bottom:1px solid var(--rule) !important;
  background:transparent !important; }
[data-baseweb="tab"] { background:transparent !important; padding:8px 14px !important;
  border-bottom:3px solid transparent !important; }
[data-baseweb="tab"] p { font-size:14px !important; color:var(--ink-2) !important; }
[data-baseweb="tab"][aria-selected="true"] { border-bottom-color:var(--graph) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color:var(--ink) !important; font-weight:500 !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none !important; }

h1, h2, h3 { font-family:var(--display) !important; font-weight:400 !important;
  letter-spacing:-.01em; }
h3 { font-size:25px !important; margin-bottom:2px !important; }
.pg-note { color:var(--ink-2); font-size:14px; max-width:66ch; margin:2px 0 14px; }
.pg-eyebrow { font-size:11.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); }

/* metrics */
.pg-metrics { display:flex; flex-wrap:wrap; border-top:1px solid var(--rule-2);
  border-bottom:1px solid var(--rule-2); margin:6px 0 18px; }
.pg-metric { flex:1 1 130px; padding:12px 16px 12px 0; }
.pg-metric b { display:block; font-family:var(--display); font-size:29px; line-height:1.05; }
.pg-metric span { font-size:12px; color:var(--ink-2); }
.pg-metric .delta { display:block; font-family:var(--mono); font-size:11.5px; color:var(--risk); }

/* badges and meters */
.pg-badge { display:inline-block; font-size:11px; letter-spacing:.08em; text-transform:uppercase;
  border:1px solid currentColor; padding:2px 7px; margin-right:6px; white-space:nowrap; }
.pg-badge.solid { color:#fff !important; border-color:transparent; }
.b-ready { color:var(--ready); } .b-ready.solid { background:var(--ready); }
.b-caution { color:var(--caution); } .b-caution.solid { background:var(--caution); }
.b-risk { color:var(--risk); } .b-risk.solid { background:var(--risk); }
.b-leaving { color:var(--leaving); } .b-leaving.solid { background:var(--leaving); }
.b-graph { color:var(--graph); } .b-graph.solid { background:var(--graph); }
.pg-meter { display:inline-block; height:4px; background:var(--rule-2); vertical-align:middle; }
.pg-meter i { display:block; height:100%; background:var(--graph); }
.pg-meter.risk i { background:var(--risk); } .pg-meter.ready i { background:var(--ready); }

/* record card */
.pg-record { border:1px solid var(--rule); border-left:3px solid var(--ink-3); background:var(--card);
  padding:14px 16px; display:grid; grid-template-columns:1fr 230px; gap:18px; margin-bottom:2px; }
.pg-record.t-ready { border-left-color:var(--ready); }
.pg-record.t-soon { border-left-color:var(--caution); }
.pg-record.t-leaving { border-left-color:var(--leaving); background:#FBFAF8; }
.pg-record h4 { margin:0 0 4px; font-size:16px; font-weight:500; font-family:var(--sans); }
.pg-record .strike { text-decoration:line-through; color:var(--leaving); }
.pg-record .who { font-size:13px; color:var(--ink-2); }
.pg-record .why { margin-top:8px; font-size:13px; color:var(--ink-2); }
.pg-record .score { text-align:right; font-family:var(--display); font-size:31px; line-height:1; }
.pg-record .score em { font-style:normal; font-family:var(--sans); font-size:12px; color:var(--ink-3); }
.pg-break { margin-top:9px; display:grid; gap:5px; }
.pg-break div { display:grid; grid-template-columns:94px 1fr 28px; gap:8px; align-items:center;
  font-size:11.5px; color:var(--ink-2); }
.pg-break span:last-child { font-family:var(--mono); text-align:right; }

/* tables */
.pg-table { border:1px solid var(--rule); background:var(--card); overflow-x:auto; margin-bottom:8px; }
.pg-table table { border-collapse:collapse; width:100%; min-width:680px; }
.pg-table th, .pg-table td { text-align:left; padding:8px 12px; border-bottom:1px solid var(--rule-2);
  font-size:13.5px; }
.pg-table th { background:#FCFBF9; font-size:11.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--ink-2); font-weight:500; }
.pg-table td.num, .pg-table th.num { text-align:right; font-family:var(--mono);
  font-variant-numeric:tabular-nums; }
.pg-table tr:last-child td { border-bottom:0; }
.pg-caption { font-size:12px; color:var(--ink-3); margin:-2px 0 16px; }

/* nine box */
.pg-grid { display:grid; grid-template-columns:auto repeat(3,1fr); gap:1px; background:var(--rule-2);
  border:1px solid var(--rule); margin-bottom:6px; }
.pg-grid > div { background:var(--card); padding:11px 12px; }
.pg-grid .axis { background:#FCFBF9; font-size:11.5px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--ink-3); display:flex; align-items:center; justify-content:center; text-align:center; }
.pg-grid .cell b { font-family:var(--display); font-size:25px; display:block; line-height:1; }
.pg-grid .cell span { font-size:12px; color:var(--ink-2); }

/* layers */
.pg-layers div { display:grid; grid-template-columns:76px 1fr 44px; gap:10px; align-items:center;
  font-size:13px; color:var(--ink-2); margin-bottom:6px; }
.pg-layers .bar { height:14px; background:var(--graph-soft); }
.pg-layers .bar i { display:block; height:100%; background:var(--graph); }
.pg-layers .n { font-family:var(--mono); text-align:right; }

/* states */
.pg-state { border:1px dashed var(--rule); background:#FCFBF9; padding:18px; margin-bottom:12px; }
.pg-state h4 { margin:0 0 5px; font-size:15px; font-weight:500; font-family:var(--sans); }
.pg-state p { margin:0; font-size:13.5px; color:var(--ink-2); max-width:60ch; }
.pg-answer { border-left:3px solid var(--graph); background:var(--graph-soft); padding:12px 14px;
  font-size:14.5px; margin-bottom:6px; }
.pg-how { font-family:var(--mono); font-size:12px; color:var(--ink-2); margin-bottom:14px; }
.pg-roadmap { opacity:.5; }

/* controls */
.stButton > button, .stDownloadButton > button {
  background:transparent; border:1px solid var(--rule); border-radius:2px; color:var(--ink-2);
  font-size:12.5px; padding:5px 11px; }
.stButton > button:hover { border-color:var(--graph); color:var(--graph); }
.stButton > button[kind="primary"] { background:var(--graph); border-color:var(--graph); color:#fff; }
[data-testid="stWidgetLabel"] p { font-size:11.5px !important; letter-spacing:.07em;
  text-transform:uppercase; color:var(--ink-3) !important; }
[data-baseweb="select"] > div, .stTextInput input, .stMultiSelect > div > div {
  border-radius:2px !important; border-color:var(--rule) !important; font-size:13.5px !important; }
[data-testid="stExpander"] { border:1px solid var(--rule) !important; border-radius:0 !important;
  background:var(--card); }
[data-testid="stExpander"] summary { font-size:14px !important; }
[data-testid="stFileUploaderDropzone"] { background:#FCFBF9; border:1px dashed var(--rule);
  border-radius:0; }
hr { border-color:var(--rule) !important; }
</style>""".replace("__FACES__", _faces())


class Raw(str):
    """A string that is already HTML and must not be escaped again."""


def esc(v) -> str:
    return html.escape(str(v))


def badge(text: str, tone: str, solid: bool = False) -> Raw:
    return Raw('<span class="pg-badge b-%s%s">%s</span>'
               % (tone, " solid" if solid else "", esc(text)))


def metrics(items: list[tuple]) -> str:
    """items: (value, label) or (value, label, delta)."""
    out = []
    for it in items:
        delta = '<span class="delta">%s</span>' % esc(it[2]) if len(it) > 2 and it[2] else ""
        out.append('<div class="pg-metric"><b>%s</b>%s<span>%s</span></div>'
                   % (esc(it[0]), delta, esc(it[1])))
    return '<div class="pg-metrics">%s</div>' % "".join(out)


def meter(pct: float, tone: str = "", width: int = 60) -> Raw:
    return Raw('<span class="pg-meter %s" style="width:%dpx"><i style="width:%d%%"></i></span>'
               % (tone, width, max(0, min(100, int(pct)))))


def table(columns: list[tuple], rows, caption: str = "") -> str:
    """columns: (header, key_or_callable, is_numeric)."""
    head = "".join('<th class="num">%s</th>' % esc(c[0]) if len(c) > 2 and c[2]
                   else "<th>%s</th>" % esc(c[0]) for c in columns)
    body = []
    for r in rows:
        tds = []
        for c in columns:
            v = c[1](r) if callable(c[1]) else r[c[1]]
            cls = ' class="num"' if len(c) > 2 and c[2] else ""
            cell = v if isinstance(v, Raw) else esc("—" if v is None or v == "" else v)
            tds.append("<td%s>%s</td>" % (cls, cell))
        body.append("<tr>%s</tr>" % "".join(tds))
    cap = '<div class="pg-caption">%s</div>' % esc(caption) if caption else ""
    return ('<div class="pg-table"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s'
            % (head, "".join(body), cap))


def state(title: str, body: str) -> str:
    return '<div class="pg-state"><h4>%s</h4><p>%s</p></div>' % (esc(title), esc(body))
