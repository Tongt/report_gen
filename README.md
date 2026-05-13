# 五看五定智能体（MVP）

一个最小可运行的本地文件分析智能体：

- 上传 `docx/pdf/md` 文件
- 自动写入本地 Chroma 知识库
- 基于“五看五定”方法生成 Markdown 报告

## 快速开始

1. 进入项目目录：

```bash
cd wukan-wuding-agent
```

2. 创建并激活虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```



4. 启动应用并在网页中配置 API Key（推荐小白方式）：

```bash
streamlit run app.py
```

首次启动后，页面顶部会出现“API Key 配置区”，填写并保存后会自动写入 `config/user_settings.json`。

5. 重新启动（或页面自动刷新后继续使用）：

```bash
streamlit run app.py
```

## 目录结构

```text
wukan-wuding-agent/
├── app.py
├── knowledge_base/
│   ├── raw_uploads/                 # 只放用户资料文件
│   └── chroma_db/                   # 向量库持久化目录
├── skills/
│   ├── 五看五定.skill.md
│   └── 公文写作规范.skill.md
├── templates/
│   └── 五看五定报告模板.md
├── outputs/
├── utils/
│   ├── loader.py
│   ├── indexer.py
│   ├── splitter.py
│   ├── vector_store.py
│   ├── retriever.py
│   └── report_generator.py
├── config.py
├── requirements.txt
└── README.md
```

## 说明

- 第一阶段仅单智能体、单页面；支持可选联网搜索补充（默认关闭）。
- 报告固定为“五看”+“五定”十个章节。
- 每章会区分“本地资料依据 / 联网补充资料”，并附来源说明。
- `knowledge_base` 只放业务资料文件，是事实来源（RAG 检索来源）。
- `skills` 只放方法论和写作规范，不参与向量检索，不作为事实来源。
- `templates` 只放报告结构模板，不参与向量检索，不作为事实来源。
- 小白模式下不需要手动编辑 `.env`，直接在网页填写 API Key 即可。
- `.env` 仍支持高级用法（例如固定模型参数、环境变量注入）。
- 已保留 `.env.example`，可用于查看/复制高级配置项（模型与 KPI 预留参数）。

## 向量库重建

- 页面操作：点击“重新解析全部资料”按钮。
- 命令行（快速）：

```bash
python -c "from config import load_settings, CHROMA_DIR, COLLECTION_NAME; from utils.vector_store import ChromaKnowledgeBase; from utils.indexer import rebuild_all; s=load_settings(); kb=ChromaKnowledgeBase(str(CHROMA_DIR), COLLECTION_NAME, s['api_key'], s['embedding_model']); print(rebuild_all(kb))"
```
