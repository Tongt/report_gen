from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import dashscope

from config import FIVE_DECISIONS, FIVE_LOOKS
from utils.retriever import collect_source_names


DECISION_GUIDANCE = {
    "定方向": "明确战略方向，说明与五看结论的对应关系。",
    "定目标": "给出阶段性目标，目标需可考核、可量化（可用定性+定量结合）。",
    "定技术": "提出关键技术路线和能力建设重点。",
    "定重大项目": "提出重大项目清单与优先级，说明落地路径。",
    "定重大举措": "提出组织、机制、资源配置、风险管控等配套举措。",
}


class QwenReportGenerator:
    def __init__(
        self,
        api_key: str,
        chat_model: str,
        enable_web_search: bool = False,
        search_keywords: str = "",
        strict_full_coverage: bool = False,
    ) -> None:
        dashscope.api_key = api_key
        self.chat_model = chat_model
        self.enable_web_search = enable_web_search
        self.search_keywords = search_keywords.strip()
        self.strict_full_coverage = strict_full_coverage

    def _is_multimodal_model(self) -> bool:
        model = self.chat_model.lower()
        return model.startswith("qwen3")

    @staticmethod
    def _extract_content(response) -> str:
        output = response.output or {}
        choices = output.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            return "\n".join(parts).strip()
        return ""

    @staticmethod
    def _extract_online_sources(response: Any) -> list[dict[str, str]]:
        output = getattr(response, "output", None) or {}
        rows: list[dict[str, str]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                url = node.get("url") or node.get("link") or node.get("source_url")
                title = node.get("title") or node.get("name") or node.get("source")
                if isinstance(url, str) and url.strip():
                    rows.append({"title": str(title or "外部公开资料"), "url": url.strip()})
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(output)
        uniq: list[dict[str, str]] = []
        seen = set()
        for item in rows:
            key = (item["title"], item["url"])
            if key not in seen:
                seen.add(key)
                uniq.append(item)
        return uniq

    @staticmethod
    def _extract_urls_from_text(text: str) -> list[dict[str, str]]:
        urls = re.findall(r"https?://[^\s\)\]】>]+", text or "")
        uniq: list[dict[str, str]] = []
        seen = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                uniq.append({"title": "外部公开资料链接", "url": url})
        return uniq

    def _chat(self, system_prompt: str, user_prompt: str) -> tuple[str, list[dict[str, str]]]:
        messages = [
            {"role": "system", "content": [{"text": system_prompt}]},
            {"role": "user", "content": [{"text": user_prompt}]},
        ]
        extra_kwargs: dict[str, Any] = {}
        if self.enable_web_search:
            extra_kwargs["enable_search"] = True
            extra_kwargs["search_options"] = {"forced_search": True}

        if self._is_multimodal_model():
            response = dashscope.MultiModalConversation.call(
                model=self.chat_model,
                messages=messages,
                temperature=0.2,
                **extra_kwargs,
            )
        else:
            response = dashscope.Generation.call(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                result_format="message",
                temperature=0.2,
                **extra_kwargs,
            )
        if response.status_code != 200:
            message = getattr(response, "message", "Generation request failed.")
            raise RuntimeError(f"Qwen generation failed: {message}")
        content = self._extract_content(response)
        online_sources = self._extract_online_sources(response)
        online_sources.extend(self._extract_urls_from_text(content))
        return content, online_sources

    @staticmethod
    def _render_context(records: list[dict], max_items: int = 4) -> str:
        snippets = []
        selected: list[dict] = []
        seen_files = set()
        for item in records:
            file_name = item.get("file_name", "")
            if file_name in seen_files:
                continue
            seen_files.add(file_name)
            selected.append(item)
            if len(selected) >= max_items:
                break
        if len(selected) < max_items:
            for item in records:
                if item in selected:
                    continue
                selected.append(item)
                if len(selected) >= max_items:
                    break

        for idx, item in enumerate(selected, start=1):
            snippets.append(f"[资料{idx}] 文件：{item['file_name']}\n{item['content'][:800]}")
        return "\n\n".join(snippets)

    @staticmethod
    def _section_template_outline(template_text: str, section_key: str) -> str:
        if not template_text.strip():
            return ""
        lines = template_text.splitlines()
        start_idx = -1
        for i, line in enumerate(lines):
            normalized = line.strip()
            if normalized.startswith("#") and section_key in normalized:
                start_idx = i
                break
        if start_idx < 0:
            return ""
        end_idx = len(lines)
        for j in range(start_idx + 1, len(lines)):
            normalized = lines[j].strip()
            if normalized.startswith("# ") and normalized != lines[start_idx].strip():
                end_idx = j
                break
        outline = "\n".join(lines[start_idx:end_idx]).strip()
        return outline

    def generate_five_looks(
        self,
        target_object: str,
        skill_rules_text: str,
        template_text: str,
        retrieved_by_look: dict[str, list[dict]],
    ) -> tuple[dict[str, str], dict[str, list[dict[str, str]]]]:
        system_prompt = (
            "你是央企战略规划顾问。请使用正式、公文风格。"
            "必须优先依据给定资料，不得编造来源。"
            "若启用联网信息，仅可作为补充参考；当本地资料与外部信息冲突时，必须以本地资料为准。"
            "skills 是规则，不是事实来源；template 是结构，不是事实来源。"
        )
        outputs: dict[str, str] = {}
        online_source_map: dict[str, list[dict[str, str]]] = {}
        for look in FIVE_LOOKS:
            look_records = retrieved_by_look.get(look, [])
            max_items = max(4, len({item.get("file_name", "") for item in look_records})) if self.strict_full_coverage else 4
            context = self._render_context(look_records, max_items=max_items)
            template_outline = self._section_template_outline(template_text, look)
            search_rule = (
                "请在末尾附“联网补充来源”并至少给出1个可访问URL（Markdown链接格式）。"
                if self.enable_web_search
                else "未启用联网搜索，不要输出“联网补充资料”或“联网补充来源”相关段落。"
            )
            user_prompt = f"""
【Skills规则】
{skill_rules_text or "未选择skills规则"}

【Template结构】
{template_text or "未使用模板"}

【当前章节模板骨架】
{template_outline or "未提供该章节专属骨架"}

【用户问题】
请围绕分析对象“{target_object}”完成“{look}”章节判断。

【当前章节】
{look}

【RAG资料片段（仅知识库事实）】
{context}

请完成“{look}”章节，要求：
1) 严格遵循模板骨架写完整正文，不要输出模板占位符，不要重复标题；
2) 语言保持央企战略规划、公文风格；
3) 事实依据仅来自给定RAG资料和用户输入；
4) 如启用联网搜索，请围绕“{target_object} {look} {self.search_keywords}”检索补充；
5) {search_rule}
"""
            text, online_sources = self._chat(system_prompt, user_prompt)
            outputs[look] = text
            online_source_map[look] = online_sources
        return outputs, online_source_map

    def generate_five_decisions(
        self,
        target_object: str,
        skill_rules_text: str,
        template_text: str,
        look_analysis: dict[str, str],
        retrieved_by_look: dict[str, list[dict]] | None = None,
    ) -> tuple[dict[str, str], dict[str, list[dict[str, str]]]]:
        system_prompt = (
            "你是央企战略规划顾问。请使用正式、公文风格。"
            "五定内容必须回应五看的结论，形成对应关系。"
            "当本地资料与外部信息冲突时，必须以本地资料结论为准。"
            "skills 是规则，不是事实来源；template 是结构，不是事实来源。"
        )
        look_text = "\n\n".join([f"{k}：{v}" for k, v in look_analysis.items()])
        outputs: dict[str, str] = {}
        online_source_map: dict[str, list[dict[str, str]]] = {}
        full_context = ""
        if self.strict_full_coverage and retrieved_by_look:
            merged = []
            seen_ids = set()
            for look in FIVE_LOOKS:
                for item in retrieved_by_look.get(look, []):
                    row_id = item.get("id") or f"{item.get('file_name')}::{item.get('distance')}"
                    if row_id in seen_ids:
                        continue
                    seen_ids.add(row_id)
                    merged.append(item)
            # 全文覆盖模式下，给五定补充跨章节资料上下文
            full_context = self._render_context(merged, max_items=max(8, len({x.get('file_name', '') for x in merged})))
        for decision in FIVE_DECISIONS:
            template_outline = self._section_template_outline(template_text, decision)
            search_rule = (
                "请在末尾附“联网补充来源”并至少给出1个可访问URL（Markdown链接格式）。"
                if self.enable_web_search
                else "未启用联网搜索，不要输出“联网补充资料”或“联网补充来源”相关段落。"
            )
            user_prompt = f"""
【Skills规则】
{skill_rules_text or "未选择skills规则"}

【Template结构】
{template_text or "未使用模板"}

【当前章节模板骨架】
{template_outline or "未提供该章节专属骨架"}

【用户问题】
请围绕分析对象“{target_object}”给出“{decision}”章节。

【五看结论（来自本地资料分析）】
{look_text}

【补充资料上下文（全文覆盖）】
{full_context or "未启用全文覆盖模式"}

【当前章节】
{decision}

【章节要求】
{DECISION_GUIDANCE[decision]}

请输出“{decision}”章节，要求：
1) 严格遵循模板骨架写完整正文，不要输出模板占位符，不要重复标题；
2) 语言精炼，不要输出额外小标题；
3) 如启用联网搜索，请围绕“{target_object} {decision} {self.search_keywords}”检索补充；
4) {search_rule}
"""
            text, online_sources = self._chat(system_prompt, user_prompt)
            outputs[decision] = text
            online_source_map[decision] = online_sources
        return outputs, online_source_map


def build_markdown_report(
    target_object: str,
    five_look_text: dict[str, str],
    five_decision_text: dict[str, str],
    retrieved_by_look: dict[str, list[dict]],
    section_online_sources: dict[str, list[dict[str, str]]],
    enable_web_search: bool,
) -> str:
    sections: list[str] = []
    sections.append(f"# “五看五定”分析报告（{target_object}）")
    sections.append(f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")

    section_bodies: dict[str, str] = {}

    for look in FIVE_LOOKS:
        sources = collect_source_names(retrieved_by_look.get(look, []))
        source_line = "、".join(sources) if sources else "无"
        section_bodies[look] = f"{five_look_text.get(look, '暂无内容')}\n\n**本地资料来源**：{source_line}"
        if enable_web_search:
            online_rows = section_online_sources.get(look, [])
            online_line = "；".join(
                [f"[{row.get('title', '外部公开资料')}]({row.get('url', '')})" for row in online_rows if row.get("url")]
            ) or "无"
            section_bodies[look] += f"\n\n**联网补充来源**：{online_line}"

    all_sources = []
    for look in FIVE_LOOKS:
        all_sources.extend(collect_source_names(retrieved_by_look.get(look, [])))
    unique_sources = []
    seen = set()
    for src in all_sources:
        if src not in seen:
            seen.add(src)
            unique_sources.append(src)
    decision_source_line = "、".join(unique_sources) if unique_sources else "无"

    for decision in FIVE_DECISIONS:
        section_bodies[decision] = f"{five_decision_text.get(decision, '暂无内容')}\n\n**本地资料来源**：{decision_source_line}"
        if enable_web_search:
            online_rows = section_online_sources.get(decision, [])
            online_line = "；".join(
                [f"[{row.get('title', '外部公开资料')}]({row.get('url', '')})" for row in online_rows if row.get("url")]
            ) or "无"
            section_bodies[decision] += f"\n\n**联网补充来源**：{online_line}"

    for key in list(FIVE_LOOKS) + list(FIVE_DECISIONS):
        sections.append(f"## {key}\n{section_bodies.get(key, '暂无内容')}")

    local_all = []
    for look in FIVE_LOOKS:
        local_all.extend(collect_source_names(retrieved_by_look.get(look, [])))
    local_uniq = []
    local_seen = set()
    for name in local_all:
        if name not in local_seen:
            local_seen.add(name)
            local_uniq.append(name)

    online_all = []
    for key in list(FIVE_LOOKS) + list(FIVE_DECISIONS):
        online_all.extend(section_online_sources.get(key, []))
    online_uniq = []
    online_seen = set()
    for row in online_all:
        title = row.get("title", "外部公开资料")
        url = row.get("url", "")
        if not url:
            continue
        key = (title, url)
        if key not in online_seen:
            online_seen.add(key)
            online_uniq.append(f"- [{title}]({url})")

    sections.append("## 资料来源说明")
    sections.append("外部资料仅作补充参考；若与本地资料冲突，以本地资料结论为准。")
    sections.append("### 本地资料来源\n" + ("\n".join([f"- {name}" for name in local_uniq]) if local_uniq else "- 无"))
    if enable_web_search:
        sections.append("### 联网补充资料来源\n" + ("\n".join(online_uniq) if online_uniq else "- 无"))

    return "\n\n".join(sections).strip() + "\n"


def clean_generated_report(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"\{\{.*?\}\}", "", cleaned, flags=re.DOTALL)

    lines = cleaned.splitlines()
    deduped: list[str] = []
    prev_header = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if stripped == prev_header:
                continue
            prev_header = stripped
        elif stripped:
            prev_header = ""
        deduped.append(line)

    kept: list[str] = []
    for line in deduped:
        stripped = line.strip()
        if stripped.startswith("**资料来源**：") and stripped.replace("**资料来源**：", "").strip() == "":
            continue
        if stripped.startswith("**本地资料来源**：") and stripped.replace("**本地资料来源**：", "").strip() == "":
            continue
        if stripped.startswith("**联网补充来源**：") and stripped.replace("**联网补充来源**：", "").strip() == "":
            continue
        kept.append(line)

    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"
    if "{{" in cleaned or "}}" in cleaned:
        raise ValueError("模板渲染失败：报告仍包含未替换占位符。")
    return cleaned
