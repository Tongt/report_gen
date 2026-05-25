from __future__ import annotations

import ssl
import time
import warnings
from typing import Any

import chromadb
import dashscope

from utils.splitter import TextChunk


class ChromaKnowledgeBase:
    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        api_key: str,
        embedding_model: str,
    ) -> None:
        self.embedding_model = embedding_model
        dashscope.api_key = api_key
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        if "LibreSSL" in ssl.OPENSSL_VERSION:
            warnings.warn(
                "Current Python ssl backend is LibreSSL. "
                "Please install dependencies with `urllib3<2` and prefer Python builds with OpenSSL for stability.",
                RuntimeWarning,
            )

    def count(self) -> int:
        return self.collection.count()

    @staticmethod
    def _batch_iter(items: list[str], batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def _embed_batch_once(self, batch: list[str]) -> list[list[float]] | None:
        response = dashscope.TextEmbedding.call(model=self.embedding_model, input=batch)
        if response.status_code != 200:
            message = getattr(response, "message", "Embedding request failed.")
            warnings.warn(
                f"Embedding batch failed, size={len(batch)}. Detail: {message}",
                RuntimeWarning,
            )
            return None
        output = response.output or {}
        items = output.get("embeddings", [])
        vectors = [item.get("embedding", []) for item in items]
        if len(vectors) != len(batch):
            warnings.warn(
                f"Embedding batch size mismatch, expected={len(batch)}, got={len(vectors)}.",
                RuntimeWarning,
            )
            return None
        return vectors

    def _embed_batch_with_retry(self, batch: list[str], max_retries: int = 3) -> list[list[float]] | None:
        for attempt in range(1, max_retries + 1):
            try:
                vectors = self._embed_batch_once(batch)
                if vectors is not None:
                    return vectors
            except Exception as exc:  # pragma: no cover - runtime guard
                warnings.warn(
                    f"Embedding batch exception, size={len(batch)}, attempt={attempt}. Detail: {exc}",
                    RuntimeWarning,
                )
            time.sleep(0.2 * attempt)
        return None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        all_vectors: list[list[float]] = []
        for batch in self._batch_iter(texts, 10):
            vectors = self._embed_batch_with_retry(batch)
            if vectors is None:
                # fallback: per-text retries to reduce total data loss
                for text in batch:
                    one = self._embed_batch_with_retry([text])
                    if one:
                        all_vectors.extend(one)
                    else:
                        warnings.warn("Embedding single text failed and was skipped.", RuntimeWarning)
                    time.sleep(0.2)
                continue
            all_vectors.extend(vectors)
            time.sleep(0.2)
        return all_vectors

    def upsert_chunks(self, chunks: list[TextChunk], batch_size: int = 16) -> None:
        if not chunks:
            return
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            valid_items: list[tuple[TextChunk, list[float]]] = []
            for sub_batch in self._batch_iter(batch, 10):
                texts = [item.content for item in sub_batch]
                vectors = self._embed_batch_with_retry(texts)
                if vectors is not None:
                    valid_items.extend(list(zip(sub_batch, vectors)))
                    time.sleep(0.2)
                    continue

                for item in sub_batch:
                    one = self._embed_batch_with_retry([item.content])
                    if one:
                        valid_items.append((item, one[0]))
                    else:
                        warnings.warn(
                            f"Skip one chunk due to embedding failure: {item.file_name}/{item.chunk_index}",
                            RuntimeWarning,
                        )
                    time.sleep(0.2)

            if not valid_items:
                warnings.warn("Skip upsert batch: no valid embedding vectors.", RuntimeWarning)
                continue

            self.collection.upsert(
                ids=[item.id for item, _ in valid_items],
                documents=[item.content for item, _ in valid_items],
                embeddings=[vector for _, vector in valid_items],
                metadatas=[
                    {
                        "file_name": item.file_name,
                        "source_path": item.source_path,
                        "chunk_index": item.chunk_index,
                    }
                    for item, _ in valid_items
                ],
            )

    def query_by_vector(
        self,
        vector: list[float],
        n_results: int = 6,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """使用已算好的查询向量检索 Chroma（不再调用 Embedding API）。"""
        query_kwargs: dict[str, Any] = {
            "query_embeddings": [vector],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where
        raw = self.collection.query(**query_kwargs)
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        rows: list[dict[str, Any]] = []
        for row_id, doc, metadata, distance in zip(ids, docs, metadatas, distances):
            rows.append(
                {
                    "id": row_id,
                    "content": doc,
                    "file_name": (metadata or {}).get("file_name", "未知来源"),
                    "source_path": (metadata or {}).get("source_path", ""),
                    "distance": distance,
                }
            )
        return rows

    def query(self, query_text: str, n_results: int = 6, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        vectors = self.embed_texts([query_text])
        if not vectors:
            warnings.warn("Query embedding failed; return empty search result.", RuntimeWarning)
            return []
        return self.query_by_vector(vectors[0], n_results=n_results, where=where)

    def list_indexed_files(self) -> list[str]:
        total = self.count()
        if total <= 0:
            return []
        raw = self.collection.get(include=["metadatas"], limit=total)
        metadatas = raw.get("metadatas", [])
        names = []
        seen = set()
        for metadata in metadatas:
            file_name = (metadata or {}).get("file_name")
            if file_name and file_name not in seen:
                seen.add(file_name)
                names.append(file_name)
        return sorted(names)

    def list_indexed_source_paths(self) -> list[str]:
        total = self.count()
        if total <= 0:
            return []
        raw = self.collection.get(include=["metadatas"], limit=total)
        metadatas = raw.get("metadatas", [])
        paths = []
        seen = set()
        for metadata in metadatas:
            source_path = (metadata or {}).get("source_path")
            if source_path and source_path not in seen:
                seen.add(source_path)
                paths.append(source_path)
        return sorted(paths)

    def delete_by_file_name(self, file_name: str) -> None:
        self.collection.delete(where={"file_name": file_name})

    def delete_by_source_path(self, source_path: str) -> None:
        self.collection.delete(where={"source_path": source_path})

    def clear(self) -> None:
        total = self.count()
        if total <= 0:
            return
        raw = self.collection.get(include=[], limit=total)
        ids = raw.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
