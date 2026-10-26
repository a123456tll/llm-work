# llm-work — LLM 应用实践合集

个人 LLM 开发实践仓库，主题不再局限于 MCP：既包含基于
[MCP](https://modelcontextprotocol.io)（Model Context Protocol）与
[AnythingLLM](https://anythingllm.io) 的知识库与工具封装实验，也包含不依赖任何框架的
Agent 流式对话与工具调用入门练习，共六个相互独立的小项目：

| 目录 | 说明 | 技术栈 |
| --- | --- | --- |
| [`anythingllm-mcp/`](anythingllm-mcp/) | 把 AnythingLLM 工作区封装成 MCP 工具，供 opencode / 任意 MCP 客户端提问 | Python · MCP SDK 2.x · Streamable HTTP |
| [`anthingllm-shangchuanwangye/`](anthingllm-shangchuanwangye/) | 单文件网页工具：上传文档到 AnythingLLM 并触发向量化嵌入 | 原生 HTML / JavaScript |
| [`chongwuyiyuanmcp/pet-hospital-mcp/`](chongwuyiyuanmcp/pet-hospital-mcp/) | 把既有 Go 宠物医院 REST API 适配成无状态 MCP 服务 | Python · MCP SDK 2.x · Pydantic · pytest |
| [`Agent/Practice01/`](Agent/Practice01/) | 最小流式对话练习：直接调用 OpenAI 兼容接口逐字输出回答 | Python · requests |
| [`Agent/Practice02/`](Agent/Practice02/) | 工具调用（function calling）练习：日期/闰年计算 + 本地文件目录读写改删，附 Mermaid 架构图 | Python · requests |
| [`Agent/tAgent/`](Agent/tAgent/) | 上述练习的工程化重构版（原 `xAgent`）：核心与界面分离的智能体框架，内置 15 个工具，含联网搜索、网页阅读与本地命令调用，先落地 Textual 终端界面 | Python · httpx · trafilatura · Textual · pytest |

> 目录名 `anthingllm-shangchuanwangye` 为历史遗留拼写（`shangchuanwangye` = 上传网页），
> 为避免破坏既有链接予以保留。

## 各项目的关系

```text
                        ┌──────────────────────────────┐
                        │      AnythingLLM 实例        │
                        │  workspace / 文档 / 向量库   │
                        └───────▲──────────────▲───────┘
                                │              │
                HTTP  /api/v1/...│              │ Streamable HTTP /mcp
                                │              │
        ┌───────────────────────┴──┐        ┌──┴──────────────────────┐
        │  上传网页（浏览器直连）  │        │  anythingllm-mcp       │
        │  document/upload        │        │  ask_workspace 工具    │
        │  workspace/update-...   │        └──┬──────────────────────┘
        └──────────────────────────┘           │ MCP client
                                                │
                                          ┌─────▼──────────┐
                                          │  opencode /    │
                                          │  其他 MCP 客户端│
                                          └────────────────┘

        ┌────────────────┐   HTTP    ┌──────────────────────┐   MCP    ┌──────────────┐
        │  AI 客户端     │──────────▶│  pet-hospital-mcp    │◀─────────│  Go 宠物医院 │
        └────────────────┘  /mcp     │  list_pets 工具      │  /mcp    │  REST API    │
                                       └──────────────────────┘           └──────────────┘
```

- **anythingllm-mcp** 与 **上传网页** 面向同一个 AnythingLLM 实例：网页负责「把知识灌进去」，
  MCP 服务负责「把知识问出来」。
- **pet-hospital-mcp** 与 AnythingLLM 无关，是另一条独立练习线：把已有 REST 后端
  无侵入地包装成 MCP 工具，**不修改 Go 后端任何代码**。
- **Agent/Practice01** 同样与 MCP 无关，是最入门的一条线：绕开所有框架，
  直接用 `requests` 流式调用 OpenAI 兼容接口，理解「请求 → SSE → 逐字输出」的最小闭环。
- **Agent/Practice02** 在 Practice01 的基础上引入 **function calling**：模型按需调用
  `getdate`（执行本地 `date` / `time` 命令）、`isLeapYear` 与 10 个本地文件工具，
  本地执行结果回填 `tool` 消息后继续对话，是「模型 → 工具 → 模型」的最小闭环。
- **Agent/tAgent** 是 Practice02 的工程化重构（原 `xAgent`，目录已改名、项目内部仍以
  `xagent` 命名）：把单文件拆成 `core`（业务：配置 / 会话 / 模型调用 / 工具执行 / 编排）
  与 `tui`（Textual 界面）两层，`core` 以**异步事件流**对外输出，因此同一套核心可以直接
  接到终端、Web、桌面端与移动端；`web/`、`desktop/`、`mobile/` 三个目录已按统一契约预留。

## 快速上手

六个项目互相独立，按需选择其一安装。

### 1. anythingllm-mcp

前置条件：本机已运行 AnythingLLM（默认 `http://localhost:3001`），
并已在其界面 **Settings → API Keys** 中生成密钥。

```powershell
cd anythingllm-mcp
pip install -r requirements.txt

# 必须设置 API Key，否则服务拒绝启动
$env:ANYTHINGLLM_API_KEY = "<你的 API Key>"

python -m uvicorn server:app --host 127.0.0.1 --port 7000
```

然后在另一个终端验证：

```powershell
python test_client.py
```

接入 opencode：本目录已附带 `opencode.json`（项目级 MCP 配置，只在当前目录生效）。
注意必须**先启动服务**，opencode 才能看到 `ask_workspace` 工具。

详见 [`anythingllm-mcp/README.md`](anythingllm-mcp/README.md)。

### 2. anthingllm-shangchuanwangye

无需安装依赖，直接用浏览器打开 `index.html`：

1. 在页面顶部「API Key」输入框粘贴密钥（仅保存在本机浏览器的 localStorage）；
2. 页面会自动读取第一个 workspace；
3. 选择文件 → 点击「上传并嵌入」，完成上传与向量化。

若 AnythingLLM 的端口不是默认的 `50368`，在地址栏附加参数打开：
`index.html?api=http://localhost:<端口>/api`。

### 3. chongwuyiyuanmcp/pet-hospital-mcp

前置条件：本机已运行 Go 宠物医院 REST API（默认 `http://127.0.0.1:8080`），
且 `GET /health` 可访问。

```bash
cd chongwuyiyuanmcp/pet-hospital-mcp

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"

# 启动 MCP 服务（默认 127.0.0.1:8000）
pet-hospital-mcp
# 等价于 python -m pet_hospital_mcp
```

运行测试（全部使用 MockTransport，**不会访问真实 Go 服务**）：

```bash
pytest -q
```

预期 `53 passed`。也可以用官方调试器验证：

```bash
npx @modelcontextprotocol/inspector
# Transport 选 Streamable HTTP，URL 填 http://127.0.0.1:8000/mcp
```

详见 [`chongwuyiyuanmcp/pet-hospital-mcp/README.md`](chongwuyiyuanmcp/pet-hospital-mcp/README.md)
与面向后续开发者的
[`UPGRADE_PROMPT.md`](chongwuyiyuanmcp/pet-hospital-mcp/UPGRADE_PROMPT.md)。

### 4. Agent/Practice01

一个单文件命令行对话程序：读取本地 `config.ini`，流式请求 OpenAI 兼容接口，
按 token 打印回答并保留多轮上下文。

```powershell
cd Agent/Practice01
pip install requests

# 复制下面的 config.ini 并填入你自己的 key（该文件已被 .gitignore 忽略，不会上传）
python chat.py
```

`config.ini` 格式：

```ini
[llm]
base_url = https://api.siliconflow.cn/v1
api_key = <你的 API Key>
model = Qwen/Qwen3-8B
```

启动后按提示输入问题，输入 `Ctrl+C` 结束程序。

### 5. Agent/Practice02

同目录下有两个单文件程序，共用一份 `config.ini`（格式同上，同样被忽略、不上传）：

| 文件 | 说明 |
| --- | --- |
| `chat.py` | Practice01 的对话循环 + 2 个工具：`getdate`（调用本地 `date` / `time` 命令取时间）、`isLeapYear`（python 判定闰年） |
| `file_chat.py` | 扩展到 12 个工具：在上面基础上新增 `getcwd`、`list_dir`、`get_file_type`、`read_file`、`create_file`、`edit_file`、`create_dir`、`delete_dir`、`delete_file`、`rename_path`，覆盖本地文件与目录的查看、创建、编辑、改名、删除 |
| `file_chat_architecture.mmd` | `file_chat.py` 的 Mermaid 架构图（纯文本，可直接预览渲染） |

```powershell
cd Agent/Practice02
pip install requests
python file_chat.py
```

常用示例：`现在几点`、`2024 年是不是闰年`、`在 tmp 目录创建 a.txt 写入你好并读回确认`、
`把 a.txt 改名为 b.txt`。

程序侧的两点约定：

- 工具参数用 `json.JSONDecoder().raw_decode()` 解析，容忍流式返回里 `arguments`
  的尾部碎片，解析失败会把错误回传给模型重试。
- 文件操作用 python 标准库实现，相对路径统一解析到当前工作目录；
  `delete_dir` 拒绝删除当前工作目录与磁盘根目录；读写仅支持纯文本文件。
  请在自己的练习目录下运行，避免让模型误删重要数据。

### 6. Agent/tAgent

在 Practice02 基础上重构出的**分层工程**（目录由原 `xAgent` 重命名而来，
项目内部仍以 `xagent` 命名）：核心逻辑与界面彻底分离，
先落地 Textual 终端界面，并为后续 Web / Desktop / Mobile 界面预留统一契约。

```text
tAgent/
├── core/     模型调用、工具执行、会话状态、编排（不依赖任何界面框架）
├── tui/      Textual 终端界面（只消费 core 的事件流）
├── web/ desktop/ mobile/   预留的其他前端（目录内附实现指引）
├── docs/FRONTEND_CONTRACT.md   前端接入契约
└── tests/   core 与 tui 的自动化测试
```

```powershell
cd Agent/tAgent
pip install -e ".[tui,dev]"

# 复制配置模板并填入 base_url / api_key / model（config.ini 已被 .gitignore 忽略）
copy config.example.ini config.ini

python -m tui          # 启动终端界面
pytest -q              # 88 个离线用例，不发真实请求
```

界面操作：`Enter` 发送、`Shift+Enter` / `Alt+Enter` 换行、`Ctrl+L` 清空、`F1` 帮助、
`Ctrl+Q` 退出；另有 `/help`、`/clear`、`/tools`、`/model`、`/cwd`、`/exit` 等斜杠命令
（界面层功能，不消耗模型请求）。

特性与能力：

- **分层清晰**：`core` 不导入任何界面库，前端之间也互不依赖；
- **事件驱动**：`Agent.run()` 以异步生成器输出事件，TUI / Web / SSE 复用同一套逻辑；
- **工具丰富**：15 个内置工具（日期时间 2 + 文件系统 10 + 网络搜索 1 + 网页抓取 1 +
  本地命令行 1）经注册中心统一管理；
- **联网搜索**：`searchweb` 调用百度千帆 AI 搜索 - 网页搜索 API，返回网页标题、摘要与链接
  （每月 1500 次免费额度，不产生模型 token 费用）；
- **网页阅读**：`fetchweb` 用本地 `curl` 下载网页，再经 `trafilatura` 提取正文并转为 Markdown；
- **本地命令**：`RunCli` 让 Agent 调用本机已安装的命令行程序（如 `python`、`git`、`ipconfig`），
  以参数列表 + `shell=False` 执行，不拼接 shell 字符串；
- **可替换**：模型客户端遵循 `LLMClient` 协议，换服务商不改业务代码；
- **兼容性强**：对服务商返回的畸形工具调用（参数碎片、缺调用 id、整段调用塞进参数）自动归一化。

安全提示：tAgent 具备创建 / 编辑 / 改名 / 删除本地文件与目录、联网搜索，
以及通过 `RunCli` 执行任意本地命令的能力（命令以当前用户权限运行、暂无可执行白名单）。
请只在受控教学实验环境、自己的练习目录下运行，不要指向重要数据目录。

详见 [`Agent/tAgent/README.md`](Agent/tAgent/README.md) 与
[`Agent/tAgent/ARCHITECTURE.md`](Agent/tAgent/ARCHITECTURE.md)。

## 环境依赖一览

| 项目 | Python | 关键依赖 | 外部服务 |
| --- | --- | --- | --- |
| anythingllm-mcp | 3.11+ | `mcp[cli]>=2.0`、`httpx`、`uvicorn` | AnythingLLM（:3001） |
| 上传网页 | 无（浏览器） | — | AnythingLLM（:50368） |
| pet-hospital-mcp | 3.11+ | `mcp==2.0.0`、`httpx`、`pydantic` | Go 宠物医院 API（:8080） |
| Agent/Practice01 | 3.8+ | `requests` | SiliconFlow 等 OpenAI 兼容 API |
| Agent/Practice02 | 3.8+ | `requests` | SiliconFlow 等 OpenAI 兼容 API |
| Agent/tAgent | 3.10+ | `httpx`、`trafilatura`、`textual`、`pytest` | SiliconFlow 等 OpenAI 兼容 API；可选百度千帆搜索 API |

## 安全说明

- 仓库**不包含任何 API Key**。密钥一律通过环境变量（`anythingllm-mcp`）、
  页面输入框（上传网页）或本地 `config.ini`（`Agent/Practice01`、`Agent/Practice02`、
  `Agent/tAgent`，均已被忽略）提供。
- `.env`、`.venv/`、`__pycache__/`、`*.egg-info/`、`*.log`、`config.ini`
  均已在 `.gitignore` 中排除。
- 前三个项目的本地服务均**只监听 127.0.0.1**，属于本机教学/实验用途：
  `pet-hospital-mcp` 明确不做认证、权限与 CORS / Origin 校验，
  **请勿直接暴露到公网**；`Agent/Practice01` 只作为出站客户端访问外部 API，
  `Agent/Practice02` 与 `Agent/tAgent` 除出站请求外还会按对话指令创建、编辑、
  改名、删除本地文件与目录；其中 `Agent/tAgent` 还内置了 `RunCli`，可执行任意本地
  命令，请只在自己的练习目录下运行。
- `pet-hospital-mcp` 的日志会对 `ownerPhone` / `ownerAddr` / `chipNo`
  （含 snake_case 写法）在任意嵌套层级递归脱敏。
- 若你曾在本仓库的历史提交中放置过密钥，请立即在对应服务中**轮换（rotate）该密钥**——
  从 Git 历史中删除并不能让它自动失效。

## 协议说明

`pet-hospital-mcp` 使用 MCP **2026-07-28** 的无状态 Streamable HTTP 流程：
不实现旧版 `initialize` 握手，不使用 `Mcp-Session-Id`，无会话存储与过期机制，
每个请求独立携带 `_meta` 协议信封。详见其
[README](chongwuyiyuanmcp/pet-hospital-mcp/README.md#无状态说明)。

## 许可证

仓库内各子项目以学习与实验为目的。
`pet-hospital-mcp` 在其 `pyproject.toml` 中声明为 MIT。
