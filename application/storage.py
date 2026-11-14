"""Small offline SQLite repository for analysis results and audit history."""
import json
import gzip
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from application.schemas import ProcessingResult


class SQLiteStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        """Commit/rollback and always close SQLite handles (important on Windows)."""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _pack(value: Any) -> bytes:
        return gzip.compress(json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _unpack(value: Any) -> Any:
        if isinstance(value, bytes):
            value = gzip.decompress(value).decode("utf-8")
        return json.loads(value)

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS processing_sessions (
                    request_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
                    source_type TEXT NOT NULL, is_synthetic INTEGER NOT NULL,
                    astronaut_id TEXT, processing_status TEXT NOT NULL, result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL, source_type TEXT NOT NULL,
                    is_synthetic INTEGER NOT NULL, alert_state TEXT, alert_id TEXT,
                    alert_json TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES processing_sessions(request_id)
                );
                CREATE TABLE IF NOT EXISTS sensor_trust (
                    request_id TEXT PRIMARY KEY, source_type TEXT NOT NULL,
                    is_synthetic INTEGER NOT NULL, trust_json TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES processing_sessions(request_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON processing_sessions(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC);
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)")}
            if "alert_state" not in columns:
                conn.execute("ALTER TABLE alerts ADD COLUMN alert_state TEXT")
            if "alert_id" not in columns:
                conn.execute("ALTER TABLE alerts ADD COLUMN alert_id TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(alert_state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_alert_id ON alerts(alert_id)")
            for row in conn.execute("SELECT id,alert_json FROM alerts WHERE alert_id IS NULL").fetchall():
                try:
                    alert_id = self._unpack(row["alert_json"]).get("alert_id")
                    if alert_id:
                        conn.execute("UPDATE alerts SET alert_id=? WHERE id=?", (alert_id, row["id"]))
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue

    def save_result(self, result: ProcessingResult) -> None:
        data = result.to_dict()
        alerts_payload = data.get("alert") or data.get("alert_summary") or {}
        active = alerts_payload.get("active_alerts", []) if isinstance(alerts_payload, dict) else []
        try:
            with self._connection() as conn:
                conn.execute("""INSERT OR REPLACE INTO processing_sessions
                    (request_id,timestamp,source_type,is_synthetic,astronaut_id,processing_status,result_json)
                    VALUES(?,?,?,?,?,?,?)""", (
                    data["request_id"], data["timestamp"], data["source_type"],
                    int(bool(data["is_synthetic"])), data.get("astronaut_id"),
                    data["processing_status"], self._pack(data),
                ))
                conn.execute("DELETE FROM alerts WHERE request_id=?", (data["request_id"],))
                for alert in active:
                    conn.execute("INSERT INTO alerts(request_id,timestamp,source_type,is_synthetic,alert_state,alert_id,alert_json) VALUES(?,?,?,?,?,?,?)",
                                 (data["request_id"], data["timestamp"], data["source_type"], int(bool(data["is_synthetic"])), alert.get("alert_state"), alert.get("alert_id"), self._pack(alert)))
                trust = data.get("sensor_trust")
                if trust is not None:
                    conn.execute("INSERT OR REPLACE INTO sensor_trust VALUES(?,?,?,?)",
                                 (data["request_id"], data["source_type"], int(bool(data["is_synthetic"])), self._pack(trust)))
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise RuntimeError(f"Could not persist WEDJAT-X result: {exc}") from exc

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT result_json FROM processing_sessions ORDER BY timestamp DESC LIMIT ?", (max(0, int(limit)),)).fetchall()
        return [self._unpack(row[0]) for row in rows]

    def recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT request_id,alert_json FROM alerts ORDER BY timestamp DESC,id DESC LIMIT ?", (max(0, int(limit)),)).fetchall()
        return [{**self._unpack(row["alert_json"]), "request_id": row["request_id"]} for row in rows]

    def alert_detail(self, alert_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT request_id,source_type,is_synthetic,alert_json FROM alerts WHERE alert_id=? ORDER BY id DESC LIMIT 1", (alert_id,)).fetchone()
            if not row:
                return None
            session = conn.execute("SELECT result_json FROM processing_sessions WHERE request_id=?", (row["request_id"],)).fetchone()
        alert = self._unpack(row["alert_json"])
        alert.update({"source_type": row["source_type"], "is_synthetic": bool(row["is_synthetic"]), "alert_id": alert_id})
        return {"request_id": row["request_id"], "alert": alert,
                "analysis": self._unpack(session["result_json"]) if session else None}

    def latest(self, source_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            if source_type:
                row = conn.execute("SELECT result_json FROM processing_sessions WHERE source_type=? ORDER BY timestamp DESC,rowid DESC LIMIT 1", (source_type,)).fetchone()
            else:
                row = conn.execute("SELECT result_json FROM processing_sessions ORDER BY timestamp DESC,rowid DESC LIMIT 1").fetchone()
        return self._unpack(row[0]) if row else None

    def analysis_count(self) -> int:
        with self._connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM processing_sessions").fetchone()[0])

    def alert_count(self, source_type: Optional[str] = None, active_only: bool = False) -> int:
        """Count persisted alert event rows; active_only filters by alert state, not lifecycle."""
        clauses = []
        params: list[Any] = []
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if active_only:
            clauses.append("alert_state IN ('ATTENTION', 'REVIEW', 'CRITICAL')")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM alerts" + where, params).fetchone()[0])

    def latest_sensor_trust(self) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("""SELECT s.request_id,s.source_type,s.is_synthetic,p.timestamp,s.trust_json
                FROM sensor_trust s JOIN processing_sessions p ON p.request_id=s.request_id
                WHERE s.source_type='SYNTHETIC_WEARABLE' ORDER BY p.timestamp DESC LIMIT 1""").fetchone()
        if not row:
            return None
        return {"request_id": row["request_id"], "source_type": row["source_type"],
                "is_synthetic": bool(row["is_synthetic"]), "timestamp": row["timestamp"],
                "sensor_trust": self._unpack(row["trust_json"])}
