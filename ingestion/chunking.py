"""Phase 3: Section-aware, token-aware chunking for processed documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to every chunk."""

    chunk_id: str
    source_url: str
    scheme_name: str
    source_type: str
    section_header: str
    crawled_at: str
    content_hash: str  # Hash of original full document
    chunk_index: int
    start_line: int
    end_line: int
    chunk_content_hash: str  # Hash of chunk content for deduplication


@dataclass
class Chunk:
    """A single chunk with metadata and content."""

    metadata: ChunkMetadata
    content: str

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            "metadata": {
                "chunk_id": self.metadata.chunk_id,
                "source_url": self.metadata.source_url,
                "scheme_name": self.metadata.scheme_name,
                "source_type": self.metadata.source_type,
                "section_header": self.metadata.section_header,
                "crawled_at": self.metadata.crawled_at,
                "content_hash": self.metadata.content_hash,
                "chunk_index": self.metadata.chunk_index,
                "start_line": self.metadata.start_line,
                "end_line": self.metadata.end_line,
                "chunk_content_hash": self.metadata.chunk_content_hash,
            },
            "content": self.content,
        }


class TokenCounter:
    """Count tokens using tiktoken with GPT-3.5 encoding."""

    def __init__(self):
        try:
            import tiktoken

            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except ImportError:
            raise ImportError(
                "tiktoken is required for token counting. "
                "Install with: pip install tiktoken"
            )

    def count(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))


class ChunkingSplitter:
    """Split text into line-safe chunks respecting token bounds."""

    def __init__(self, token_counter: Optional[TokenCounter] = None):
        self.token_counter = token_counter or TokenCounter()

    def split_by_lines(
        self,
        text: str,
        target_tokens: int = 250,
        overlap_tokens: int = 50,
        is_table_dense: bool = False,
    ) -> list[tuple[str, int, int]]:
        """
        Split text into chunks by complete lines.

        Args:
            text: Text to split
            target_tokens: Target chunk size in tokens
            overlap_tokens: Overlap size in tokens
            is_table_dense: If True, use tighter bounds for table sections

        Returns:
            List of (chunk_content, start_line, end_line) tuples
        """
        if is_table_dense:
            target_tokens = min(150, target_tokens)
            overlap_tokens = min(30, overlap_tokens)

        lines = text.split("\n")
        chunks = []
        i = 0

        while i < len(lines):
            chunk_lines = []
            chunk_tokens = 0
            start_line = i

            # Accumulate lines until we hit target tokens
            while i < len(lines) and chunk_tokens < target_tokens:
                line = lines[i]
                line_tokens = self.token_counter.count(line)

                # Add line to chunk
                chunk_lines.append(line)
                chunk_tokens += line_tokens
                i += 1

            if not chunk_lines:
                # Single line exceeded target tokens, take it anyway
                chunk_lines = [lines[start_line]]
                i = start_line + 1

            end_line = i - 1
            chunk_content = "\n".join(chunk_lines)

            if chunk_content.strip():
                chunks.append((chunk_content, start_line, end_line))

            # Backtrack for overlap if not at end
            if i < len(lines):
                overlap_lines = 0
                overlap_tokens_count = 0
                for j in range(i - 1, start_line - 1, -1):
                    overlap_lines += 1
                    overlap_tokens_count += self.token_counter.count(lines[j])
                    if overlap_tokens_count >= overlap_tokens:
                        break
                i = max(start_line + 1, i - overlap_lines)

        return chunks


class SectionAwareChunker:
    """Chunk documents with awareness of section headers and table-dense regions."""

    def __init__(self, token_counter: Optional[TokenCounter] = None):
        self.token_counter = token_counter or TokenCounter()
        self.splitter = ChunkingSplitter(self.token_counter)

    def _detect_table_dense_section(self, text: str) -> bool:
        """
        Detect if a section is table-dense (holdings, returns, etc.).
        Table-dense sections have many lines with consistent column structure.
        """
        lines = text.split("\n")[:30]  # Check first 30 lines
        if not lines:
            return False

        # Count lines that look like table rows (multiple tabs/spaces + values)
        table_like_count = 0
        for line in lines:
            if re.search(r"\t|\s{2,}", line) and re.search(r"[\d,%]", line):
                table_like_count += 1

        return table_like_count > len(lines) * 0.3  # >30% table-like

    def chunk(
        self,
        text: str,
        source_url: str,
        scheme_name: str,
        source_type: str,
        crawled_at: str,
        content_hash: str,
    ) -> list[Chunk]:
        """
        Chunk document by sections marked with "##" headers.

        Args:
            text: Normalized text with "##" section markers
            source_url: URL this came from
            scheme_name: Scheme name (e.g., "HDFC Equity Fund")
            source_type: Type of source (e.g., "scheme_page")
            crawled_at: ISO datetime of crawl
            content_hash: Hash of original full document

        Returns:
            List of Chunk objects with metadata
        """
        chunks = []
        chunk_index = 0

        # Split by section headers "##"
        section_pattern = r"^## "
        lines = text.split("\n")
        sections = []
        current_section_header = "General"
        current_section_lines = []
        current_section_start_line = 0

        for line_idx, line in enumerate(lines):
            if re.match(section_pattern, line):
                # Save previous section if it has content
                if current_section_lines:
                    section_text = "\n".join(current_section_lines)
                    sections.append(
                        (
                            current_section_header,
                            section_text,
                            current_section_start_line,
                            line_idx - 1,
                        )
                    )

                # Start new section
                current_section_header = line[3:].strip()  # Remove "## "
                current_section_lines = []
                current_section_start_line = line_idx + 1
            else:
                current_section_lines.append(line)

        # Don't forget the last section
        if current_section_lines:
            section_text = "\n".join(current_section_lines)
            sections.append(
                (
                    current_section_header,
                    section_text,
                    current_section_start_line,
                    len(lines) - 1,
                )
            )

        # Chunk each section
        for section_header, section_text, section_start_line, section_end_line in sections:
            if not section_text.strip():
                continue

            is_table_dense = self._detect_table_dense_section(section_text)
            target_tokens = 150 if is_table_dense else 270
            overlap_tokens = 30 if is_table_dense else 50

            # Split section into sub-chunks
            sub_chunks = self.splitter.split_by_lines(
                section_text,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
                is_table_dense=is_table_dense,
            )

            for chunk_content, start_line_offset, end_line_offset in sub_chunks:
                # Compute hash of chunk content
                chunk_content_hash = hashlib.sha256(
                    chunk_content.encode()
                ).hexdigest()[:16]

                # Create chunk ID
                chunk_id = f"{content_hash[:8]}_chunk_{chunk_index}"

                metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    source_url=source_url,
                    scheme_name=scheme_name,
                    source_type=source_type,
                    section_header=section_header,
                    crawled_at=crawled_at,
                    content_hash=content_hash,
                    chunk_index=chunk_index,
                    start_line=section_start_line + start_line_offset,
                    end_line=section_start_line + end_line_offset,
                    chunk_content_hash=chunk_content_hash,
                )

                chunk = Chunk(metadata=metadata, content=chunk_content)
                chunks.append(chunk)
                chunk_index += 1

        return chunks
