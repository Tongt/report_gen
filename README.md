# 五看五定智能体（MVP）

一个最小可运行的本地文件分析智能体：

- 上传 `docx/pdf/md` 文件
- 自动写入本地 Chroma 知识库
- 基于“五看五定”方法生成 Markdown 报告

## 快速开始（本地）

1. 进入项目目录：

```bash
cd wukan-wuding-agent
```

2. 创建并激活虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

在 Windows 上可使用：`\.venv\Scripts\activate`

3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 启动应用：

```bash
streamlit run app.py
```

5. 配置 API Key（任选其一）：

- **推荐**：打开页面后按提示填写并保存。本机默认写入 `config/user_settings.json`；侧栏「API Key」可随时更换或清除。
- **本机可选**：复制 `.env.example` 为 `.env`，设置 `DASHSCOPE_API_KEY`（优先级低于页面已保存的 Key）。
- **Streamlit Cloud**：见下文；访客隔离模式下 **不会**把 Key 写入共享的 `user_settings.json`，而是仅保存在当前浏览器会话中。

## 部署到 Streamlit Community Cloud

1. 将仓库推送到 GitHub（或 GitLab 等受支持源），确保根目录包含 `app.py` 与 `requirements.txt`。
2. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)，用仓库创建应用；主文件填 `app.py`。
3. **API Key**：不在 Streamlit Secrets 里配 `DASHSCOPE_API_KEY`。每位访问者在页面填写**自己的** Key。开启「访客隔离」时 Key 只存在该访客的 Streamlit 会话里，写入共享磁盘的 `config/user_settings.json` 会已被避免，且资料与向量库按会话分子目录存放，**用户之间不应再共用同一份上传记录与 Chroma**。
4. 若部署后仍像「全员共用一块盘」，请在 **Secrets** 中显式打开多租户隔离（与 `[server]` 无关，整段 TOML 放在 Secrets 即可）：

```toml
WUKAN_MULTI_TENANT = "true"
```

（若你**故意**要所有登录者共用同一知识库与同一保存路径，可设 `WUKAN_SINGLE_TENANT = "true"`，恢复旧行为，但不适合公开展示。）

5. 在部署向导的 **Advanced settings** 中，将 **Python 版本** 选为 **3.11**（与 Chroma 等依赖更一致）。

**注意**：Community Cloud 的磁盘在实例回收后通常不持久；向量库与上传资料在冷启动后可能丢失。若需长期保留知识库，需自行接入对象存储或外部向量库，这超出本 MVP 范围。

项目内已包含 `.streamlit/config.toml`，用于 Streamlit 的通用运行参数（与云端、本地均兼容）。`.streamlit/secrets.toml.example` 仅作说明参考，**勿**在 Secrets 中放共享的用户 API Key。

### 为何以前在 Cloud 上会「看到别人填的 Key / 资料」？

Streamlit Community Cloud **多台浏览器共用同一台容器和一块磁盘**。原先把 API Key 放在 `config/user_settings.json`，把上传与 Chroma 放在全局的 `knowledge_base/`，因此后打开的访客会读到前一个访客写进磁盘的文件。当前版本在检测到云环境（或通过 `WUKAN_MULTI_TENANT`）时会按**浏览器会话**拆分目录，并把 Key 放在会话状态中。

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
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── README.md
```

## 说明

- 第一阶段仅单智能体、单页面；支持可选联网搜索补充（默认关闭）。
- 报告固定为“五看”+“五定”十个章节。
- 每章会区分“本地资料依据 / 联网补充资料”，并附来源说明。
- `knowledge_base` 只放业务资料文件，是事实来源（RAG 检索来源）。
- `skills` 只放方法论和写作规范，不参与向量检索，不作为事实来源。
- `templates` 只放报告结构模板，不参与向量检索，不作为事实来源。
- 本地可仅用网页保存 API Key，不必手写 `.env`；Streamlit Cloud 在访客隔离模式下 Key 在会话内、资料在 `knowledge_base/sessions/<会话ID>/`，避免多人共盘串数据；勿用 Deploy Secrets 放共享的用户 API Key。
- `.env` 仍支持高级用法（例如固定模型参数、环境变量注入）。
- 已保留 `.env.example`，可用于查看/复制高级配置项（模型与 KPI 预留参数）。

## 向量库重建

- 页面操作：点击“重新解析全部资料”按钮。
- 命令行（快速）：

```bash
python -c "from config import load_settings, CHROMA_DIR, COLLECTION_NAME; from utils.vector_store import ChromaKnowledgeBase; from utils.indexer import rebuild_all; s=load_settings(); kb=ChromaKnowledgeBase(str(CHROMA_DIR), COLLECTION_NAME, s['api_key'], s['embedding_model']); print(rebuild_all(kb))"
```
