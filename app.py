from __future__ import annotations

from datetime import datetime
from pathlib import Path

import dashscope
import streamlit as st

from config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    OUTPUTS_DIR,
    RAW_UPLOADS_DIR,
    SKILLS_DIR,
    ensure_dirs,
    load_api_key,
    mask_api_key,
    save_user_api_key,
    load_settings,
)
from utils.indexer import delete_file, index_new_files, list_saved_files, rebuild_all
from utils.loader import (
    list_knowledge_base_files,
    load_skills,
    load_templates,
    save_uploaded_files,
)
from utils.report_generator import QwenReportGenerator, build_markdown_report, clean_generated_report
from utils.retriever import retrieve_for_five_looks
from utils.vector_store import ChromaKnowledgeBase


def _skill_file_path() -> Path:
    return SKILLS_DIR / "五看五定.skill.md"


def _load_skill_text() -> str:
    skill_path = _skill_file_path()
    if not skill_path.exists():
        raise FileNotFoundError(f"未找到方法论文件：{skill_path}")
    return skill_path.read_text(encoding="utf-8")


def _init_state() -> None:
    if "kb" not in st.session_state:
        st.session_state.kb = None
    if "report_markdown" not in st.session_state:
        st.session_state.report_markdown = ""
    if "last_output_path" not in st.session_state:
        st.session_state.last_output_path = ""
    if "bootstrap_done" not in st.session_state:
        st.session_state.bootstrap_done = False


def _test_api_key(api_key: str) -> tuple[bool, str]:
    dashscope.api_key = api_key
    try:
        response = dashscope.Generation.call(
            model="qwen-plus",
            messages=[{"role": "user", "content": "请回复：连接成功"}],
            result_format="message",
            temperature=0,
        )
        if response.status_code == 200:
            return True, "API Key 可用"
        message = getattr(response, "message", "请求失败")
        return False, f"API Key 无效，请检查是否复制完整。详情：{message}"
    except Exception as exc:
        return False, f"API Key 无效，请检查是否复制完整。详情：{exc}"


def _build_selected_skills_text(selected_skill_names: list[str], skill_map: dict[str, str]) -> str:
    sections = []
    for name in selected_skill_names:
        text = skill_map.get(name, "").strip()
        if text:
            sections.append(f"### {name}\n{text}")
    return "\n\n".join(sections).strip()


def _build_kb(api_key: str) -> ChromaKnowledgeBase:
    settings = load_settings()
    return ChromaKnowledgeBase(
        persist_dir=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
        api_key=api_key,
        embedding_model=settings["embedding_model"],
    )


def _save_report(content: str) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS_DIR / f"五看五定报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path


ensure_dirs()
st.set_page_config(page_title="五看五定智能体", layout="centered")
st.title("五看五定智能体（MVP）")
st.caption("知识库资料（事实）+ Skills（规则）+ 模板（结构） -> 五看五定报告")

_init_state()

settings = load_settings()
effective_api_key = load_api_key().strip()

if not effective_api_key:
    st.warning("首次使用，请填写 Qwen API Key")
    input_key = st.text_input("请输入 DashScope API Key", type="password", value="")
    col_save, col_test = st.columns(2)
    if col_save.button("保存 API Key", use_container_width=True):
        if not input_key.strip():
            st.error("API Key 不能为空。")
        else:
            save_user_api_key(input_key.strip())
            st.success("API Key 已保存，下次启动自动读取。")
            st.rerun()
    if col_test.button("测试 API Key 是否可用", use_container_width=True):
        if not input_key.strip():
            st.error("请先输入 API Key。")
        else:
            ok, message = _test_api_key(input_key.strip())
            if ok:
                st.success(message)
            else:
                st.error(message)
    st.stop()
else:
    st.caption(f"当前 API Key：`{mask_api_key(effective_api_key)}`")

try:
    st.session_state.kb = st.session_state.kb or _build_kb(effective_api_key)
except Exception as exc:  # pragma: no cover - runtime guard
    st.error(f"初始化失败：{exc}")
    st.stop()

skill_map = load_skills()
template_map = load_templates()
skill_names = list(skill_map.keys())
template_names = list(template_map.keys())

with st.sidebar:
    st.subheader("技能与模板")
    default_skills = [name for name in ["五看五定.skill.md", "公文写作规范.skill.md"] if name in skill_names]
    selected_skills = st.multiselect(
        "选择 skill（可多选）",
        options=skill_names,
        default=default_skills,
    )
    template_options = ["不使用模板"] + template_names
    selected_template_name = st.radio("选择报告模板", options=template_options, index=0)
    selected_template_text = "" if selected_template_name == "不使用模板" else template_map.get(selected_template_name, "")

    st.subheader("知识库资料")
    kb_paths = list_knowledge_base_files()
    if not kb_paths:
        st.caption("knowledge_base 下暂无可用资料。")
    else:
        for path in kb_paths:
            st.caption(path.name)

if not st.session_state.bootstrap_done:
    saved = list_saved_files()
    if saved and st.session_state.kb.count() == 0:
        stats = rebuild_all(st.session_state.kb)
        st.info(
            f"检测到历史资料，已自动重建索引：{stats['files']}个文件，"
            f"{stats['parsed_files']}个解析成功，{stats['chunks']}个分片。"
        )
    else:
        stats = index_new_files(st.session_state.kb)
        if stats["new_files"] > 0:
            st.info(
                f"已自动补齐新增历史资料索引：{stats['new_files']}个文件，"
                f"{stats['parsed_files']}个解析成功，{stats['chunks']}个分片。"
            )
    st.session_state.bootstrap_done = True

st.subheader("1) 上传资料")
uploaded_files = st.file_uploader(
    "支持 docx/pdf/md",
    type=["docx", "pdf", "md"],
    accept_multiple_files=True,
)

if st.button("上传并增量入库", use_container_width=True):
    if not uploaded_files:
        st.warning("请先选择文件。")
    else:
        new_paths = save_uploaded_files(uploaded_files, RAW_UPLOADS_DIR)
        if not new_paths:
            st.info("文件已存在，未新增。")
        stats = index_new_files(st.session_state.kb)
        st.success(
            f"处理完成：新增保存{len(new_paths)}个文件，"
            f"新增索引{stats['new_files']}个文件，{stats['chunks']}个分片。"
        )
        st.rerun()

st.caption(f"当前知识库分片数量：{st.session_state.kb.count()}")

st.subheader("知识库管理")
saved_files = list_saved_files()
indexed_files = st.session_state.kb.list_indexed_files()
st.write(f"当前资料数：{len(saved_files)}")
st.write(f"当前解析数：{len(indexed_files)}")
st.write(f"当前向量分片数：{st.session_state.kb.count()}")

col_rebuild, col_clear = st.columns(2)
if col_rebuild.button("重新解析全部资料", use_container_width=True):
    stats = rebuild_all(st.session_state.kb)
    st.success(
        f"已重建：扫描{stats['files']}个文件，"
        f"解析成功{stats['parsed_files']}个，生成{stats['chunks']}个分片。"
    )
    st.rerun()

if col_clear.button("清空知识库", use_container_width=True):
    st.session_state.kb.clear()
    st.success("已清空 Chroma 向量数据。")
    st.rerun()

st.markdown("**已保存资料列表**")
if not saved_files:
    st.caption("暂无已保存资料。")
else:
    for file_name in saved_files:
        col_name, col_del = st.columns([5, 1])
        col_name.write(file_name)
        if col_del.button("删除", key=f"delete_{file_name}"):
            ok = delete_file(st.session_state.kb, file_name)
            if ok:
                st.success(f"已删除资料并同步删除向量：{file_name}")
            else:
                st.warning(f"未找到文件：{file_name}")
            st.rerun()

st.subheader("2) 输入分析对象")
target_object = st.text_input("例如：风电新能源板块", value="风电新能源板块")
enable_web_search = st.checkbox("启用联网搜索补充外部资料", value=False)
search_keywords = st.text_input("联网搜索关键词补充", value="")
strict_full_coverage = st.checkbox("严格全文件覆盖检索", value=False)

st.subheader("3) 生成报告")
if st.button("生成五看五定报告", type="primary", use_container_width=True):
    if st.session_state.kb.count() == 0:
        st.error("知识库为空，请先上传资料。")
    elif not target_object.strip():
        st.error("请输入分析对象。")
    else:
        try:
            settings = load_settings()
            selected_skill_text = _build_selected_skills_text(selected_skills, skill_map)
            if not selected_skill_text:
                # 保持向后兼容：至少加载五看五定基础规则
                selected_skill_text = _load_skill_text()
            retrieved_by_look = retrieve_for_five_looks(
                kb=st.session_state.kb,
                target_object=target_object.strip(),
                n_results=6,
                strict_full_coverage=strict_full_coverage,
            )
            generator = QwenReportGenerator(
                api_key=effective_api_key,
                chat_model=settings["chat_model"],
                enable_web_search=enable_web_search,
                search_keywords=search_keywords,
                strict_full_coverage=strict_full_coverage,
            )
            five_look_text, look_online_sources = generator.generate_five_looks(
                target_object=target_object.strip(),
                skill_rules_text=selected_skill_text,
                template_text=selected_template_text,
                retrieved_by_look=retrieved_by_look,
            )
            five_decision_text, decision_online_sources = generator.generate_five_decisions(
                target_object=target_object.strip(),
                skill_rules_text=selected_skill_text,
                template_text=selected_template_text,
                look_analysis=five_look_text,
                retrieved_by_look=retrieved_by_look,
            )
            section_online_sources = {**look_online_sources, **decision_online_sources}
            report_md = build_markdown_report(
                target_object=target_object.strip(),
                five_look_text=five_look_text,
                five_decision_text=five_decision_text,
                retrieved_by_look=retrieved_by_look,
                section_online_sources=section_online_sources,
                enable_web_search=enable_web_search,
            )
            report_md = clean_generated_report(report_md)
            st.session_state.report_markdown = report_md
            out_path = _save_report(report_md)
            st.session_state.last_output_path = str(out_path)
            st.success("报告生成完成。")
        except Exception as exc:  # pragma: no cover - runtime guard
            st.error(f"生成失败：{exc}")

if st.session_state.report_markdown:
    st.markdown(st.session_state.report_markdown)
    st.download_button(
        "下载 Markdown 报告",
        data=st.session_state.report_markdown.encode("utf-8"),
        file_name=f"五看五定报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

if st.session_state.last_output_path:
    st.caption(f"已保存：`{st.session_state.last_output_path}`")
