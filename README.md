Vibe-Blender-Flow（VBF）

通过自然语言驱动 Blender 进行“原子化建模”。核心思想是：
1) Blender 端提供封装好的 High-Level Skills（禁止 LLM 直接操作 bmesh 这类复杂底层）
2) Controller 端用 JSON-RPC 2.0 over WebSocket 调用 Skills，逐步完成建模，并在每一步返回 Success/Error + traceback 用于重试

本仓库包含：
- `/client`：客户端入口与 Vibe Protocol 编排（当前包含 RadioTask demo 的确定性计划）
- `/blender_provider`：Blender Addon（8006 WebSocket 监听 + modal timer 每 0.1s 轮询执行队列）与 skills 封装
- `/assets`：保存生成的 `.blend`（预留）
- `/vbf`：对外可复用的 Python 模块（供其它项目 import）

## 运行前置条件

### 客户端环境
- 需要 Python >= 3.10
- 依赖：`websockets`

### Blender 端环境
- Blender 内置 Python 需要具备 WebSocket 依赖（Addon 内会尝试 import `websockets`）
- 建议先在你使用的 Blender Python 环境里安装 `websockets`
  - 具体安装方式取决于你的 Blender 版本与 Python 环境（这里不强行给命令，避免猜错路径）

## Blender Addon（标准安装方式）

本项目已整理出标准 Addon 包目录：`blender_provider/vbf_addon/`。

### 安装
- 将整个文件夹 `vbf_addon` 复制到你的 Blender 插件目录之一：
  - `<Blender 安装目录>/scripts/addons/vbf_addon`
  - 或你的用户目录 addons 路径（取决于 Blender 配置）
- 打开 Blender：
  - Edit -> Preferences -> Add-ons
  - 搜索 “Vibe-Blender-Flow” 并启用

### 启动服务
- 启用后，在 Blender 的 Python Console 运行：
  - `bpy.ops.vbf.serve()`
（或使用本项目 headless 启动脚本，见下方）

### UI 控制
- 3D View -> 右侧 N 面板 -> `VBF` 选项卡
  - Start / Stop 按钮
  - 状态与当前绑定的 host:port 显示

## LLM 配置（OpenAI 兼容模式）

如果希望“自然语言 -> skills 参数 + 自动修复重试”由 LLM 完成，需要提供 OpenAI-compatible 的配置。
如果未配置 LLM，本项目会自动退回到可运行的确定性 `RadioTask` demo（不调用外部 API）。

### 方式 A：环境变量（推荐）
- `VBF_LLM_BASE_URL`：例如 `https://api.openai.com/v1`、或 openrouter 提供的 base_url
- `VBF_LLM_API_KEY`
- `VBF_LLM_MODEL`：例如 `gpt-4o-mini` / `qwen2.5-*` / `glm-*` / openrouter 上的模型名
- 可选：
  - `VBF_LLM_TEMPERATURE`（默认 `0.2`）
  - `VBF_LLM_CHAT_COMPLETIONS_PATH`（默认 `/v1/chat/completions`）
  - `VBF_LLM_JSON_OBJECT`（默认 `1`）

### 方式 B：JSON 配置文件
- 默认会读取 `vbf/config/llm.json`（包内相对路径）。
- 你也可以设置 `VBF_LLM_CONFIG_PATH` 指向任意 JSON 文件覆盖默认位置。
- JSON 文件内容示例：

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "YOUR_KEY",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "chat_completions_path": "/v1/chat/completions",
  "use_response_format_json_object": true
}
```

## skills_plan / repair_plan schema（已实现并用于规划）

`$ref` 引用规则：
- 规范用法：`{"$ref":"<step_id>.data.<key>"}`（与 Blender 返回 `{"ok":..., "data": {...}}` 对齐）
- 兼容别名：`{"$ref":"<step_id>.result.<key>"}` 也会按 `data.<key>` 解析（为避免你提到的 `result` / `data` 字段差异）

LLM 生成的 JSON 只包含 skill 名称与 args，不会输出任何 `bpy`/`bmesh` 操作代码；所有 Blender API 封装都在 `blender_provider/skills.py` 的 skill registry 中。

### 可控建模流程（推荐）
为保证建模过程可控，plan 支持以下控制字段：

```json
{
  "controls": {
    "max_steps": 80,
    "allow_low_level_gateway": false,
    "require_ops_introspect_before_invoke": true
  },
  "steps": [
    {
      "step_id": "s1",
      "stage": "discover|blockout|detail|material|finalize",
      "skill": "ops_search",
      "args": { "query": "cube add" }
    }
  ]
}
```

执行器会强制：
- 阶段顺序不能倒退：`discover -> blockout -> detail -> material -> finalize`
- `ops_invoke` 前必须先有对应 `ops_introspect`
- `py_call/py_set` 默认禁用（除非 `allow_low_level_gateway=true`）

### Blender 可执行文件路径
- 建议设置环境变量：`BLENDER_PATH`
- 默认 fallback：`blender`（假设已加入 PATH）

### WebSocket 地址
- 默认：`127.0.0.1:8006`
- 可通过环境变量覆盖：
  - `VBF_WS_HOST`（默认 `127.0.0.1`）
  - `VBF_WS_PORT`（默认 `8006`）

## 安装

使用 uv（如果你在用 uv）：

```bash
uv sync
```

如果不使用 uv，则至少需要先安装 `websockets`：

```bash
pip install websockets
```

## 启动与示例

### 情况 A：Blender 已在运行（Addon 已开启）
- 只需运行 client，会自动连接到 `ws://127.0.0.1:8006`

### 情况 B：Blender 未运行（Controller 自动 headless 启动）
- client 会用 `blender -b -P /blender_provider/start_vbf_blender.py` 启动并等待 WebSocket 可用

### RadioTask demo

```bash
python client/main.py --prompt "复古收音机"
```

成功后，Controller 将依次下发 skills，并在控制台显示每一步的返回（包含错误 traceback）。
如果 LLM 未配置，会自动退回到“确定性的示例任务”（RadioTask），以保证项目可跑通。

## 作为其它项目的调用模块

你可以直接 import `/vbf` 对外模块：

```python
import asyncio
from vbf import VBFClient

async def main():
    client = VBFClient()
    await client.ensure_connected()
    await client.run_radio_task(prompt="复古收音机")

asyncio.run(main())
```

如果 Blender 尚未运行，`ensure_connected()` 会自动 headless 启动。

## 仅依赖一个包名 + 直接命令行运行

你可以只依赖 `vbf` 包（不需要引入 `client/`），并直接运行：

### 方式 A：模块方式（无需安装脚本）

```bash
python -m vbf --prompt "做一个复古收音机"
```

### 方式 B：安装后作为命令（推荐）

安装本项目（例如用 pip/uv 安装到你的环境后），会获得命令 `vbf`：

```bash
vbf --prompt "做一个复古收音机"
```

> 说明：`client/` 目录仅为历史入口与示例保留，新项目请直接使用 `vbf` 包与其 CLI。

