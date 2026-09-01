"""Persistence + observability — SQLite (default) or Postgres. Owner: mr.jarvis0.

Honest local stand-in for the readme §15 data layer (PostgreSQL + audit) and §19
observability. Everything is event-sourced: trip snapshots + an append-only
`trip_events` log, plus `agent_runs` (cost/latency/confidence/sources) and
`bookings` (saga output incl. real PNR/order refs).

Backend swap (readme §15, "the call sites don't change"): set DATABASE_URL to a
Postgres DSN and this module talks to Postgres instead — same public functions,
same shapes. Blank DATABASE_URL (the default) → local SQLite on one file. If a
Postgres DSN is set but the driver/server is unreachable, it falls back to SQLite
with a printed warning rather than crashing.
"""
import json
import pathlib
import time

from . import config

_DB_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "safar.db"
_conn = None
_PG = config.DATABASE_URL.startswith(("postgres://", "postgresql://"))

# Portable schema: two dialects, identical columns. JSON is stored as TEXT in
# both (our code json.dumps/loads it), so no jsonb-specific code is needed.
_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS trips(
  trip_id TEXT PRIMARY KEY, user_id TEXT, status TEXT, version INTEGER,
  snapshot TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS trip_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT, seq INTEGER,
  type TEXT, payload TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS agent_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT, agent TEXT, status TEXT,
  confidence REAL, cost_usd REAL, latency_ms INTEGER, sources TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT, type TEXT, vendor TEXT,
  status TEXT, idempotency_key TEXT, amount_inr REAL, ref TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS profiles(
  user_id TEXT PRIMARY KEY, weights TEXT, history TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS provenance(
  id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT, claim TEXT, source TEXT,
  retrieved_at TEXT, expires_at TEXT, confidence REAL, created_at REAL);
"""
_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS trips(
  trip_id TEXT PRIMARY KEY, user_id TEXT, status TEXT, version INTEGER,
  snapshot TEXT, updated_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS trip_events(
  id BIGSERIAL PRIMARY KEY, trip_id TEXT, seq INTEGER,
  type TEXT, payload TEXT, created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS agent_runs(
  id BIGSERIAL PRIMARY KEY, trip_id TEXT, agent TEXT, status TEXT,
  confidence DOUBLE PRECISION, cost_usd DOUBLE PRECISION, latency_ms INTEGER,
  sources TEXT, created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS bookings(
  id BIGSERIAL PRIMARY KEY, trip_id TEXT, type TEXT, vendor TEXT,
  status TEXT, idempotency_key TEXT, amount_inr DOUBLE PRECISION, ref TEXT,
  created_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS profiles(
  user_id TEXT PRIMARY KEY, weights TEXT, history TEXT, updated_at DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS provenance(
  id BIGSERIAL PRIMARY KEY, trip_id TEXT, claim TEXT, source TEXT,
  retrieved_at TEXT, expires_at TEXT, confidence DOUBLE PRECISION,
  created_at DOUBLE PRECISION);
"""


def backend() -> str:
    """'postgres' or 'sqlite' — resolved after the first conn()."""
    conn()
    return "postgres" if _PG else "sqlite"


def conn():
    """Lazily open the backing connection (Postgres if DATABASE_URL, else SQLite)."""
    global _conn, _PG
    if _conn is not None:
        return _conn
    if _PG:
        try:
            import psycopg                       # psycopg 3
            _conn = psycopg.connect(config.DATABASE_URL, autocommit=True)
            for stmt in filter(str.strip, _SCHEMA_PG.split(";")):
                _conn.execute(stmt)
            return _conn
        except Exception as e:                   # noqa: BLE001 — degrade, never crash
            print(f"[store] Postgres unavailable ({str(e)[:120]}); using SQLite")
            _PG = False
    import sqlite3
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: Streamlit reruns across threads; our writes are
    # short + serialized per interaction, so a single shared connection is fine.
    _conn = sqlite3.connect(str(_DB_FILE), check_same_thread=False)
    _conn.executescript(_SCHEMA_SQLITE)
    _conn.commit()
    _migrate_sqlite(_conn)
    return _conn


def _migrate_sqlite(c) -> None:
    """Best-effort column add for DBs created before the `ref` column existed."""
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(bookings)").fetchall()]
        if "ref" not in cols:
            c.execute("ALTER TABLE bookings ADD COLUMN ref TEXT")
            c.commit()
    except Exception:
        pass


# ---- placeholder + commit helpers (bridge the two dialects) ------------------
def _sql(q: str) -> str:
    return q.replace("?", "%s") if _PG else q


def _exec(q: str, params: tuple = ()):
    cur = conn().execute(_sql(q), params)
    if not _PG:
        _conn.commit()
    return cur


def _query(q: str, params: tuple = ()) -> list:
    return conn().execute(_sql(q), params).fetchall()


def save_trip(state) -> None:
    snap = json.dumps(_snapshot(state), default=str)
    row = (state.trip_id, getattr(state, "user_id", "demo"), state.status,
           len(getattr(state, "_events", []) or []), snap, time.time())
    if _PG:
        _exec("INSERT INTO trips(trip_id,user_id,status,version,snapshot,updated_at)"
              " VALUES(?,?,?,?,?,?) ON CONFLICT (trip_id) DO UPDATE SET"
              " user_id=EXCLUDED.user_id, status=EXCLUDED.status,"
              " version=EXCLUDED.version, snapshot=EXCLUDED.snapshot,"
              " updated_at=EXCLUDED.updated_at", row)
    else:
        _exec("INSERT OR REPLACE INTO trips VALUES (?,?,?,?,?,?)", row)


def append_event(trip_id: str, etype: str, payload: dict) -> None:
    seq = _query("SELECT COALESCE(MAX(seq), 0) + 1 FROM trip_events WHERE trip_id=?",
                 (trip_id,))[0][0]
    _exec("INSERT INTO trip_events(trip_id,seq,type,payload,created_at) VALUES(?,?,?,?,?)",
          (trip_id, seq, etype, json.dumps(payload, default=str), time.time()))


def log_agent_run(trip_id: str, agent: str, status: str = "complete",
                  confidence: float = 1.0, cost_usd: float = 0.0,
                  latency_ms: int = 0, sources: list | None = None) -> None:
    _exec("INSERT INTO agent_runs(trip_id,agent,status,confidence,cost_usd,"
          "latency_ms,sources,created_at) VALUES(?,?,?,?,?,?,?,?)",
          (trip_id, agent, status, confidence, cost_usd, latency_ms,
           json.dumps(sources or []), time.time()))


def record_booking(trip_id: str, btype: str, vendor: str, status: str,
                   idem: str, amount_inr: float, ref: str = "") -> None:
    """Record one saga step. `ref` carries the real PNR / order id in live mode."""
    _exec("INSERT INTO bookings(trip_id,type,vendor,status,idempotency_key,"
          "amount_inr,ref,created_at) VALUES(?,?,?,?,?,?,?,?)",
          (trip_id, btype, vendor, status, idem, amount_inr, ref, time.time()))


def update_booking_status(trip_id: str, idem: str, status: str) -> None:
    """Advance a booking's status (e.g. BOOKED → CAPTURED after human pays)."""
    _exec("UPDATE bookings SET status=? WHERE trip_id=? AND idempotency_key=?",
          (status, trip_id, idem))


def load_profile(user_id: str) -> dict | None:
    row = _query("SELECT weights,history FROM profiles WHERE user_id=?", (user_id,))
    if not row:
        return None
    return {"weights": json.loads(row[0][0]), "history": json.loads(row[0][1] or "[]")}


def save_profile(user_id: str, weights: dict, history: list) -> None:
    row = (user_id, json.dumps(weights), json.dumps(history), time.time())
    if _PG:
        _exec("INSERT INTO profiles(user_id,weights,history,updated_at)"
              " VALUES(?,?,?,?) ON CONFLICT (user_id) DO UPDATE SET"
              " weights=EXCLUDED.weights, history=EXCLUDED.history,"
              " updated_at=EXCLUDED.updated_at", row)
    else:
        _exec("INSERT OR REPLACE INTO profiles VALUES(?,?,?,?)", row)


def events(trip_id: str) -> list:
    rows = _query("SELECT seq,type,payload,created_at FROM trip_events "
                  "WHERE trip_id=? ORDER BY seq", (trip_id,))
    return [{"seq": s, "type": t, "payload": json.loads(p), "at": a}
            for s, t, p, a in rows]


def list_trips(limit: int = 20) -> list:
    rows = _query("SELECT trip_id,user_id,status,updated_at FROM trips "
                  "ORDER BY updated_at DESC LIMIT ?", (limit,))
    return [{"trip_id": t, "user_id": u, "status": s, "updated_at": a}
            for t, u, s, a in rows]


def agent_runs(trip_id: str) -> list:
    rows = _query("SELECT agent,status,confidence,cost_usd,latency_ms,created_at "
                  "FROM agent_runs WHERE trip_id=? ORDER BY id", (trip_id,))
    return [{"agent": a, "status": s, "confidence": c, "cost_usd": co,
             "latency_ms": l, "created_at": t} for a, s, c, co, l, t in rows]


def bookings(trip_id: str) -> list:
    rows = _query("SELECT type,vendor,status,idempotency_key,amount_inr,ref "
                  "FROM bookings WHERE trip_id=? ORDER BY id", (trip_id,))
    return [{"type": t, "vendor": v, "status": s, "idempotency_key": k,
             "amount_inr": a, "ref": r} for t, v, s, k, a, r in rows]


def agent_run_summary(trip_id: str) -> dict:
    rows = _query("SELECT COUNT(*), COALESCE(SUM(cost_usd),0), "
                  "COALESCE(AVG(confidence),0) FROM agent_runs WHERE trip_id=?",
                  (trip_id,))[0]
    return {"runs": rows[0], "cost_usd": round(rows[1], 4),
            "avg_confidence": round(rows[2], 3)}


def _snapshot(state) -> dict:
    return {"trip_id": state.trip_id, "status": state.status, "trip": state.trip,
            "constraints": state.constraints, "weights": state.weights,
            "candidates": state.candidates, "errors": state.errors,
            "warnings": getattr(state, "warnings", []),
            "provenance_count": len(getattr(state, "provenance", []) or [])}


def save_provenance(trip_id: str, records: list) -> None:
    """Persist provenance records (§11) to the provenance table."""
    for r in records:
        _exec("INSERT INTO provenance(trip_id,claim,source,retrieved_at,"
              "expires_at,confidence,created_at) VALUES(?,?,?,?,?,?,?)",
              (trip_id, r.get("claim"), r.get("source"),
               r.get("retrieved_at"), r.get("expires_at"),
               r.get("confidence", 0), time.time()))


def get_provenance(trip_id: str) -> list:
    """Retrieve provenance records for a trip."""
    rows = _query("SELECT claim,source,retrieved_at,expires_at,confidence "
                  "FROM provenance WHERE trip_id=? ORDER BY id", (trip_id,))
    return [{"claim": c, "source": s, "retrieved_at": r, "expires_at": e,
             "confidence": co} for c, s, r, e, co in rows]
