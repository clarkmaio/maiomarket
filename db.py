"""Data layer per MaioMarket.

Di default usa SQLite locale (file `MAIOMARKET_DB`). Se sono presenti le env
`TURSO_DATABASE_URL` (+ `TURSO_AUTH_TOKEN`) usa Turso/libSQL come storage
persistente: in pratica tiene un *embedded replica* locale (lo stesso file) che
viene sincronizzato col database remoto Turso -> i dati sopravvivono al riavvio
dello Space anche se il filesystem e' effimero.

L'accesso alle righe avviene sempre per nome di colonna: un piccolo adapter
converte ogni riga in dict cosi' il resto del modulo e' identico per i due
backend.
"""

from __future__ import annotations
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("MAIOMARKET_DB", "maiomarket.db")

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
USE_TURSO = bool(TURSO_URL)

# Pull dello stato remoto fatto una volta al primo accesso (cold start).
_pulled_once = False


SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    expires TEXT NOT NULL,
    liquidity REAL NOT NULL,
    q_yes REAL NOT NULL DEFAULT 0,
    q_no  REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',   -- open | resolved_yes | resolved_no
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    market_id TEXT NOT NULL,
    username TEXT NOT NULL,
    side TEXT NOT NULL,             -- YES | NO
    shares REAL NOT NULL,           -- + buy, - sell
    cost REAL NOT NULL,             -- + paid, - received
    price_yes_after REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id);
CREATE INDEX IF NOT EXISTS idx_trades_user   ON trades(username);

CREATE TABLE IF NOT EXISTS balances (
    username TEXT PRIMARY KEY,
    balance REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    username TEXT NOT NULL,
    market_id TEXT NOT NULL,
    yes_shares REAL NOT NULL DEFAULT 0,
    no_shares  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (username, market_id)
);

-- Mercati di config.yaml gia' seminati: evita che un mercato cancellato
-- venga ricreato al successivo avvio/reload del server.
CREATE TABLE IF NOT EXISTS seeded_markets (
    id TEXT PRIMARY KEY,
    seeded_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Connessione: adapter unico per sqlite3 e Turso/libSQL
# ---------------------------------------------------------------------------

def _split_sql(script: str) -> list[str]:
    """Spezza uno script in singoli statement, ignorando commenti `-- ...`."""
    no_comments = "\n".join(
        line for line in script.splitlines() if not line.strip().startswith("--")
    )
    return [s.strip() for s in no_comments.split(";") if s.strip()]


class _Result:
    """Wrappa un cursor restituendo righe come dict (accesso per nome)."""

    def __init__(self, cursor):
        self._cur = cursor
        self._cols = [d[0] for d in cursor.description] if cursor.description else None

    def _wrap(self, row):
        if row is None or self._cols is None:
            return row
        return {k: row[i] for i, k in enumerate(self._cols)}

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    @property
    def rowcount(self):
        return self._cur.rowcount


class _Conn:
    """Connessione minimale comune ai due backend."""

    def __init__(self, raw, is_turso):
        self._raw = raw
        self._is_turso = is_turso

    def execute(self, sql, params=()):
        return _Result(self._raw.execute(sql, params))

    def executescript(self, script):
        if self._is_turso:
            for stmt in _split_sql(script):
                self._raw.execute(stmt)
        else:
            self._raw.executescript(script)

    def commit(self):
        self._raw.commit()
        if self._is_turso:
            try:
                self._raw.sync()  # push delle scritture verso Turso
            except Exception:
                pass

    def close(self):
        self._raw.close()


def _raw_connect():
    global _pulled_once
    if USE_TURSO:
        import libsql  # pip install libsql
        raw = libsql.connect(DB_PATH, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        if not _pulled_once:
            try:
                raw.sync()  # pull dello stato remoto al cold start
            except Exception:
                pass
            _pulled_once = True
        return raw, True
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return raw, False


@contextmanager
def conn():
    raw, is_turso = _raw_connect()
    c = _Conn(raw, is_turso)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db(users: list[dict], markets: list[dict], initial_balance: float):
    """Crea tabelle e popola da config. Idempotente: non sovrascrive stato esistente."""
    with conn() as c:
        c.executescript(SCHEMA)

        for u in users:
            c.execute(
                "INSERT OR IGNORE INTO balances(username, balance) VALUES (?, ?)",
                (u["username"], initial_balance),
            )

        for m in markets:
            # Semina ogni mercato di config una sola volta. Se e' gia' stato
            # seminato (anche se poi cancellato dall'admin) non lo ricreiamo.
            already = c.execute(
                "SELECT 1 FROM seeded_markets WHERE id=?", (m["id"],)
            ).fetchone()
            if already:
                continue
            c.execute(
                """INSERT OR IGNORE INTO markets
                   (id, question, expires, liquidity, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (m["id"], m["question"], m["expires"], float(m["liquidity"]), now_iso()),
            )
            for u in users:
                c.execute(
                    """INSERT OR IGNORE INTO positions(username, market_id)
                       VALUES (?, ?)""",
                    (u["username"], m["id"]),
                )
            c.execute(
                "INSERT INTO seeded_markets(id, seeded_at) VALUES (?, ?)",
                (m["id"], now_iso()),
            )

        # Garantisce una riga 'positions' per ogni (utente, mercato) esistente:
        # cosi' anche un utente aggiunto a config.yaml in un secondo momento puo'
        # operare sui mercati gia' creati (config o da UI admin).
        existing = c.execute("SELECT id FROM markets").fetchall()
        for u in users:
            for mk in existing:
                c.execute(
                    "INSERT OR IGNORE INTO positions(username, market_id) VALUES (?, ?)",
                    (u["username"], mk["id"]),
                )


def get_balance(username: str) -> float:
    with conn() as c:
        row = c.execute("SELECT balance FROM balances WHERE username=?", (username,)).fetchone()
    return row["balance"] if row else 0.0


def get_market(market_id: str):
    with conn() as c:
        return c.execute("SELECT * FROM markets WHERE id=?", (market_id,)).fetchone()


def list_markets():
    with conn() as c:
        return c.execute("SELECT * FROM markets ORDER BY status, expires").fetchall()


def get_position(username: str, market_id: str):
    with conn() as c:
        row = c.execute(
            "SELECT yes_shares, no_shares FROM positions WHERE username=? AND market_id=?",
            (username, market_id),
        ).fetchone()
    if not row:
        return 0.0, 0.0
    return row["yes_shares"], row["no_shares"]


def user_positions(username: str):
    with conn() as c:
        return c.execute(
            """SELECT p.market_id, p.yes_shares, p.no_shares,
                      m.question, m.q_yes, m.q_no, m.liquidity, m.status
               FROM positions p JOIN markets m ON m.id = p.market_id
               WHERE p.username = ?
                 AND (p.yes_shares <> 0 OR p.no_shares <> 0)""",
            (username,),
        ).fetchall()


def trade_history(market_id: str):
    with conn() as c:
        return c.execute(
            """SELECT ts, username, side, shares, cost, price_yes_after
               FROM trades WHERE market_id=? ORDER BY id ASC""",
            (market_id,),
        ).fetchall()


def user_trades(username: str, limit: int = 100):
    with conn() as c:
        return c.execute(
            """SELECT t.*, m.question FROM trades t JOIN markets m ON m.id=t.market_id
               WHERE t.username=? ORDER BY t.id DESC LIMIT ?""",
            (username, limit),
        ).fetchall()


def record_trade(
    username: str,
    market_id: str,
    side: str,
    shares: float,
    cost: float,
    new_q_yes: float,
    new_q_no: float,
    price_yes_after: float,
) -> None:
    """Esegue il trade atomicamente: aggiorna market, balance, posizione, log."""
    with conn() as c:
        c.execute(
            "UPDATE markets SET q_yes=?, q_no=? WHERE id=?",
            (new_q_yes, new_q_no, market_id),
        )
        c.execute(
            "UPDATE balances SET balance = balance - ? WHERE username=?",
            (cost, username),
        )
        col = "yes_shares" if side.upper() == "YES" else "no_shares"
        c.execute(
            f"""INSERT INTO positions(username, market_id, {col})
                VALUES (?, ?, ?)
                ON CONFLICT(username, market_id)
                DO UPDATE SET {col} = {col} + excluded.{col}""",
            (username, market_id, shares),
        )
        c.execute(
            """INSERT INTO trades(ts, market_id, username, side, shares, cost, price_yes_after)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now_iso(), market_id, username, side.upper(), shares, cost, price_yes_after),
        )


def create_market(
    market_id: str,
    question: str,
    expires: str,
    liquidity: float,
    usernames: list[str],
) -> None:
    with conn() as c:
        existing = c.execute("SELECT id FROM markets WHERE id=?", (market_id,)).fetchone()
        if existing:
            raise ValueError(f"id '{market_id}' gia' esistente")
        c.execute(
            """INSERT INTO markets(id, question, expires, liquidity, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (market_id, question, expires, float(liquidity), now_iso()),
        )
        for u in usernames:
            c.execute(
                "INSERT OR IGNORE INTO positions(username, market_id) VALUES (?, ?)",
                (u, market_id),
            )


def list_balances():
    with conn() as c:
        return c.execute(
            "SELECT username, balance FROM balances ORDER BY username"
        ).fetchall()


def set_balance(username: str, new_balance: float) -> None:
    with conn() as c:
        cur = c.execute(
            "UPDATE balances SET balance=? WHERE username=?",
            (float(new_balance), username),
        )
        if cur.rowcount == 0:
            raise ValueError(f"utente '{username}' non trovato")


def set_position(username: str, market_id: str, yes_shares: float, no_shares: float) -> None:
    """Override admin delle share YES/NO possedute da un utente in un mercato.

    Non tocca q_yes/q_no del mercato ne' il saldo: e' un assegnamento diretto
    dei token (uso goliardico/correttivo).
    """
    if yes_shares < 0 or no_shares < 0:
        raise ValueError("le share non possono essere negative")
    with conn() as c:
        m = c.execute("SELECT 1 FROM markets WHERE id=?", (market_id,)).fetchone()
        if not m:
            raise ValueError(f"mercato '{market_id}' non trovato")
        c.execute(
            """INSERT INTO positions(username, market_id, yes_shares, no_shares)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(username, market_id)
               DO UPDATE SET yes_shares=excluded.yes_shares, no_shares=excluded.no_shares""",
            (username, market_id, float(yes_shares), float(no_shares)),
        )


def market_trades(market_id: str):
    """Tutti i trade di un mercato, con id (per la gestione admin)."""
    with conn() as c:
        return c.execute(
            """SELECT id, ts, username, side, shares, cost, price_yes_after
               FROM trades WHERE market_id=? ORDER BY id DESC""",
            (market_id,),
        ).fetchall()


def delete_trade(trade_id: int) -> None:
    """Cancella un trade STORNANDONE gli effetti, cosi' saldo/posizioni/quote
    restano coerenti (come se il trade non fosse mai avvenuto)."""
    with conn() as c:
        t = c.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not t:
            raise ValueError("trade non trovato")
        mid, user = t["market_id"], t["username"]
        side = t["side"].upper()
        shares, cost = t["shares"], t["cost"]

        # storno della quota di mercato (q era stato spostato di +shares sul lato)
        qcol = "q_yes" if side == "YES" else "q_no"
        c.execute(f"UPDATE markets SET {qcol} = {qcol} - ? WHERE id=?", (shares, mid))
        # rimborso del costo (era stato sottratto al saldo)
        c.execute("UPDATE balances SET balance = balance + ? WHERE username=?", (cost, user))
        # storno della posizione
        pcol = "yes_shares" if side == "YES" else "no_shares"
        c.execute(
            f"UPDATE positions SET {pcol} = {pcol} - ? WHERE username=? AND market_id=?",
            (shares, user, mid),
        )
        c.execute("DELETE FROM trades WHERE id=?", (trade_id,))


def set_market_price(market_id: str, p_yes: float) -> None:
    """Imposta la chance YES del mercato (override admin).

    Nel modello LMSR il prezzo dipende da q_yes/q_no e dalla liquidita' b:
    scegliamo q_yes = b*ln(p/(1-p)), q_no = 0, che da' esattamente price_yes = p.
    Non tocca i token gia' posseduti dagli utenti.
    """
    import math
    p = min(max(float(p_yes), 0.001), 0.999)
    with conn() as c:
        m = c.execute("SELECT liquidity FROM markets WHERE id=?", (market_id,)).fetchone()
        if not m:
            raise ValueError("mercato non trovato")
        b = m["liquidity"]
        q_yes = b * math.log(p / (1.0 - p))
        c.execute("UPDATE markets SET q_yes=?, q_no=0 WHERE id=?", (q_yes, market_id))


def market_stats(market_id: str):
    with conn() as c:
        row = c.execute(
            """SELECT
                (SELECT COUNT(*) FROM trades    WHERE market_id=?) AS n_trades,
                (SELECT COUNT(*) FROM positions WHERE market_id=?
                                          AND (yes_shares<>0 OR no_shares<>0)) AS n_holders
            """,
            (market_id, market_id),
        ).fetchone()
    return row


def delete_market(market_id: str) -> None:
    """Cancella un mercato e tutto cio' che ne dipende.

    Se ci sono posizioni aperte (mercato non risolto) restituisce ai possessori
    quello che hanno speso per quelle share, calcolato come il prezzo medio
    pagato. Per semplicita' qui rimborsiamo il valore mark-to-market corrente:
    e' il modo piu' equo senza ricostruire il book.
    """
    with conn() as c:
        m = c.execute("SELECT * FROM markets WHERE id=?", (market_id,)).fetchone()
        if not m:
            raise ValueError("market non trovato")

        if m["status"] == "open":
            import math
            b = m["liquidity"]
            q_y, q_n = m["q_yes"], m["q_no"]
            p_yes = 1.0 / (1.0 + math.exp((q_n - q_y) / b))
            holders = c.execute(
                """SELECT username, yes_shares, no_shares FROM positions
                   WHERE market_id=? AND (yes_shares<>0 OR no_shares<>0)""",
                (market_id,),
            ).fetchall()
            for h in holders:
                refund = h["yes_shares"] * p_yes + h["no_shares"] * (1 - p_yes)
                if refund > 0:
                    c.execute(
                        "UPDATE balances SET balance = balance + ? WHERE username=?",
                        (refund, h["username"]),
                    )

        c.execute("DELETE FROM trades    WHERE market_id=?", (market_id,))
        c.execute("DELETE FROM positions WHERE market_id=?", (market_id,))
        c.execute("DELETE FROM markets   WHERE id=?", (market_id,))


def resolve_market(market_id: str, outcome: str) -> None:
    """outcome: 'YES' o 'NO'. Paga 1 credito per ogni share del lato vincente."""
    outcome = outcome.upper()
    assert outcome in ("YES", "NO")
    status = "resolved_yes" if outcome == "YES" else "resolved_no"
    win_col = "yes_shares" if outcome == "YES" else "no_shares"

    with conn() as c:
        m = c.execute("SELECT status FROM markets WHERE id=?", (market_id,)).fetchone()
        if not m:
            raise ValueError("market non trovato")
        if m["status"] != "open":
            raise ValueError("market gia' risolto")

        rows = c.execute(
            f"SELECT username, {win_col} AS win FROM positions WHERE market_id=? AND {win_col} > 0",
            (market_id,),
        ).fetchall()
        for r in rows:
            c.execute(
                "UPDATE balances SET balance = balance + ? WHERE username=?",
                (r["win"], r["username"]),
            )
        c.execute("UPDATE markets SET status=? WHERE id=?", (status, market_id))
