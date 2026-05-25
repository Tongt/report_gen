from __future__ import annotations

from config import FIVE_LOOKS
from utils.vector_store import ChromaKnowledgeBase


LOOK_QUERY_HINTS = {
    "看宏观": "宏观经济、政策导向、双碳目标、能源转型、区域政策环境",
    "看行业": "行业规模、增长趋势、产业链、行业痛点、技术路线",
    "看客户": "客户类型、客户需求、采购偏好、决策链条、典型客户案例",
    "看竞争": "竞争格局、主要对手、差异化、替代方案、进入壁垒",
    "看自己": "自身能力、资源禀赋、组织机制、短板约束、历史基础",
}


def retrieve_for_five_looks(
    kb: ChromaKnowledgeBase,
    target_object: str,
    n_results: int = 6,
    strict_full_coverage: bool = False,
) -> dict[str, list[dict]]:
    output: dict[str, list[dict]] = {}
    indexed_files = kb.list_indexed_files()
    for look in FIVE_LOOKS:
        query = f"围绕{target_object}，重点检索：{look}。请关注：{LOOK_QUERY_HINTS[look]}"
        # 同一「看」内全局检索与按文件过滤共用一次 query 向量，避免对每份文件重复调用 Embedding API
        query_vecs = kb.embed_texts([query])
        if not query_vecs:
            output[look] = []
            continue
        qemb = query_vecs[0]

        global_rows = kb.query_by_vector(qemb, n_results=max(n_results, 12))
        coverage_rows: list[dict] = []
        for file_name in indexed_files:
            per_file = kb.query_by_vector(qemb, n_results=1, where={"file_name": file_name})
            if per_file:
                coverage_rows.extend(per_file)

        merged = []
        seen = set()
        base_rows = coverage_rows if strict_full_coverage else (coverage_rows + global_rows)
        for row in base_rows:
            row_id = row.get("id") or f"{row.get('file_name')}::{row.get('distance')}"
            if row_id in seen:
                continue
            seen.add(row_id)
            merged.append(row)
        if strict_full_coverage and global_rows:
            # 严格覆盖下仍补充少量全局高相似片段，提升信息密度
            extra = []
            for row in global_rows:
                row_id = row.get("id") or f"{row.get('file_name')}::{row.get('distance')}"
                if row_id in seen:
                    continue
                extra.append(row)
                if len(extra) >= 5:
                    break
            merged.extend(extra)
        output[look] = merged
    return output


def collect_source_names(records: list[dict]) -> list[str]:
    names = []
    seen = set()
    for item in records:
        name = item.get("file_name", "未知来源")
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names
