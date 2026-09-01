"""Premium dark theme + reusable HTML components for the Safar UI.

Design language: deep space-dark canvas, gradient accents (indigo → cyan →
emerald), glassmorphism cards, soft glow, and restrained motion (fade-in,
gradient drift, hover lift). All colours live in CSS variables so the whole
palette can be retuned in one place.

Nothing here calls the agent pipeline — these are pure `st.markdown` helpers.
"""
from __future__ import annotations

import math

import streamlit as st

# ---- palette (kept in sync with the Altair charts in charts.py) -------------
ACCENT = "#7c5cff"     # indigo-violet
ACCENT2 = "#22d3ee"    # cyan
ACCENT3 = "#34d399"    # emerald
AMBER = "#f59e0b"
ROSE = "#f43f5e"

ARCH_COLOR = {"saver": "#38bdf8", "comfort": "#c084fc", "balanced": "#f59e0b"}

_gauge_seq = 0  # unique gradient ids per rendered gauge


# ============================================================== global CSS ===
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#0a0e1a; --bg2:#0e1426;
  --surface:rgba(255,255,255,.04); --surface2:rgba(255,255,255,.07);
  --border:rgba(255,255,255,.09); --border-strong:rgba(255,255,255,.16);
  --text:#e6e9f2; --muted:#94a0bd;
  --accent:#7c5cff; --accent2:#22d3ee; --accent3:#34d399; --amber:#f59e0b; --rose:#f43f5e;
  --grad:linear-gradient(135deg,#7c5cff 0%,#22d3ee 100%);
  --grad-soft:linear-gradient(135deg,rgba(124,92,255,.18),rgba(34,211,238,.12));
}

/* ---- base canvas ---- */
.stApp{
  background:
    radial-gradient(1200px 620px at 8% -12%, rgba(124,92,255,.16), transparent 60%),
    radial-gradient(1000px 520px at 102% -4%, rgba(34,211,238,.12), transparent 55%),
    radial-gradient(900px 520px at 50% 118%, rgba(52,211,153,.08), transparent 60%),
    var(--bg);
  color:var(--text);
  font-family:'Inter',system-ui,sans-serif;
}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"]{right:1rem;}
.block-container{padding-top:2.2rem; max-width:1280px; animation:fadeInUp .5s ease both;}
@keyframes fadeInUp{from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:none}}

/* ---- typography ---- */
h1,h2,h3,h4{font-family:'Sora','Inter',sans-serif; letter-spacing:-.01em; color:var(--text);}
h2{font-weight:700;} h3{font-weight:600;}
p,label,span,div{font-family:'Inter',sans-serif;}
a{color:var(--accent2);}

/* ---- sidebar ---- */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0c1224 0%,#090d18 100%);
  border-right:1px solid var(--border);
}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem;}
[data-testid="stSidebar"] h1{
  font-size:1.7rem; font-weight:800; margin-bottom:.1rem;
  background:linear-gradient(120deg,#c4b5fd,#22d3ee); -webkit-background-clip:text;
  background-clip:text; -webkit-text-fill-color:transparent;
}

/* ---- metric cards (glass) ---- */
[data-testid="stMetric"]{
  background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:14px 16px 12px; backdrop-filter:blur(10px);
  transition:transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
[data-testid="stMetric"]:hover{
  transform:translateY(-3px); border-color:rgba(124,92,255,.5);
  box-shadow:0 14px 34px -14px rgba(124,92,255,.55);
}
[data-testid="stMetricLabel"] p{color:var(--muted); font-weight:500; font-size:.8rem;
  text-transform:uppercase; letter-spacing:.04em;}
[data-testid="stMetricValue"]{font-family:'Sora',sans-serif; font-weight:700;}

/* ---- buttons ---- */
.stButton>button, .stFormSubmitButton>button, .stDownloadButton>button{
  border-radius:12px; border:1px solid var(--border); background:var(--surface2);
  color:var(--text); font-family:'Sora',sans-serif; font-weight:600; letter-spacing:.01em;
  transition:transform .18s ease, box-shadow .2s ease, border-color .2s ease, background .2s;
}
.stButton>button:hover, .stFormSubmitButton>button:hover, .stDownloadButton>button:hover{
  transform:translateY(-2px); border-color:rgba(124,92,255,.6);
  box-shadow:0 10px 26px -12px rgba(124,92,255,.6);
}
.stButton>button[kind="primary"], .stButton>button[data-testid="baseButton-primary"],
.stFormSubmitButton>button[kind="primary"], button[kind="primaryFormSubmit"]{
  background:var(--grad); border:none; color:#0a0e1a; font-weight:700;
  box-shadow:0 10px 30px -12px rgba(34,211,238,.6);
}
.stButton>button[kind="primary"]:hover{filter:brightness(1.06); transform:translateY(-2px);}

/* ---- tabs ---- */
.stTabs [data-baseweb="tab-list"]{gap:8px; background:transparent; border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{
  background:var(--surface); border:1px solid var(--border); border-bottom:none;
  border-radius:12px 12px 0 0; padding:9px 20px; color:var(--muted);
  font-family:'Sora',sans-serif; font-weight:600; transition:all .2s ease;
}
.stTabs [data-baseweb="tab"]:hover{color:var(--text); background:var(--surface2);}
.stTabs [aria-selected="true"]{
  background:var(--grad-soft); color:var(--text);
  box-shadow:inset 0 -2px 0 0 var(--accent);
}

/* ---- expanders ---- */
[data-testid="stExpander"]{
  border:1px solid var(--border); border-radius:14px; background:var(--surface);
  overflow:hidden; transition:border-color .2s ease, box-shadow .2s ease;
}
[data-testid="stExpander"]:hover{border-color:var(--border-strong);}
[data-testid="stExpander"] summary{font-family:'Sora',sans-serif; font-weight:600;}
[data-testid="stExpander"] summary:hover{color:var(--accent2);}

/* ---- inputs ---- */
[data-baseweb="input"], [data-baseweb="select"]>div, .stTextInput input, .stNumberInput input{
  border-radius:10px !important;
}
.stTextInput input:focus, .stNumberInput input:focus{border-color:var(--accent)!important;}

/* ---- progress ---- */
[data-testid="stProgress"] > div > div > div > div{
  background:var(--grad)!important;
}

/* ---- alerts: soften into glass ---- */
[data-testid="stAlert"], .stAlert{border-radius:12px; backdrop-filter:blur(6px);}

/* ---- dataframe ---- */
[data-testid="stDataFrame"]{border:1px solid var(--border); border-radius:12px; overflow:hidden;}

/* ---- dividers ---- */
hr{border-color:var(--border);}

/* ---- scrollbar ---- */
::-webkit-scrollbar{width:10px; height:10px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:rgba(124,92,255,.35); border-radius:10px;}
::-webkit-scrollbar-thumb:hover{background:rgba(124,92,255,.6);}

/* ======================= custom components ======================= */
.safar-hero{
  position:relative; border-radius:22px; padding:30px 34px; margin-bottom:14px;
  background:linear-gradient(135deg,rgba(124,92,255,.16),rgba(34,211,238,.08) 55%,rgba(52,211,153,.08));
  border:1px solid var(--border); overflow:hidden; backdrop-filter:blur(10px);
}
.safar-hero::after{
  content:""; position:absolute; inset:-40% -10% auto auto; width:420px; height:420px;
  background:radial-gradient(circle,rgba(124,92,255,.35),transparent 62%); filter:blur(20px);
  animation:floaty 9s ease-in-out infinite;
}
@keyframes floaty{0%,100%{transform:translate(0,0)} 50%{transform:translate(-24px,20px)}}
.safar-hero .eyebrow{
  font-family:'Sora',sans-serif; font-weight:600; font-size:.72rem; letter-spacing:.22em;
  text-transform:uppercase; color:var(--accent2); margin:0 0 6px;
}
.safar-hero h1{
  font-family:'Sora',sans-serif; font-weight:800; font-size:clamp(2rem,4.4vw,3.1rem);
  line-height:1.04; margin:0; letter-spacing:-.02em;
  background:linear-gradient(120deg,#c4b5fd 0%,#22d3ee 42%,#34d399 72%,#c4b5fd 100%);
  background-size:280% 280%; -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; animation:grad 9s ease infinite;
}
@keyframes grad{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
.safar-hero .sub{color:var(--muted); font-size:1rem; margin:10px 0 0; max-width:640px;}
.safar-pills{display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; position:relative; z-index:1;}
.safar-pill{
  font-family:'Sora',sans-serif; font-size:.76rem; font-weight:600; color:var(--text);
  padding:6px 13px; border-radius:999px; border:1px solid var(--border-strong);
  background:var(--surface2); backdrop-filter:blur(6px); display:inline-flex; gap:6px; align-items:center;
}
.safar-pill .dot{width:7px; height:7px; border-radius:50%; box-shadow:0 0 10px currentColor;}

.safar-section{display:flex; align-items:center; gap:12px; margin:26px 0 12px;}
.safar-section .bar{width:4px; height:26px; border-radius:4px; background:var(--grad);
  box-shadow:0 0 16px rgba(124,92,255,.6);}
.safar-section .t{font-family:'Sora',sans-serif; font-weight:700; font-size:1.28rem; color:var(--text);}
.safar-section .s{color:var(--muted); font-size:.85rem; margin-left:2px;}

.safar-card{
  background:var(--surface); border:1px solid var(--border); border-radius:18px;
  padding:18px 18px 14px; backdrop-filter:blur(10px); height:100%;
  transition:transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.safar-card:hover{transform:translateY(-4px); box-shadow:0 20px 44px -20px rgba(124,92,255,.5);}
.safar-card .cap{font-family:'Sora',sans-serif; font-size:.72rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted);}

/* radial gauge */
.safar-gauge{display:flex; flex-direction:column; align-items:center; gap:2px;}
.safar-gauge svg{filter:drop-shadow(0 6px 16px rgba(124,92,255,.35)); animation:fadeInUp .6s ease both;}
.safar-gauge .val{font-family:'Sora',sans-serif; font-weight:700; font-size:1.5rem; fill:var(--text);}
.safar-gauge .lbl{font-family:'Sora',sans-serif; font-size:.74rem; letter-spacing:.06em;
  text-transform:uppercase; color:var(--muted); margin-top:-2px;}
.safar-gauge .sub{color:var(--muted); font-size:.72rem;}

/* small stat chips */
.safar-chips{display:flex; flex-wrap:wrap; gap:8px;}
.safar-chip{border:1px solid var(--border); border-radius:12px; padding:8px 12px; background:var(--surface);
  min-width:96px;}
.safar-chip .k{font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);}
.safar-chip .v{font-family:'Sora',sans-serif; font-weight:700; font-size:1.05rem; color:var(--text);}
</style>
"""


def inject_theme() -> None:
    """Inject the global stylesheet + fonts. Call once, right after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ hero -----
def hero(pills: list[tuple[str, str]] | None = None) -> None:
    """Animated gradient hero banner. `pills` = list of (label, color)."""
    pills = pills or [
        ("Multi-agent", ACCENT), ("Negotiation engine", ACCENT2),
        ("Human-in-the-loop", ACCENT3), ("Live replanning", AMBER),
    ]
    chips = "".join(
        f'<span class="safar-pill"><span class="dot" style="background:{c};color:{c}"></span>{lbl}</span>'
        for lbl, c in pills)
    st.markdown(
        f'''<div class="safar-hero">
              <p class="eyebrow">Travel Operating System</p>
              <h1>Safar&nbsp;·&nbsp;your trip, run by a team of agents</h1>
              <p class="sub">Specialised agents divide the work, negotiate competing
                 priorities into three Pareto plans, and hand every irreversible call to you.</p>
              <div class="safar-pills">{chips}</div>
            </div>''',
        unsafe_allow_html=True)


def section(title: str, sub: str = "") -> None:
    """A gradient-accented section header."""
    sub_html = f'<span class="s">— {sub}</span>' if sub else ""
    st.markdown(
        f'<div class="safar-section"><div class="bar"></div>'
        f'<span class="t">{title}</span>{sub_html}</div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------- gauge ------
def radial_gauge(pct: float, label: str = "", sub: str = "",
                 color: str = ACCENT, size: int = 132) -> str:
    """Return HTML for an animated radial gauge. `pct` in 0..1."""
    global _gauge_seq
    _gauge_seq += 1
    gid = f"g{_gauge_seq}"
    pct = max(0.0, min(1.0, float(pct)))
    r = size / 2 - 12
    cx = cy = size / 2
    circ = 2 * math.pi * r
    dash = circ * pct
    gap = circ - dash
    return f'''
<div class="safar-gauge">
  <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <defs>
      <linearGradient id="{gid}" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="{color}"/>
        <stop offset="100%" stop-color="{ACCENT2}"/>
      </linearGradient>
    </defs>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="10"/>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#{gid})" stroke-width="10"
            stroke-linecap="round" stroke-dasharray="{dash:.1f} {gap:.1f}"
            transform="rotate(-90 {cx} {cy})"/>
    <text x="50%" y="49%" text-anchor="middle" dominant-baseline="middle" class="val">{int(round(pct*100))}%</text>
  </svg>
  <div class="lbl">{label}</div>
  {f'<div class="sub">{sub}</div>' if sub else ''}
</div>'''


def gauge(pct: float, label: str = "", sub: str = "", color: str = ACCENT,
          size: int = 132) -> None:
    """Render a radial gauge directly."""
    st.markdown(radial_gauge(pct, label, sub, color, size), unsafe_allow_html=True)


def chips(items: list[tuple[str, str]]) -> None:
    """Render a row of small key/value stat chips. `items` = [(key, value)]."""
    html = "".join(f'<div class="safar-chip"><div class="k">{k}</div>'
                   f'<div class="v">{v}</div></div>' for k, v in items)
    st.markdown(f'<div class="safar-chips">{html}</div>', unsafe_allow_html=True)
