"""Dual SQLite memory store for T.I.V.I.S.S.

Provides two separate databases:
- conversation_logs.db: Append-only conversation history (request/response pairs)
- semantic_memory.db: Structured long-term memory (facts, preferences, context)
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .interface import MemoryBackend, MemoryRecord, MemorySearchResult


@dataclass
class ConversationLogEntry:
    """A single conversation log entry."""
    log_id: int
    request_id: str
    request_content: str
    response_content: str
    metadata: dict[str, Any]
    created_at: float


@dataclass
class SemanticMemoryEntry:
    """A single semantic memory entry."""
    record_id: str
    content: str
    category: str
    memory_type: str
    importance: int
    confidence: float
    source: str
    evidence: str
    metadata: dict[str, Any]
    created_at: float
    updated_at: float


class SQLiteMemoryStore:
    """Dual SQLite memory store with separate conversation and semantic databases."""

    def __init__(
        self,
        conversation_db: str,
        semantic_db: str,
        autosave: bool = True,
    ) -> None:
        self.conversation_db = Path(conversation_db)
        self.semantic_db = Path(semantic_db)
        self.autosave = autosave

        # Ensure parent directories exist
        self.conversation_db.parent.mkdir(parents=True, exist_ok=True)
        self.semantic_db.parent.mkdir(parents=True, exist_ok=True)

        self._init_conversation_db()
        self._init_semantic_db()

    def _init_conversation_db(self) -> None:
        """Initialize the conversation logs database."""
        with sqlite3.connect(self.conversation_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    request_content TEXT NOT NULL,
                    response_content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_request_id
                ON conversation_logs(request_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_created_at
                ON conversation_logs(created_at)
            """)

    def _init_semantic_db(self) -> None:
        """Initialize the semantic memory database."""
        with sqlite3.connect(self.semantic_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    record_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 5,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    source TEXT NOT NULL DEFAULT 'user-stated',
                    evidence TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_category
                ON semantic_memory(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_memory_type
                ON semantic_memory(memory_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_importance
                ON semantic_memory(importance)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_created_at
                ON semantic_memory(created_at)
            """)

    # --- Conversation Log Methods ---

    def append_conversation(
        self,
        request_id: str,
        request_content: str,
        response_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Append a conversation exchange to the log."""
        metadata = metadata or {}
        created_at = time.time()
        with sqlite3.connect(self.conversation_db) as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversation_logs
                (request_id, request_content, response_content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (request_id, request_content, response_content, json.dumps(metadata), created_at),
            )
            return cursor.lastrowid

    def get_conversation_history(
        self,
        limit: int = 100,
        session_id: str | None = None,
    ) -> list[ConversationLogEntry]:
        """Get recent conversation history."""
        query = "SELECT log_id, request_id, request_content, response_content, metadata, created_at FROM conversation_logs"
        params: list[Any] = []
        if session_id:
            query += " WHERE request_id LIKE ?"
            params.append(f"{session_id}%")
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.conversation_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [
            ConversationLogEntry(
                log_id=row["log_id"],
                request_id=row["request_id"],
                request_content=row["request_content"],
                response_content=row["response_content"],
                metadata=json.loads(row["metadata"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def search_conversation(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ConversationLogEntry]:
        """Search conversation history by content."""
        search_term = f"%{query}%"
        with sqlite3.connect(self.conversation_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT log_id, request_id, request_content, response_content, metadata, created_at
                FROM conversation_logs
                WHERE request_content LIKE ? OR response_content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (search_term, search_term, limit),
            ).fetchall()
        return [
            ConversationLogEntry(
                log_id=row["log_id"],
                request_id=row["request_id"],
                request_content=row["request_content"],
                response_content=row["response_content"],
                metadata=json.loads(row["metadata"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # --- Semantic Memory Methods (implements MemoryBackend interface) ---

    def store(self, record: MemoryRecord) -> MemoryRecord:
        """Store a memory record in semantic memory."""
        now = time.time()
        if record.record_id in ("", None):
            record_id = str(uuid.uuid4())
        else:
            record_id = record.record_id

        with sqlite3.connect(self.semantic_db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_memory
                (record_id, content, category, memory_type, importance, confidence,
                 source, evidence, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record.content,
                    record.metadata.get("category", "general"),
                    record.metadata.get("memory_type", "fact"),
                    record.metadata.get("importance", 5),
                    record.metadata.get("confidence", 0.7),
                    record.metadata.get("source", "user-stated"),
                    record.metadata.get("evidence", ""),
                    json.dumps({k: v for k, v in record.metadata.items()
                                if k not in {"category", "memory_type", "importance",
                                             "confidence", "source", "evidence"}}),
                    record.metadata.get("created_at", now),
                    now,
                ),
            )
        return MemoryRecord(
            key=record.key,
            content=record.content,
            record_id=record_id,
            metadata={**record.metadata, "record_id": record_id},
            created_at=record.metadata.get("created_at", now),
            updated_at=now,
        )

    def retrieve(self, record_id: str) -> MemoryRecord | None:
        """Retrieve a memory record by ID."""
        with sqlite3.connect(self.semantic_db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM semantic_memory WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if not row:
            return None
        metadata = json.loads(row["metadata"])
        metadata.update({
            "category": row["category"],
            "memory_type": row["memory_type"],
            "importance": row["importance"],
            "confidence": row["confidence"],
            "source": row["source"],
            "evidence": row["evidence"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
        return MemoryRecord(
            key=row["record_id"],
            content=row["content"],
            record_id=row["record_id"],
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update(
        self,
        record_id: str,
        content: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        """Update a memory record."""
        with sqlite3.connect(self.semantic_db) as conn:
            # Get existing
            row = conn.execute(
                "SELECT content, metadata FROM semantic_memory WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                return False

            old_content, old_metadata = row
            new_content = content if content is not None else old_content
            new_metadata = dict(json.loads(old_metadata))
            if metadata:
                new_metadata.update(metadata)

            now = time.time()
            conn.execute(
                """
                UPDATE semantic_memory
                SET content = ?, metadata = ?, updated_at = ?
                WHERE record_id = ?
                """,
                (new_content, json.dumps(new_metadata), now, record_id),
            )
            return True

    def delete(self, record_id: str) -> bool:
        """Delete a memory record."""
        with sqlite3.connect(self.semantic_db) as conn:
            cursor = conn.execute(
                "DELETE FROM semantic_memory WHERE record_id = ?",
                (record_id,),
            )
            return cursor.rowcount > 0

    def search(
        self,
        query: str,
        limit: int = 10,
        category: str | None = None,
        memory_type: str | None = None,
        min_importance: int = 1,
    ) -> MemorySearchResult:
        """Search semantic memory with optional filters."""
        search_term = f"%{query}%"
        params: list[Any] = [search_term, search_term, search_term]
        where_clauses = ["(content LIKE ? OR category LIKE ? OR memory_type LIKE ?)"]

        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if memory_type:
            where_clauses.append("memory_type = ?")
            params.append(memory_type)
        if min_importance > 1:
            where_clauses.append("importance >= ?")
            params.append(min_importance)

        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        with sqlite3.connect(self.semantic_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT * FROM semantic_memory
                WHERE {where_sql}
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        records = []
        for row in rows:
            metadata = json.loads(row["metadata"])
            metadata.update({
                "category": row["category"],
                "memory_type": row["memory_type"],
                "importance": row["importance"],
                "confidence": row["confidence"],
                "source": row["source"],
                "evidence": row["evidence"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
            records.append(
                MemoryRecord(
                    key=row["record_id"],
                    content=row["content"],
                    record_id=row["record_id"],
                    metadata=metadata,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        return MemorySearchResult(query=query, records=tuple(records), total=len(records))

    def clear(self) -> None:
        """Clear all memories (both databases)."""
        with sqlite3.connect(self.semantic_db) as conn:
            conn.execute("DELETE FROM semantic_memory")
        with sqlite3.connect(self.conversation_db) as conn:
            conn.execute("DELETE FROM conversation_logs")

    def metadata(self) -> Mapping[str, Any]:
        """Return store metadata."""
        with sqlite3.connect(self.semantic_db) as conn:
            semantic_count = conn.execute("SELECT COUNT(*) FROM semantic_memory").fetchone()[0]
        with sqlite3.connect(self.conversation_db) as conn:
            conversation_count = conn.execute("SELECT COUNT(*) FROM conversation_logs").fetchone()[0]
        return {
            "conversation_log_count": conversation_count,
            "semantic_memory_count": semantic_count,
            "conversation_db": str(self.conversation_db),
            "semantic_db": str(self.semantic_db),
        }