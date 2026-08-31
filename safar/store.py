"""Persistence + observability — SQLite (stdlib). Owner: mr.jarvis0.

Honest local stand-in for the readme §15 data layer (PostgreSQL + audit) and §19
observability. Everything is event-sourced: trip snapshots + an append-only
`trip_events` log, plus `agent_runs` (cost/latency/confidence/sources) and
`bookings`. Swap this module for real Postgres/Redis/VectorDB later — the call
sites don't change.

NOTE: not Postgres/Redis/Vector DB (those need running services); SQLite gives
the same shape — durable rows, an audit trail, optimistic version — on one file.
"""
import json
import pathlib
import sqlite3
import time

_DB = pathlib.Path(__file__).resolve().parents[1] / "data" / "safar.db"
_conn: sqlite3.Connection | None = None

_SCHEMA = """
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
  status TEXT, idempotency_key TEXT, amount_inr REAL, created_at REAL);
CREATE TABLE IF NOT EXISTS profiles(
  user_id TEXT PRIMARY KEY, weights TEXT, history TEXT, updated_at REAL);
"""


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: Streamlit reruns across threads; our writes are
        # short + serialized per interaction, so a single shared connection is fine.
        _conn = sqlite3.connect(str(_DB), check_same_thread=False)
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def save_trip(state) -> None:
    c = conn()
    snap = json.dumps(_snapshot(state), default=str)
    c.execute("INSERT OR REPLACE INTO trips VALUES (?,?,?,?,?,?)",
              (state.trip_id, getattr(state, "user_id", "demo"), state.status,
               len(getattr(state, "_events", []) or []), snap, time.time()))
    c.commit()


def append_event(trip_id: str, etype: str, payload: dict) -> None:
    c = conn()
    seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM trip_events WHERE trip_id=?",
                    (trip_id,)).fetchone()[0]
    c.execute("INSERT INTO trip_events(trip_id,seq,type,payload,created_at) VALUES(?,?,?,?,?)",
              (trip_id, seq, etype, json.dumps(payload, default=str), time.time()))
    c.commit()


def log_agent_run(trip_id: str, agent: str, status: str = "complete",
                  confidence: float = 1.0, cost_usd: float = 0.0,
                  latency_ms: int = 0, sources: list | None = None) -> None:
    c = conn()
    c.execute("INSERT INTO agent_runs(trip_id,agent,status,confidence,cost_usd,"
              "latency_ms,sources,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (trip_id, agent, status, confidence, cost_usd, latency_ms,
               json.dumps(sources or []), time.time()))
    c.commit()


def record_booking(trip_id: str, btype: str, vendor: str, status: str,
                   idem: str, amount_inr: float) -> None:
    c = conn()
    c.execute("INSERT INTO bookings(trip_id,type,vendor,status,idempotency_key,"
              "amount_inr,created_at) VALUES(?,?,?,?,?,?,?)",
              (trip_id, btype, vendor, status, idem, amount_inr, time.time()))
    c.commit()


def load_profile(user_id: str) -> dict | None:
    row = conn().execute("SELECT weights,history FROM profiles WHERE user_id=?",
                         (user_id,)).fetchone()
    if not row:
        return None
    return {"weights": json.loads(row[0]), "history": json.loads(row[1] or "[]")}


def save_profile(user_id: str, weights: dict, history: list) -> None:
    c = conn()
    c.execute("INSERT OR REPLACE INTO profiles VALUES(?,?,?,?)",
              (user_id, json.dumps(weights), json.dumps(history), time.time()))
    c.commit()


def events(trip_id: str) -> list:
    rows = conn().execute("SELECT seq,type,payload,created_at FROM trip_events "
                          "WHERE trip_id=? ORDER BY seq", (trip_id,)).fetchall()
    return [{"seq": s, "type": t, "payload": json.loads(p), "at": a}
            for s, t, p, a in rows]


def list_trips(limit: int = 20) -> list:
    rows = conn().execute("SELECT trip_id,user_id,status,updated_at FROM trips "
                          "ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [{"trip_id": t, "user_id": u, "status": s, "updated_at": a}
            for t, u, s, a in rows]


def agent_runs(trip_id: str) -> list:
    rows = conn().execute("SELECT agent,status,confidence,cost_usd,latency_ms,created_at "
                          "FROM agent_runs WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()
    return [{"agent": a, "status": s, "confidence": c, "cost_usd": co,
             "latency_ms": l, "created_at": t} for a, s, c, co, l, t in rows]


def bookings(trip_id: str) -> list:
    rows = conn().execute("SELECT type,vendor,status,idempotency_key,amount_inr "
                          "FROM bookings WHERE trip_id=? ORDER BY id", (trip_id,)).fetchall()
    return [{"type": t, "vendor": v, "status": s, "idempotency_key": k, "amount_inr": a}
            for t, v, s, k, a in rows]


def agent_run_summary(trip_id: str) -> dict:
    rows = conn().execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0), "
                          "COALESCE(AVG(confidence),0) FROM agent_runs WHERE trip_id=?",
                          (trip_id,)).fetchone()
    return {"runs": rows[0], "cost_usd": round(rows[1], 4),
            "avg_confidence": round(rows[2], 3)}


def _snapshot(state) -> dict:
    return {"trip_id": state.trip_id, "status": state.status, "trip": state.trip,
            "constraints": state.constraints, "weights": state.weights,
            "candidates": state.candidates, "errors": state.errors,
            "warnings": getattr(state, "warnings", [])}
