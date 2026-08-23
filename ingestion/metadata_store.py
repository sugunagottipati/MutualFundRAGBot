"""Phase 3: SQLite metadata store for chunk traceability and filtering."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ingestion.chunking import Chunk, ChunkMetadata


class ChunkMetadataStore:
    """SQLite store for chunk metadata with filter and trace capabilities."""

    def __init__(self, db_path: Path | str = "data/processed/app.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Main chunks table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                scheme_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                section_header TEXT NOT NULL,
                crawled_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                chunk_content_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Deduplication tracking (for identifying repeated chunks across versions)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_dedup (
                chunk_content_hash TEXT PRIMARY KEY,
                chunk_id TEXT NOT NULL,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seen_count INTEGER DEFAULT 1,
                FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
            )
            """
        )

        # Index for fast lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_source_url ON chunks(source_url)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scheme_name ON chunks(scheme_name)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_section_header ON chunks(section_header)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_content_hash ON chunks(content_hash)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chunk_content_hash ON chunks(chunk_content_hash)
            """
        )

        conn.commit()
        conn.close()

    def insert_chunks(self, chunks: list[Chunk]) -> int:
        """
        Insert chunks into store.

        Args:
            chunks: List of Chunk objects

        Returns:
            Number of chunks inserted
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        inserted = 0
        for chunk in chunks:
            try:
                meta = chunk.metadata
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO chunks (
                        chunk_id, source_url, scheme_name, source_type,
                        section_header, crawled_at, content_hash, chunk_index,
                        start_line, end_line, chunk_content_hash, content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meta.chunk_id,
                        meta.source_url,
                        meta.scheme_name,
                        meta.source_type,
                        meta.section_header,
                        meta.crawled_at,
                        meta.content_hash,
                        meta.chunk_index,
                        meta.start_line,
                        meta.end_line,
                        meta.chunk_content_hash,
                        chunk.content,
                    ),
                )

                # Track deduplication
                cursor.execute(
                    """
                    INSERT INTO chunk_dedup (chunk_content_hash, chunk_id, seen_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(chunk_content_hash) DO UPDATE SET
                        seen_count = seen_count + 1
                    """,
                    (meta.chunk_content_hash, meta.chunk_id),
                )

                inserted += 1
            except Exception as e:
                print(f"Error inserting chunk {chunk.metadata.chunk_id}: {e}")

        conn.commit()
        conn.close()
        return inserted

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Retrieve a chunk by ID."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata = ChunkMetadata(
            chunk_id=row["chunk_id"],
            source_url=row["source_url"],
            scheme_name=row["scheme_name"],
            source_type=row["source_type"],
            section_header=row["section_header"],
            crawled_at=row["crawled_at"],
            content_hash=row["content_hash"],
            chunk_index=row["chunk_index"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            chunk_content_hash=row["chunk_content_hash"],
        )
        return Chunk(metadata=metadata, content=row["content"])

    def get_chunks_by_source_url(self, source_url: str) -> list[Chunk]:
        """Get all chunks from a specific source URL."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM chunks WHERE source_url = ? ORDER BY chunk_index", (source_url,))
        rows = cursor.fetchall()
        conn.close()

        chunks = []
        for row in rows:
            metadata = ChunkMetadata(
                chunk_id=row["chunk_id"],
                source_url=row["source_url"],
                scheme_name=row["scheme_name"],
                source_type=row["source_type"],
                section_header=row["section_header"],
                crawled_at=row["crawled_at"],
                content_hash=row["content_hash"],
                chunk_index=row["chunk_index"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                chunk_content_hash=row["chunk_content_hash"],
            )
            chunks.append(Chunk(metadata=metadata, content=row["content"]))

        return chunks

    def get_chunks_by_scheme_name(self, scheme_name: str) -> list[Chunk]:
        """Get all chunks for a specific scheme."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM chunks WHERE scheme_name = ? ORDER BY chunk_index", (scheme_name,))
        rows = cursor.fetchall()
        conn.close()

        chunks = []
        for row in rows:
            metadata = ChunkMetadata(
                chunk_id=row["chunk_id"],
                source_url=row["source_url"],
                scheme_name=row["scheme_name"],
                source_type=row["source_type"],
                section_header=row["section_header"],
                crawled_at=row["crawled_at"],
                content_hash=row["content_hash"],
                chunk_index=row["chunk_index"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                chunk_content_hash=row["chunk_content_hash"],
            )
            chunks.append(Chunk(metadata=metadata, content=row["content"]))

        return chunks

    def get_chunks_by_section_header(self, section_header: str) -> list[Chunk]:
        """Get all chunks from a specific section across all documents."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM chunks WHERE section_header = ? ORDER BY source_url, chunk_index",
            (section_header,),
        )
        rows = cursor.fetchall()
        conn.close()

        chunks = []
        for row in rows:
            metadata = ChunkMetadata(
                chunk_id=row["chunk_id"],
                source_url=row["source_url"],
                scheme_name=row["scheme_name"],
                source_type=row["source_type"],
                section_header=row["section_header"],
                crawled_at=row["crawled_at"],
                content_hash=row["content_hash"],
                chunk_index=row["chunk_index"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                chunk_content_hash=row["chunk_content_hash"],
            )
            chunks.append(Chunk(metadata=metadata, content=row["content"]))

        return chunks

    def get_duplicate_chunks(self, min_seen_count: int = 2) -> list[dict]:
        """
        Get chunks that appear multiple times (across versions).

        Args:
            min_seen_count: Minimum times a chunk must appear

        Returns:
            List of dedup records
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT d.chunk_content_hash, d.chunk_id, d.seen_count, c.source_url, c.section_header
            FROM chunk_dedup d
            JOIN chunks c ON d.chunk_id = c.chunk_id
            WHERE d.seen_count >= ?
            ORDER BY d.seen_count DESC
            """,
            (min_seen_count,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def clear_chunks_by_source_url(self, source_url: str) -> int:
        """Delete all chunks for a source (for re-ingestion)."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM chunks WHERE source_url = ?", (source_url,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()
        return deleted

    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total_chunks FROM chunks")
        total_chunks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT source_url) as sources FROM chunks")
        total_sources = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT scheme_name) as schemes FROM chunks")
        total_schemes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT section_header) as sections FROM chunks")
        total_sections = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) as duped FROM chunk_dedup WHERE seen_count > 1"
        )
        duplicate_records = cursor.fetchone()[0]

        conn.close()

        return {
            "total_chunks": total_chunks,
            "total_sources": total_sources,
            "total_schemes": total_schemes,
            "total_sections": total_sections,
            "duplicate_records": duplicate_records,
        }
