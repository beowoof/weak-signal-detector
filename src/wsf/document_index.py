"""Content-addressed passage index for admitted documents.

Only versioned research documents are stored. Search snippets never enter the
index. Each passage is an exact character slice of its parent document so
quotes remain checkable against the review bundle.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from wsf.connectors.http import HttpTransport, UrllibTransport
from wsf.env import load_project_env
from wsf.evidence_bundle import canonical

SCHEMA = "document_passage_index_v1"
MAX_PASSAGE = 1200
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


EmbedFn = Callable[[list[str]], list[list[float]]]


def chunk_document(text: str) -> list[dict[str, Any]]:
    """Split admitted text into exact original-string slices."""
    if not isinstance(text, str) or not text.strip():
        return []
    source = text.replace("\r\n", "\n")
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r".+?(?:\n\s*\n|$)", source, flags=re.S):
        start, end = match.start(), match.end()
        while end > start and source[end - 1] in "\n\r":
            end -= 1
        if source[start:end].strip():
            spans.append((start, end))
    if not spans:
        spans = [(0, len(source))]
    chunks: list[dict[str, Any]] = []
    buf_start, buf_end = spans[0]
    for start, end in spans:
        if buf_end == buf_start:
            buf_start, buf_end = start, end
            continue
        candidate = source[buf_start:end]
        if len(candidate) <= MAX_PASSAGE:
            buf_end = end
            continue
        chunks.extend(_windows(source, buf_start, buf_end))
        buf_start, buf_end = start, end
    chunks.extend(_windows(source, buf_start, buf_end))
    return [row for row in chunks if row["text"].strip()]


def _windows(source: str, start: int, end: int) -> list[dict[str, Any]]:
    length = end - start
    if length <= MAX_PASSAGE:
        return [{"start": start, "end": end, "text": source[start:end]}]
    step = MAX_PASSAGE - 120
    rows = []
    cursor = start
    while cursor < end:
        stop = min(cursor + MAX_PASSAGE, end)
        rows.append({"start": cursor, "end": stop, "text": source[cursor:stop]})
        if stop >= end:
            break
        cursor += step
    return rows


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)


def _tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9]{3,}", text.casefold())}


def lexical_score(query: str, passage: str) -> float:
    q, p = _tokens(query), _tokens(passage)
    if not q or not p:
        return 0.0
    return len(q & p) / len(q)


def embed_model_name(project_root: Path | None = None) -> str:
    if project_root is not None:
        load_project_env(project_root)
    return (os.environ.get("OLLAMA_EMBED_MODEL") or "mxbai-embed-large").strip()


def ollama_embed(
    texts: list[str],
    *,
    project_root: Path,
    transport: HttpTransport | None = None,
) -> list[list[float]]:
    load_project_env(project_root)
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip().rstrip("/")
    model = embed_model_name()
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) server base URL")
    client = transport or UrllibTransport()
    response = client.post(
        base + "/api/embed",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"model": model, "input": texts}).encode(),
        timeout=120,
    )
    if response.status == 404:
        vectors = []
        for text in texts:
            one = client.post(
                base + "/api/embeddings",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"model": model, "prompt": text}).encode(),
                timeout=120,
            )
            if one.status != 200:
                raise ValueError(f"Ollama embeddings HTTP {one.status}")
            payload = json.loads(one.body)
            vector = payload.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise ValueError("Ollama embeddings returned no vector")
            vectors.append([float(v) for v in vector])
        return vectors
    if response.status != 200:
        raise ValueError(f"Ollama embed HTTP {response.status}")
    payload = json.loads(response.body)
    rows = payload.get("embeddings")
    if not isinstance(rows, list) or len(rows) != len(texts):
        raise ValueError("Ollama embed returned the wrong number of vectors")
    return [[float(v) for v in row] for row in rows]


class DocumentIndex:
    def __init__(self, project_root: Path, embed: EmbedFn | None = None):
        self.root = project_root / "scenarios" / ".document_index"
        self.embed = embed

    def _path(self, content_sha256: str) -> Path:
        return self.root / "documents" / f"{content_sha256}.json"

    def upsert(self, documents: list[dict[str, Any]]) -> dict[str, int]:
        """Index admitted documents. Identical content hashes are reused."""
        counts: dict[str, int] = {}
        for row in documents:
            text = row.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            sha = hashlib.sha256(text.encode()).hexdigest()
            path = self._path(sha)
            if path.exists():
                stored = json.loads(path.read_text())
                if stored.get("text") == text and stored.get("passages"):
                    counts[sha] = len(stored["passages"])
                    continue
            chunks = chunk_document(text)
            vectors: list[list[float]] | None = None
            method = "lexical"
            if self.embed and chunks:
                try:
                    vectors = self.embed([chunk["text"] for chunk in chunks])
                    if len(vectors) == len(chunks):
                        method = "embedding"
                    else:
                        vectors = None
                except (OSError, ValueError, TypeError, KeyError):
                    vectors = None
            passages = []
            for index, chunk in enumerate(chunks):
                if text[chunk["start"] : chunk["end"]] != chunk["text"]:
                    raise ValueError("Passage is not an exact slice of the admitted document")
                passages.append(
                    {
                        "index": index,
                        "start": chunk["start"],
                        "end": chunk["end"],
                        "text": chunk["text"],
                        "embedding": vectors[index] if vectors else None,
                    }
                )
            record = {
                "schema_id": SCHEMA,
                "content_sha256": sha,
                "url": row.get("url"),
                "archive_url": row.get("archive_url"),
                "version_at": row.get("version_at"),
                "source_tier": row.get("source_tier"),
                "requirement_id": row.get("requirement_id"),
                "originating_source": row.get("originating_source"),
                "text": text,
                "embedding_method": method,
                "passages": passages,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(canonical(record) + "\n")
            tmp.replace(path)
            counts[sha] = len(passages)
        return counts

    def query(self, queries: list[str], *, limit: int = 12) -> list[dict[str, Any]]:
        queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        if not queries or limit < 1:
            return []
        documents = []
        folder = self.root / "documents"
        if folder.is_dir():
            for path in folder.glob("*.json"):
                documents.append(json.loads(path.read_text()))
        if not documents:
            return []
        query_vectors = None
        if self.embed:
            try:
                query_vectors = self.embed([QUERY_PREFIX + q for q in queries])
            except (OSError, ValueError, TypeError, KeyError):
                query_vectors = None
        scored: list[tuple[float, dict[str, Any]]] = []
        for document in documents:
            for passage in document.get("passages") or []:
                lexical = max(lexical_score(query, passage["text"]) for query in queries)
                semantic = 0.0
                embedding = passage.get("embedding")
                if query_vectors and isinstance(embedding, list):
                    semantic = max(_cosine(vector, embedding) for vector in query_vectors)
                score = semantic if semantic else lexical
                if score <= 0:
                    continue
                scored.append(
                    (
                        score,
                        {
                            "content_sha256": document["content_sha256"],
                            "url": document.get("url"),
                            "archive_url": document.get("archive_url"),
                            "version_at": document.get("version_at"),
                            "source_tier": document.get("source_tier"),
                            "requirement_id": document.get("requirement_id"),
                            "originating_source": document.get("originating_source"),
                            "start": passage["start"],
                            "end": passage["end"],
                            "text": passage["text"],
                            "score": round(score, 6),
                            "retrieval": "embedding" if semantic else "lexical",
                        },
                    )
                )
        scored.sort(key=lambda row: (-row[0], 0 if row[1].get("source_tier") == "preferred" else 1))
        seen: set[tuple[str, int]] = set()
        selected = []
        for _, row in scored:
            key = (row["content_sha256"], row["start"])
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
            if len(selected) >= limit:
                break
        return selected


def retrieval_queries(packet, research: dict) -> list[str]:
    queries = []
    product = getattr(packet, "product", None)
    if product is not None:
        if getattr(product, "headline", None):
            queries.append(product.headline)
        if getattr(product, "geographic_frame", None):
            queries.append(product.geographic_frame)
        for requirement in product.collection or []:
            title = requirement.get("title")
            why = requirement.get("why")
            queries.append(" ".join(part for part in (title, why) if part))
    for outcome in research.get("collection_outcomes") or []:
        question = outcome.get("question") or outcome.get("purpose")
        if question:
            queries.append(str(question))
    return queries
