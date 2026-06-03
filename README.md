# Multi-LLM Group Chat / 多 LLM 群聊

A web-based chat application where you converse with multiple AI LLMs in a single group-chat conversation. LLMs can talk to each other — @mention one another, respond autonomously, and build on each other's responses.

一个基于 Web 的聊天应用，你可以在一个群聊对话中与多个 AI LLM 交流。LLM 之间可以互相交谈 — @提及彼此、自主回复、在彼此的回复基础上继续讨论。

## Features / 功能

- Multi-LLM group chat with @mention system / 多 LLM 群聊，支持 @提及
- SSE streaming with token-by-token output / SSE 流式逐字输出
- Markdown rendering (code blocks, lists, tables) / Markdown 渲染（代码块、列表、表格）
- Auto-title generation + inline editing / 自动标题生成 + 行内编辑
- Configurable per-LLM: participation mode, response length / 每个 LLM 可配置：参与模式、回复长度
- BYO API keys, encrypted at rest / 自带 API 密钥，加密存储
- i18n: Simplified Chinese + English / 国际化：简体中文 + 英文
- Supported providers: OpenAI, Anthropic, Google Gemini, DeepSeek, Zhipu (GLM), Kimi (Moonshot)

## Quick Start / 快速开始

### Prerequisites / 环境要求

- Python 3.11+
- pip

### Web App / Web 应用

```bash
# Clone the repository / 克隆仓库
git clone https://github.com/lixingyi2020/agent-group-chat.git
cd agent-group-chat

# Install dependencies / 安装依赖
pip install -r requirements.txt

# Start the server / 启动服务器
python run.py
```

Open your browser to **http://127.0.0.1:8000** / 打开浏览器访问 **http://127.0.0.1:8000**

### Desktop App / 桌面应用

Build a standalone desktop app with system tray — no terminal needed.

```bash
# Install build dependencies / 安装打包依赖
pip install pyinstaller pystray pillow pywebview

# Windows / Windows 平台
build.bat

# macOS / macOS 平台
bash build_mac.sh
```

Output: `dist/agent-chat/` — double-click `agent-chat.exe` (Windows) or `open agent-chat` (macOS) to launch.

输出的桌面应用位于 `dist/agent-chat/` — 双击 `agent-chat.exe`（Windows）或在终端执行 `open agent-chat`（macOS）启动。

| Feature | Windows | macOS |
|---------|---------|-------|
| WebView backend | Edge WebView2 | Native WKWebView |
| System tray | ✓ | ✓ |
| Close to tray | ✓ | ✓ |

### First-Time Setup / 首次设置

1. Click the gear icon (⚙) in the top-right to open **Settings** / 点击右上角齿轮图标 (⚙) 打开**设置**
2. In the **API Keys** section, select a provider and paste your API key, then click **Add Key** / 在 **API 密钥** 区域，选择提供商并粘贴 API 密钥，点击**添加密钥**
3. Scroll down to **LLM Configs**, click **Add LLM**, fill in:
   - **Name**: Display name for this LLM / 显示名称
   - **Provider**: Select the provider / 选择提供商
   - **Model**: Model name (e.g. `gpt-4o`, `deepseek-v4-flash`, `glm-4-flash`) / 模型名称
   - **Participation Mode**: How the LLM joins conversations / 参与模式
   - **API Key**: Select your saved key / 选择已保存的密钥
4. Click **Save** / 点击**保存**
5. Return to the main page and click **+ New Chat** to start / 返回主页，点击**+ 新建对话**开始

### Usage / 使用

| Action / 操作 | How / 方法 |
|---------------|------------|
| Send a message / 发送消息 | Type and press Enter / 输入后按回车 |
| @mention an LLM / @提及 LLM | Type `@` and select from dropdown / 输入 `@` 从下拉菜单选择 |
| @mention all LLMs / @提及所有 LLM | Type `@Everyone` (EN) or `@所有AI` (ZH) / 输入 `@Everyone` 或 `@所有AI` |
| Edit conversation title / 编辑标题 | Click ✎ next to title / 点击标题旁的 ✎ |
| Delete conversation / 删除对话 | Click ✕ next to conversation in sidebar / 点击侧边栏对话旁的 ✕ |
| Switch language / 切换语言 | Use dropdown at bottom of sidebar / 使用侧边栏底部的下拉菜单 |

## Configuration / 配置

### LLM Participation Modes / LLM 参与模式

| Mode / 模式 | Behavior / 行为 |
|-------------|-----------------|
| **@mention only** / 仅 @提及 | Only responds when explicitly @mentioned / 仅在显式 @提及时回复 |
| **Always** / 始终回应 | Responds to every message / 回复每条消息 |
| **Probabilistic** / 概率回应 | Responds randomly based on probability setting / 根据概率设置随机回复 |

When specific LLMs are @mentioned, ONLY those LLMs respond — others stay silent regardless of their mode. @Everyone overrides all modes and triggers every LLM.

当 @提及特定 LLM 时，只有这些 LLM 会回复 — 其他 LLM 无论处于什么模式都不会发言。@所有人 会覆盖所有模式，触发全部 LLM。

### Title Generator / 标题生成器

One LLM can be designated as the "Default for Conversation Title Generation" — it will automatically summarize new conversations into short titles. Check the box in the LLM's edit form. Only one LLM can hold this role at a time.

可以指定一个 LLM 作为"对话标题生成默认" — 它会自动将新对话总结为简短标题。在 LLM 编辑表单中勾选此项。同一时间只能有一个 LLM 担任此角色。

## Project Structure / 项目结构

```
agent-chat/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── routes/              # Page + fragment + SSE + settings routes
│   ├── orchestrator.py      # Multi-LLM coordination
│   ├── providers/           # LLM adapters (OpenAI, Anthropic, Google)
│   ├── db/                  # Models, queries, migrations
│   ├── templates/           # Jinja2 + HTMX templates
│   ├── i18n/                # Chinese + English strings
│   └── crypto.py            # Fernet encryption
├── desktop/
│   ├── main.py              # Desktop app entry (webview + tray)
│   └── tray.py              # System tray icon
├── tests/                   # pytest test suite
├── static/style.css
├── build.bat                # Windows desktop build script
├── build_mac.sh             # macOS desktop build script
├── requirements.txt
└── run.py
```

## Tech Stack / 技术栈

| Component | Technology |
|-----------|------------|
| Backend / 后端 | Python FastAPI |
| Frontend / 前端 | HTMX + Jinja2 + vanilla JS |
| Database / 数据库 | SQLite (aiosqlite) |
| Streaming / 流式 | Server-Sent Events (SSE) |
| Markdown | marked.js |
| Encryption / 加密 | Fernet (cryptography) |

## License / 许可证

MIT
