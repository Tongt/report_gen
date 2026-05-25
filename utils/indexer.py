from __future__ import annotations

from pathlib import Path

from config import KB_DIR
from utils.loader import list_knowledge_base_files, load_documents
from utils.splitter import split_documents
from utils.vector_store import ChromaKnowledgeBase


def _list_kb_files(kb_root: Path) -> list[Path]:
    return list_knowledge_base_files(base_dir=kb_root)


def list_saved_files(kb_root: Path | None = None) -> list[str]:
    root = KB_DIR if kb_root is None else kb_root
    return [path.name for path in _list_kb_files(root)]


def index_new_files(kb: ChromaKnowledgeBase, kb_root: Path | None = None) -> dict[str, int]:
    root = KB_DIR if kb_root is None else kb_root
    indexed_paths = set(kb.list_indexed_source_paths())
    candidates = [path for path in _list_kb_files(root) if str(path) not in indexed_paths]
    if not candidates:
        return {"new_files": 0, "parsed_files": 0, "chunks": 0}

    docs = load_documents(candidates)
    chunks = split_documents(docs)
    kb.upsert_chunks(chunks)
    return {"new_files": len(candidates), "parsed_files": len(docs), "chunks": len(chunks)}


def rebuild_all(kb: ChromaKnowledgeBase, kb_root: Path | None = None) -> dict[str, int]:
    root = KB_DIR if kb_root is None else kb_root
    kb.clear()
    candidates = _list_kb_files(root)
    if not candidates:
        return {"files": 0, "parsed_files": 0, "chunks": 0}

    docs = load_documents(candidates)
    chunks = split_documents(docs)
    kb.upsert_chunks(chunks)
    return {"files": len(candidates), "parsed_files": len(docs), "chunks": len(chunks)}


def delete_file(kb: ChromaKnowledgeBase, filename: str, kb_root: Path | None = None) -> bool:
    root = KB_DIR if kb_root is None else kb_root
    candidates = [path for path in _list_kb_files(root) if path.name == filename]
    if not candidates:
        return False
    path = candidates[0]
    path.unlink()
    kb.delete_by_source_path(str(path))
    return True
