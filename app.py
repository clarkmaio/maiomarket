"""MaioMarket - prediction market goliardico in stile Polymarket.

Esegui con:    python app.py
Poi apri:      http://localhost:5001
"""

from __future__ import annotations

import os
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path

from fasthtml.common import *
from starlette.responses import RedirectResponse

import market as mkt
import db


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(os.environ.get("MAIOMARKET_CONFIG", "config.yaml"))
CFG = yaml.safe_load(CONFIG_PATH.read_text())

SETTINGS = CFG.get("settings", {})
INITIAL_BALANCE = float(SETTINGS.get("initial_balance", 1000.0))
SESSION_SECRET = os.environ.get("SESSION_SECRET") or SETTINGS.get("session_secret", "dev-secret-change-me")

USERS = {u["username"]: u for u in CFG.get("users", [])}
MARKETS_CFG = CFG.get("markets", [])

db.init_db(CFG.get("users", []), MARKETS_CFG, INITIAL_BALANCE)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def current_user(sess) -> str | None:
    return sess.get("user")


def is_admin(username: str | None) -> bool:
    return bool(username and USERS.get(username, {}).get("admin"))


def auth_before(req, sess):
    if req.url.path.startswith("/login") or req.url.path.startswith("/static"):
        return
    if not current_user(sess):
        return RedirectResponse("/login", status_code=303)


bware = Beforeware(auth_before, skip=[r"/login", r"/static/.*"])

app, rt = fast_app(
    secret_key=SESSION_SECRET,
    before=bware,
    pico=True,
    htmlkw=dict(data_theme="dark"),
    hdrs=(
        Style("""
            /* ---- Tema scuro: palette stile Polymarket ---- */
            :root {
                --pico-background-color: #0d1424;
                --pico-color: #e6e9ef;
                --pico-h1-color:#f4f6f9; --pico-h2-color:#f4f6f9; --pico-h3-color:#f4f6f9;
                --pico-h4-color:#f4f6f9; --pico-h5-color:#f4f6f9; --pico-h6-color:#f4f6f9;
                --pico-muted-color:#8b97a4;
                --pico-primary:#2f9fe0;
                --pico-primary-background:#2f9fe0;
                --pico-primary-hover-background:#2588c4;
                --pico-primary-inverse:#ffffff;
                --pico-primary-focus:rgba(47,159,224,.35);
                --pico-card-background-color:#1a2433;
                --pico-card-border-color:#2a3441;
                --pico-card-sectioning-background-color:#1a2433;
                --pico-form-element-background-color:#121b29;
                --pico-form-element-border-color:#2a3441;
                --pico-form-element-color:#e6e9ef;
                --pico-form-element-placeholder-color:#6b7785;
                --pico-form-element-active-background-color:#121b29;
                --pico-table-border-color:#2a3441;
                --pico-table-row-stripped-background-color:#16202d;
                --pico-secondary:#8b97a4;
                --pico-secondary-background:#2a3441;
                --pico-secondary-hover-background:#36414f;
                --pico-secondary-inverse:#e6e9ef;
                --pico-contrast:#e6e9ef;
                --pico-contrast-background:#c4313a;
                --pico-contrast-hover-background:#a3262e;
                --pico-contrast-inverse:#ffffff;
                --pico-border-color:#2a3441;
                --pico-muted-border-color:#2a3441;
                --pico-text-selection-color:rgba(47,159,224,.3);
                --card-border-color:#2a3441;
                color-scheme: dark;
            }

            body { max-width: 1120px; margin: 1rem auto; padding: 0 1rem;
                   background: #0d1424; color: #e6e9ef; }
            a { color: #2f9fe0; }
            .markets { display: grid; gap: 1rem;
                       grid-template-columns: repeat(3, 1fr); }
            @media (max-width: 760px) { .markets { grid-template-columns: 1fr; } }
            .market-card { border: 1px solid #2a3441; border-radius: 8px; padding: 1rem;
                           background: #1a2433; }
            .market-card h3 { margin: 0 0 .25rem 0; }
            .prices { display: flex; gap: 1rem; font-weight: bold; }

            /* tile compatte stile prediction market */
            .tile { border: 1px solid #2a3441; border-radius: 12px; padding: 1.1rem;
                    display: flex; flex-direction: column; gap: .9rem; min-height: 150px;
                    transition: box-shadow .15s, border-color .15s; background: #1a2433; }
            .tile:hover { border-color: #3a4757; box-shadow: 0 2px 12px rgba(0,0,0,.45); }
            .tile-title { font-weight: 600; font-size: 1.05rem; line-height: 1.3;
                          color: #e6e9ef; text-decoration: none;
                          display: -webkit-box; -webkit-line-clamp: 2;
                          -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em; }
            .tile-actions { display: flex; gap: .5rem; margin-top: auto; }
            .tile-actions a { flex: 1; text-align: center; padding: .55rem .25rem;
                              border-radius: 8px; font-weight: 600; font-size: .92rem;
                              text-decoration: none; }
            .tile-yes { background: rgba(39,174,96,.16); color: #3fb950; }
            .tile-no  { background: rgba(225,91,100,.16); color: #f0676f; }
            .tile-yes:hover { background: #238636; color: #fff; }
            .tile-no:hover  { background: #c4313a; color: #fff; }
            .tile-foot { display: flex; justify-content: space-between; align-items: center;
                         font-size: .72rem; color: #8b97a4; }
            .price-yes { color: #3fb950; }
            .price-no  { color: #f0676f; }
            .pill { display:inline-block; padding: .1rem .5rem; border-radius: 999px;
                    background: #243042; color: #aab4c0; font-size: .8em; }
            .pill.resolved-yes { background: rgba(39,174,96,.18); color: #3fb950; }
            .pill.resolved-no  { background: rgba(225,91,100,.18); color: #f0676f; }
            .pill.expired { background: rgba(210,170,40,.18); color: #d8b341; }
            table { width: 100%; }
            .site-title { text-align: center; font-size: 2.5rem; font-weight: 800;
                          letter-spacing: .05em; margin: 1rem 0 .5rem 0;
                          color: #f4f6f9; }
            .navbar { display:flex; justify-content: space-between; align-items: center;
                      border-bottom: 1px solid #2a3441; padding-bottom: .5rem; margin-bottom: 1rem;
                      gap: 1rem; flex-wrap: wrap; }
            .nav-right { display:flex; align-items:center; gap:.4rem; }
            .tabs { display:flex; gap:.35rem; padding:.2rem; background:#121b29;
                    border:1px solid #2a3441; border-radius:10px; }
            .tab { padding:.4rem .9rem; border-radius:7px; text-decoration:none;
                   font-weight:600; font-size:.9rem; color:#8b97a4;
                   transition:background .15s, color .15s; }
            .tab:hover { color:#e6e9ef; background:#1a2433; }
            .tab.active { color:#fff; background:#2f9fe0; }
            .err { background: rgba(225,91,100,.12); border: 1px solid rgba(225,91,100,.4);
                   color: #f0676f; padding: .5rem 1rem; border-radius: 6px; }
            .ok  { background: rgba(39,174,96,.12); border: 1px solid rgba(39,174,96,.4);
                   color: #3fb950; padding: .5rem 1rem; border-radius: 6px; }
            svg.chart { width: 100%; height: 260px; background:#0d1424; border:none; border-radius:6px; }

            /* ---- pagina mercato: layout a due colonne ---- */
            .market-layout { display:flex; gap:1.5rem; align-items:flex-start; }
            .market-main { flex:1 1 auto; min-width:0; }
            .market-side { flex:0 0 330px; position:sticky; top:1rem; }
            @media (max-width:820px) {
                .market-layout { flex-direction:column; }
                .market-side { position:static; flex-basis:auto; width:100%; }
            }
            .mkt-title { margin:0 0 .4rem 0; }
            .market-meta { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap;
                           color:#8b97a4; font-size:.85rem; margin-bottom:.4rem; }
            .chance { font-size:2rem; font-weight:800; color:#2f9fe0; margin:.2rem 0 .4rem; }
            .position-box { background:#121b29; border:1px solid #2a3441; border-radius:10px;
                            padding:.6rem 1rem; margin:1rem 0; }
            .position-box p { margin:.2rem 0; }

            /* ---- pannello trading (sidebar) ---- */
            .trade-panel { background:#121b29; border:1px solid #2a3441; border-radius:12px;
                           padding:1rem; }
            .seg { display:flex; gap:1.4rem; border-bottom:1px solid #2a3441; margin-bottom:1rem; }
            .seg-opt { cursor:pointer; padding:.4rem .1rem; font-weight:700; color:#8b97a4;
                       border-bottom:2px solid transparent; margin-bottom:-1px; }
            .seg-opt input { display:none; }
            .seg-opt:has(input:checked) { color:#e6e9ef; border-bottom-color:#2f9fe0; }
            .outcomes { display:flex; gap:.6rem; margin-bottom:1rem; }
            .outcome { flex:1; display:flex; flex-direction:column; align-items:center; gap:.1rem;
                       padding:.65rem; border-radius:8px; cursor:pointer; font-weight:700; }
            .outcome input { display:none; }
            .outcome .oc-price { font-size:.82rem; font-weight:600; opacity:.9; }
            .outcome.yes { background:rgba(39,174,96,.14); color:#3fb950; }
            .outcome.no  { background:rgba(225,91,100,.14); color:#f0676f; }
            .outcome.yes:has(input:checked) { background:#238636; color:#fff; }
            .outcome.no:has(input:checked)  { background:#c4313a; color:#fff; }
            .amount-row { margin-bottom:1rem; }
            .amount-row label { font-weight:700; color:#e6e9ef; display:block; margin-bottom:.3rem; }
            .amount-row input { margin:0; }
            .trade-btn { width:100%; margin:0; }
        """),
    ),
)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def site_header():
    return Div("maiomarket", cls="site-title")


def navbar(user: str):
    bal = db.get_balance(user)
    tabs = [
        A("Mercati", href="/", cls="tab", data_match="/"),
        A("Portfolio", href="/portfolio", cls="tab", data_match="/portfolio"),
    ]
    if is_admin(user):
        tabs.append(A("Admin", href="/admin", cls="tab", data_match="/admin"))
    return Div(
        Nav(*tabs, cls="tabs"),
        Div(
            Span(f"{user}", cls="pill"),
            " ",
            Span(f"{bal:.2f} cr", cls="pill"),
            " ",
            Form(Button("logout", type="submit"), action="/logout", method="post",
                 style="display:inline"),
            cls="nav-right",
        ),
        Script("""
            (function () {
                var p = location.pathname;
                document.querySelectorAll('.tab').forEach(function (t) {
                    var m = t.getAttribute('data-match');
                    var on = m === '/' ? (p === '/' || p.indexOf('/market') === 0)
                                       : p.indexOf(m) === 0;
                    if (on) t.classList.add('active');
                });
            })();
        """),
        cls="navbar",
    )


def page(user: str, title: str, *content, msg: tuple[str, str] | None = None):
    banner = ()
    if msg:
        kind, text = msg
        banner = (Div(text, cls=kind),)
    return (
        Title(title),
        Main(
            site_header(),
            navbar(user),
            *banner,
            *content,
        ),
    )


def market_status_pill(m) -> str:
    if m["status"] == "resolved_yes":
        return Span("RISOLTO: YES", cls="pill resolved-yes")
    if m["status"] == "resolved_no":
        return Span("RISOLTO: NO", cls="pill resolved-no")
    today = date.today().isoformat()
    if m["expires"] < today:
        return Span(f"SCADUTO {m['expires']}", cls="pill expired")
    return Span(f"scade {m['expires']}", cls="pill")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@rt("/login")
def get(sess, err: str = ""):
    if current_user(sess):
        return RedirectResponse("/", status_code=303)
    return (
        Title("MaioMarket - login"),
        Main(
            site_header(),
            Div(err, cls="err") if err else "",
            Form(
                Label("Username", Input(name="username", required=True, autofocus=True)),
                Label("Password", Input(name="password", type="password", required=True)),
                Button("entra", type="submit"),
                method="post",
                action="/login",
            ),
            P(Small("Le credenziali sono definite in config.yaml")),
        ),
    )


@rt("/login")
def post(sess, username: str, password: str):
    u = USERS.get(username)
    if not u or u.get("password") != password:
        return RedirectResponse("/login?err=Credenziali+errate", status_code=303)
    sess["user"] = username
    return RedirectResponse("/", status_code=303)


@rt("/logout")
def post(sess):
    sess.clear()
    return RedirectResponse("/login", status_code=303)


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

@rt("/")
def get(sess):
    user = current_user(sess)
    cards = []
    for m in db.list_markets():
        p_yes = mkt.price_yes(m["q_yes"], m["q_no"], m["liquidity"])
        n_trades = db.market_stats(m["id"])["n_trades"]
        href = f"/market/{m['id']}"
        cards.append(
            Div(
                A(m["question"], href=href, cls="tile-title"),
                Div(
                    A(f"Yes {p_yes*100:.0f}%", href=f"{href}?side=YES", cls="tile-yes"),
                    A(f"No {(1-p_yes)*100:.0f}%", href=f"{href}?side=NO", cls="tile-no"),
                    cls="tile-actions",
                ),
                Div(
                    market_status_pill(m),
                    Span(f"{n_trades} trade"),
                    cls="tile-foot",
                ),
                cls="tile",
            )
        )
    return page(user, "Mercati", Div(*cards, cls="markets"))


# ---------------------------------------------------------------------------
# Market detail
# ---------------------------------------------------------------------------

def _price_chart(history) -> str:
    """SVG line chart della chance YES (probabilita' di mercato) nel tempo.

    Una sola linea blu, stile Polymarket. L'asse x rappresenta il timestamp del
    bid (punti spaziati in base a quando e' avvenuto il trade); le etichette di
    percentuale sono sull'asse destro.
    """
    if not history:
        return Div(P("Nessun trade ancora. La chance parte da 50%."), cls="market-card")

    accent = "#2f9fe0"
    times = [datetime.strptime(h["ts"], "%Y-%m-%dT%H:%M:%SZ") for h in history]
    t0 = times[0]
    secs = [(t - t0).total_seconds() for t in times]
    span = max(1e-9, secs[-1])

    pts = [(s, float(h["price_yes_after"])) for s, h in zip(secs, history)]
    w, h = 900, 260
    pad_l, pad_r, pad_t, pad_b = 12, 46, 16, 28

    def x(s): return pad_l + (w - pad_l - pad_r) * (s / span)
    def y(p): return pad_t + (h - pad_t - pad_b) * (1 - p)

    line = " ".join(f"{x(s):.1f},{y(p):.1f}" for s, p in pts)
    area = (f"{x(pts[0][0]):.1f},{y(0):.1f} " + line +
            f" {x(pts[-1][0]):.1f},{y(0):.1f}")

    grid = []
    for frac in (0, .25, .5, .75, 1):
        yy = y(frac)
        grid.append(f'<line x1="{pad_l}" y1="{yy}" x2="{w-pad_r}" y2="{yy}" stroke="#1c2735"/>')
        grid.append(f'<text x="{w-pad_r+6}" y="{yy+4}" font-size="11" fill="#8b97a4" '
                    f'text-anchor="start">{int(frac*100)}%</text>')

    # Etichette temporali sull'asse x (inizio, meta', fine)
    for frac in (0, .5, 1):
        s = span * frac
        xx = x(s)
        label = (t0 + timedelta(seconds=s)).strftime("%d/%m %H:%M")
        anchor = "start" if frac == 0 else ("end" if frac == 1 else "middle")
        grid.append(
            f'<text x="{xx:.1f}" y="{h-10}" font-size="11" fill="#8b97a4" '
            f'text-anchor="{anchor}">{label}</text>')

    dots = "".join(
        f'<circle cx="{x(s):.1f}" cy="{y(p):.1f}" r="2" fill="{accent}"/>'
        for s, p in pts
    )
    # punto corrente evidenziato (come nella reference)
    lx, lp = x(pts[-1][0]), y(pts[-1][1])
    end_dot = (f'<circle cx="{lx:.1f}" cy="{lp:.1f}" r="8" fill="{accent}" opacity="0.25"/>'
               f'<circle cx="{lx:.1f}" cy="{lp:.1f}" r="4" fill="{accent}"/>')

    svg = (
        f'<svg class="chart" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        + "".join(grid)
        + f'<polygon points="{area}" fill="{accent}" fill-opacity="0.10" stroke="none"/>'
        + f'<polyline fill="none" stroke="{accent}" stroke-width="2.5" '
        + f'stroke-linejoin="round" points="{line}"/>'
        + dots
        + end_dot
        + "</svg>"
    )
    return NotStr(svg)


@rt("/market/{mid}")
def get(sess, mid: str, err: str = "", ok: str = "", side: str = ""):
    user = current_user(sess)
    m = db.get_market(mid)
    if not m:
        return page(user, "404", P("Mercato non trovato."))

    sel_side = side.upper() if side.upper() in ("YES", "NO") else "YES"

    b = m["liquidity"]
    p_yes = mkt.price_yes(m["q_yes"], m["q_no"], b)
    p_no = 1 - p_yes
    yes_sh, no_sh = db.get_position(user, mid)
    bal = db.get_balance(user)
    history = db.trade_history(mid)

    is_resolved = m["status"] != "open"
    can_resolve = is_admin(user) and not is_resolved and m["expires"] <= date.today().isoformat()

    if is_resolved:
        trade_block = Div(
            B("Mercato risolto."), P("Niente piu' trading.", style="color:#8b97a4"),
            cls="trade-panel",
        )
    else:
        trade_block = Form(
            # tab Buy / Sell
            Div(
                Label(Input(type="radio", name="action", value="BUY", checked=True),
                      Span("Buy"), cls="seg-opt"),
                Label(Input(type="radio", name="action", value="SELL"),
                      Span("Sell"), cls="seg-opt"),
                cls="seg",
            ),
            # esito Yes / No con prezzo in centesimi (1 share paga 1 cr = 100¢)
            Div(
                Label(Input(type="radio", name="side", value="YES", checked=(sel_side == "YES")),
                      Span("Yes"), Span(f"{p_yes*100:.1f}¢", cls="oc-price"),
                      cls="outcome yes"),
                Label(Input(type="radio", name="side", value="NO", checked=(sel_side == "NO")),
                      Span("No"), Span(f"{p_no*100:.1f}¢", cls="oc-price"),
                      cls="outcome no"),
                cls="outcomes",
            ),
            Div(
                Label("Quantita' (token)", fr="shares"),
                Input(name="shares", id="shares", type="number", min="1", step="1",
                      value="10", required=True),
                cls="amount-row",
            ),
            Button("Trade", type="submit", cls="trade-btn"),
            method="post",
            action=f"/market/{mid}/trade",
            cls="trade-panel",
        )

    resolve_block = ()
    if can_resolve:
        resolve_block = (
            Div(
                H5("Risoluzione (admin)", style="margin-top:0"),
                Div(
                    Form(Input(name="outcome", type="hidden", value="YES"),
                         Button("Risolvi YES", type="submit"),
                         action=f"/market/{mid}/resolve", method="post",
                         style="display:inline; margin-right:.5rem"),
                    Form(Input(name="outcome", type="hidden", value="NO"),
                         Button("Risolvi NO", type="submit", cls="contrast"),
                         action=f"/market/{mid}/resolve", method="post",
                         style="display:inline"),
                ),
                cls="trade-panel", style="margin-top:1rem",
            ),
        )

    history_rows = [
        Tr(
            Td(h["ts"].replace("T", " ").rstrip("Z")),
            Td(h["username"]),
            Td(f"{'BUY' if h['shares']>0 else 'SELL'} {h['side']}"),
            Td(f"{abs(h['shares']):.2f}"),
            Td(f"{h['cost']:+.2f}"),
            Td(f"{h['price_yes_after']*100:.1f}%"),
        )
        for h in reversed(history)
    ]

    msg = None
    if err: msg = ("err", err)
    elif ok: msg = ("ok", ok)

    n_trades = db.market_stats(mid)["n_trades"]
    main_col = Div(
        H2(m["question"], cls="mkt-title"),
        Div(
            market_status_pill(m),
            Span(f"Scade: {m['expires']}"),
            Span("·"),
            Span(f"{n_trades} trade"),
            cls="market-meta",
        ),
        Div(f"{p_yes*100:.0f}% chance", cls="chance"),
        _price_chart(history),
        Div(
            P(f"Saldo: ", B(f"{bal:.2f} cr")),
            P(f"Posseduti — YES: ", B(f"{yes_sh:.2f}"), "  |  NO: ", B(f"{no_sh:.2f}")),
            cls="position-box",
        ),
        H4("Storico trade"),
        Table(
            Thead(Tr(Th("Quando"), Th("Utente"), Th("Op"), Th("Shares"),
                     Th("Costo"), Th("Chance YES"))),
            Tbody(*history_rows) if history_rows else Tbody(Tr(Td("(nessuno)", colspan="6"))),
        ),
        cls="market-main",
    )
    side_col = Div(trade_block, *resolve_block, cls="market-side")

    return page(
        user,
        m["question"],
        Div(main_col, side_col, cls="market-layout"),
        msg=msg,
    )


# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------

@rt("/market/{mid}/trade")
def post(sess, mid: str, side: str, shares: int, action: str = "BUY"):
    user = current_user(sess)
    m = db.get_market(mid)
    if not m:
        return RedirectResponse("/", status_code=303)

    if m["status"] != "open":
        return RedirectResponse(f"/market/{mid}?err=Mercato+chiuso", status_code=303)
    if m["expires"] < date.today().isoformat():
        return RedirectResponse(f"/market/{mid}?err=Mercato+scaduto", status_code=303)

    side = side.upper()
    action = action.upper()
    if side not in ("YES", "NO") or action not in ("BUY", "SELL"):
        return RedirectResponse(f"/market/{mid}?err=Input+invalido", status_code=303)
    if shares <= 0:
        return RedirectResponse(f"/market/{mid}?err=Shares+deve+essere+positivo", status_code=303)

    signed = float(shares) if action == "BUY" else -float(shares)

    # Pre-check: per SELL, l'utente deve possedere abbastanza share
    if action == "SELL":
        yes_sh, no_sh = db.get_position(user, mid)
        owned = yes_sh if side == "YES" else no_sh
        if owned < shares - 1e-9:
            return RedirectResponse(
                f"/market/{mid}?err=Non+possiedi+abbastanza+{side}", status_code=303)

    b = m["liquidity"]
    cost = mkt.trade_cost(m["q_yes"], m["q_no"], b, side, signed)

    bal = db.get_balance(user)
    if cost > bal + 1e-9:
        return RedirectResponse(
            f"/market/{mid}?err=Saldo+insufficiente+(serve+{cost:.2f})", status_code=303)

    new_y, new_n = mkt.apply_trade(m["q_yes"], m["q_no"], side, signed)
    new_price = mkt.price_yes(new_y, new_n, b)

    db.record_trade(user, mid, side, signed, cost, new_y, new_n, new_price)

    label = "comprato" if action == "BUY" else "venduto"
    return RedirectResponse(
        f"/market/{mid}?ok={label}+{shares}+{side}+per+{cost:+.2f}+cr",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Risoluzione (admin)
# ---------------------------------------------------------------------------

@rt("/market/{mid}/resolve")
def post(sess, mid: str, outcome: str):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse(f"/market/{mid}?err=Non+sei+admin", status_code=303)
    m = db.get_market(mid)
    if not m:
        return RedirectResponse("/", status_code=303)
    if m["expires"] > date.today().isoformat():
        return RedirectResponse(f"/market/{mid}?err=Mercato+non+ancora+scaduto", status_code=303)
    try:
        db.resolve_market(mid, outcome)
    except ValueError as e:
        return RedirectResponse(f"/market/{mid}?err={e}", status_code=303)
    return RedirectResponse(f"/market/{mid}?ok=Risolto+{outcome}", status_code=303)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@rt("/portfolio")
def get(sess):
    user = current_user(sess)
    bal = db.get_balance(user)
    positions = db.user_positions(user)
    trades = db.user_trades(user)

    pos_rows = []
    total_value = bal
    for p in positions:
        py = mkt.price_yes(p["q_yes"], p["q_no"], p["liquidity"])
        val_yes = p["yes_shares"] * py
        val_no = p["no_shares"] * (1 - py)
        total_value += val_yes + val_no
        pos_rows.append(Tr(
            Td(A(p["question"], href=f"/market/{p['market_id']}")),
            Td(f"{p['yes_shares']:.2f}"),
            Td(f"{p['no_shares']:.2f}"),
            Td(f"{py*100:.1f}%"),
            Td(f"{val_yes + val_no:.2f}"),
        ))

    trade_rows = [
        Tr(
            Td(t["ts"].replace("T", " ").rstrip("Z")),
            Td(t["question"]),
            Td(f"{'BUY' if t['shares']>0 else 'SELL'} {t['side']}"),
            Td(f"{abs(t['shares']):.2f}"),
            Td(f"{t['cost']:+.2f}"),
        )
        for t in trades
    ]

    return page(
        user, "Portfolio",
        H2("Portfolio"),
        P(f"Saldo cash: ", Strong(f"{bal:.2f} cr"),
          "   |   Valore stimato totale: ", Strong(f"{total_value:.2f} cr")),
        H4("Posizioni aperte"),
        Table(
            Thead(Tr(Th("Mercato"), Th("YES"), Th("NO"), Th("Prezzo YES"), Th("Valore mark-to-market"))),
            Tbody(*pos_rows) if pos_rows else Tbody(Tr(Td("Nessuna posizione", colspan="5"))),
        ),
        H4("Ultimi trade"),
        Table(
            Thead(Tr(Th("Quando"), Th("Mercato"), Th("Op"), Th("Shares"), Th("Costo"))),
            Tbody(*trade_rows) if trade_rows else Tbody(Tr(Td("Nessun trade", colspan="5"))),
        ),
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@rt("/admin")
def get(sess, err: str = "", ok: str = ""):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)

    rows = []
    for m in db.list_markets():
        stats = db.market_stats(m["id"])
        p_yes = mkt.price_yes(m["q_yes"], m["q_no"], m["liquidity"])
        status_label = {
            "open": "aperto",
            "resolved_yes": "risolto YES",
            "resolved_no": "risolto NO",
        }.get(m["status"], m["status"])
        warn = ""
        if m["status"] == "open" and stats["n_holders"] > 0:
            warn = f" - {stats['n_holders']} possessori verranno rimborsati"

        rows.append(Tr(
            Td(A(m["question"], href=f"/market/{m['id']}"),
               Br(), Small(m["id"], style="color:#888")),
            Td(status_label),
            Td(m["expires"]),
            Td(f"{p_yes*100:.1f}% / {(1-p_yes)*100:.1f}%"),
            Td(stats["n_trades"]),
            Td(
                Form(
                    Button("Elimina", type="submit",
                           cls="contrast",
                           onclick=f"return confirm('Eliminare definitivamente \\'{m['question']}\\'?{warn}')"),
                    action=f"/admin/delete/{m['id']}",
                    method="post",
                    style="margin:0",
                ),
            ),
        ))

    msg = None
    if err: msg = ("err", err)
    elif ok: msg = ("ok", ok)

    return page(
        user, "Admin",
        H2("Pannello admin"),
        Div(
            A("Crea nuovo mercato", href="/admin/markets/new", role="button"),
            " ",
            A("Gestisci crediti utenti", href="/admin/users", role="button", cls="secondary"),
            style="margin-bottom: 1rem",
        ),
        P(Small(
            "Eliminare un mercato cancella tutti i trade e le posizioni associate. "
            "Se il mercato e' ancora aperto, i possessori vengono rimborsati al valore mark-to-market corrente. "
            "La cancellazione e' definitiva: i mercati di config.yaml vengono seminati una sola volta e non riappaiono al riavvio."
        )),
        Table(
            Thead(Tr(Th("Mercato"), Th("Stato"), Th("Scadenza"),
                     Th("YES / NO"), Th("# trade"), Th("Azioni"))),
            Tbody(*rows) if rows else Tbody(Tr(Td("Nessun mercato", colspan="6"))),
        ),
        msg=msg,
    )


@rt("/admin/delete/{mid}")
def post(sess, mid: str):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)
    try:
        db.delete_market(mid)
    except ValueError as e:
        return RedirectResponse(f"/admin?err={e}", status_code=303)
    return RedirectResponse(f"/admin?ok=Mercato+{mid}+eliminato", status_code=303)


# --- crea mercato ---------------------------------------------------------

import re as _re
_MARKET_ID_RE = _re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


@rt("/admin/markets/new")
def get(sess, err: str = ""):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)
    return page(
        user, "Crea mercato",
        H2("Crea nuovo mercato"),
        Form(
            Label("ID (lowercase, lettere/cifre/trattini)",
                  Input(name="mid", required=True, placeholder="es. gara-trazioni",
                        pattern="[a-z0-9][a-z0-9-]{1,63}")),
            Label("Domanda",
                  Input(name="question", required=True,
                        placeholder="Es. Simone fara' piu' trazioni di Andrea?")),
            Label("Scadenza (YYYY-MM-DD)",
                  Input(name="expires", type="date", required=True)),
            Label("Liquidity b (piu' alto = quote piu' lente)",
                  Input(name="liquidity", type="number", min="1", step="1", value="100", required=True)),
            Button("Crea", type="submit"),
            method="post",
            action="/admin/markets/new",
        ),
        P(A("annulla", href="/admin")),
        msg=("err", err) if err else None,
    )


@rt("/admin/markets/new")
def post(sess, mid: str, question: str, expires: str, liquidity: float):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)

    mid = mid.strip()
    question = question.strip()
    expires = expires.strip()

    if not _MARKET_ID_RE.match(mid):
        return RedirectResponse("/admin/markets/new?err=ID+non+valido", status_code=303)
    if not question:
        return RedirectResponse("/admin/markets/new?err=Domanda+vuota", status_code=303)
    try:
        date.fromisoformat(expires)
    except ValueError:
        return RedirectResponse("/admin/markets/new?err=Data+invalida", status_code=303)
    if expires <= date.today().isoformat():
        return RedirectResponse("/admin/markets/new?err=Scadenza+deve+essere+nel+futuro", status_code=303)
    if liquidity <= 0:
        return RedirectResponse("/admin/markets/new?err=Liquidity+deve+essere+positiva", status_code=303)

    try:
        db.create_market(mid, question, expires, liquidity, list(USERS.keys()))
    except ValueError as e:
        return RedirectResponse(f"/admin/markets/new?err={e}", status_code=303)
    return RedirectResponse(f"/admin?ok=Mercato+{mid}+creato", status_code=303)


# --- gestione crediti utenti ---------------------------------------------

@rt("/admin/users")
def get(sess, err: str = "", ok: str = ""):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)

    balances = {b["username"]: b["balance"] for b in db.list_balances()}
    rows = []
    for username, info in USERS.items():
        bal = balances.get(username, 0.0)
        rows.append(Tr(
            Td(username, " ", Span("admin", cls="pill") if info.get("admin") else ""),
            Td(f"{bal:.2f}"),
            Td(
                Form(
                    Input(name="balance", type="number", step="0.01", value=f"{bal:.2f}",
                          required=True, style="width:8rem; display:inline-block"),
                    Button("Imposta", type="submit", style="margin-left:.5rem"),
                    action=f"/admin/users/{username}/credits",
                    method="post",
                    style="display:flex; gap:.5rem; align-items:center; margin:0",
                ),
            ),
            Td(A("Modifica token", href=f"/admin/users/{username}/positions",
                 role="button", cls="secondary")),
        ))

    msg = None
    if err: msg = ("err", err)
    elif ok: msg = ("ok", ok)

    return page(
        user, "Crediti utenti",
        H2("Crediti utenti"),
        P(Small("Imposta il saldo totale (in crediti) per ciascun utente. "
                "Valori negativi sono ammessi (l'utente potra' solo vendere).")),
        Table(
            Thead(Tr(Th("Utente"), Th("Saldo attuale"), Th("Nuovo saldo"), Th("Token"))),
            Tbody(*rows),
        ),
        P(A("torna all'admin", href="/admin")),
        msg=msg,
    )


@rt("/admin/users/{username}/credits")
def post(sess, username: str, balance: float):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)
    if username not in USERS:
        return RedirectResponse("/admin/users?err=Utente+sconosciuto", status_code=303)
    try:
        db.set_balance(username, balance)
    except ValueError as e:
        return RedirectResponse(f"/admin/users?err={e}", status_code=303)
    return RedirectResponse(
        f"/admin/users?ok=Saldo+di+{username}+impostato+a+{balance:.2f}", status_code=303)


# --- gestione token (posizioni) utenti -----------------------------------

@rt("/admin/users/{username}/positions")
def get(sess, username: str, err: str = "", ok: str = ""):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)
    if username not in USERS:
        return RedirectResponse("/admin/users?err=Utente+sconosciuto", status_code=303)

    rows = []
    for m in db.list_markets():
        yes_sh, no_sh = db.get_position(username, m["id"])
        rows.append(Tr(
            Td(A(m["question"], href=f"/market/{m['id']}"),
               Br(), Small(m["id"], style="color:#8b97a4")),
            Td(
                Form(
                    Input(name="yes_shares", type="number", step="0.01", min="0",
                          value=f"{yes_sh:.2f}", required=True,
                          style="width:6rem; display:inline-block"),
                    Input(name="no_shares", type="number", step="0.01", min="0",
                          value=f"{no_sh:.2f}", required=True,
                          style="width:6rem; display:inline-block"),
                    Button("Imposta", type="submit"),
                    action=f"/admin/users/{username}/positions/{m['id']}",
                    method="post",
                    style="display:flex; gap:.5rem; align-items:center; margin:0",
                ),
            ),
        ))

    msg = None
    if err: msg = ("err", err)
    elif ok: msg = ("ok", ok)

    return page(
        user, f"Token di {username}",
        H2(f"Token di {username}"),
        P(Small("Assegna direttamente le share YES / NO possedute dall'utente in ciascun "
                "mercato. E' un override: non modifica le quote del mercato ne' il saldo.")),
        Table(
            Thead(Tr(Th("Mercato"), Th("YES / NO posseduti"))),
            Tbody(*rows) if rows else Tbody(Tr(Td("Nessun mercato", colspan="2"))),
        ),
        P(A("torna ai crediti utenti", href="/admin/users")),
        msg=msg,
    )


@rt("/admin/users/{username}/positions/{mid}")
def post(sess, username: str, mid: str, yes_shares: float, no_shares: float):
    user = current_user(sess)
    if not is_admin(user):
        return RedirectResponse("/", status_code=303)
    if username not in USERS:
        return RedirectResponse("/admin/users?err=Utente+sconosciuto", status_code=303)
    try:
        db.set_position(username, mid, yes_shares, no_shares)
    except ValueError as e:
        return RedirectResponse(f"/admin/users/{username}/positions?err={e}", status_code=303)
    return RedirectResponse(
        f"/admin/users/{username}/positions?ok=Token+aggiornati+per+{mid}", status_code=303)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # In locale gira su 5001 con auto-reload; in container (HF Space) imposta
    # PORT=7860 e disabilita il reload.
    in_container = "PORT" in os.environ
    port = int(os.environ.get("PORT", 5001))
    serve(host="0.0.0.0", port=port, reload=not in_container)
