import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path


class AuditLogger:
    """操作审计日志

    记录所有文件操作（谁、何时、做了什么），
    支持查询、统计和告警。
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        retention_days: int = 90,
    ):
        self.retention_days = retention_days
        if db_path is None:
            db_path = os.path.join("logs", "audit.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    user_id TEXT DEFAULT 'system',
                    status TEXT NOT NULL,
                    detail TEXT,
                    duration_ms INTEGER,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation
                ON audit_log(operation)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON audit_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON audit_log(status)
            """)

    def log(
        self,
        operation: str,
        resource: str,
        user_id: str = "system",
        status: str = "success",
        detail: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        trace_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (trace_id, timestamp, operation, resource, user_id,
                    status, detail, duration_ms, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace_id,
                    timestamp,
                    operation,
                    resource,
                    user_id,
                    status,
                    detail,
                    duration_ms,
                    json.dumps(metadata, ensure_ascii=False) if metadata else None,
                ),
            )

        return trace_id

    def log_success(
        self,
        operation: str,
        resource: str,
        duration_ms: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        return self.log(
            operation=operation,
            resource=resource,
            status="success",
            duration_ms=duration_ms,
            **kwargs,
        )

    def log_failure(
        self,
        operation: str,
        resource: str,
        error: str,
        duration_ms: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        return self.log(
            operation=operation,
            resource=resource,
            status="failure",
            detail=error,
            duration_ms=duration_ms,
            **kwargs,
        )

    def log_security_event(
        self,
        operation: str,
        resource: str,
        detail: str,
        **kwargs: Any,
    ) -> str:
        return self.log(
            operation=f"security_{operation}",
            resource=resource,
            status="blocked",
            detail=detail,
            **kwargs,
        )

    def query(
        self,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: List[Any] = []

        if operation:
            sql += " AND operation LIKE ?"
            params.append(f"%{operation}%")
        if status:
            sql += " AND status = ?"
            params.append(status)
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "timestamp": row["timestamp"],
                "operation": row["operation"],
                "resource": row["resource"],
                "user_id": row["user_id"],
                "status": row["status"],
                "detail": row["detail"],
                "duration_ms": row["duration_ms"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }
            for row in rows
        ]

    def cleanup_expired(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """DELETE FROM audit_log
                   WHERE timestamp < datetime('now', ?)""",
                (f"-{self.retention_days} days",),
            )
            return cursor.rowcount


_instances: Dict[str, AuditLogger] = {}


def get_audit_logger(db_path: Optional[str] = None) -> AuditLogger:
    """获取审计日志单例"""
    key = db_path or "default"
    if key not in _instances:
        _instances[key] = AuditLogger(db_path=db_path)
    return _instances[key]
