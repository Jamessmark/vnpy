---
name: agent-session-controller
description: This skill should be used when the user asks to "control agent session", "create agent session", "delete agent session", "update agent session", "send task to agent", "get agent task status", "query agent messages", "open workspace", "close workspace", "find workspace", "control CodeFlicker", "operate CodeFlicker", "send task to CodeFlicker", "CodeFlicker automation", "操作 agent 会话", "创建 agent 会话", "删除会话", "发送任务", "获取任务状态", "查询消息列表", "打开工作空间", "关闭工作空间", "查找工作空间", "操作 CodeFlicker", "控制 CodeFlicker", "给 CodeFlicker 发任务", "CodeFlicker 自动化", or discusses programmatic control of AI agent sessions or CodeFlicker IDE via HTTP API. Provides comprehensive guidance for managing workspaces, sessions (CRUD operations), and executing AI tasks through the Duet Protocol External API.
version: 2.2.0
---

# Agent Session Controller

This skill enables AI agents to programmatically control other AI agent sessions through the Duet Protocol External API (HTTP). It provides two layers of functionality:

- **基础层**: 直接操作工作空间、Session 和 AI 任务
- **功能层**: 高级功能如任务监听、模糊搜索等

## ⚠️ 重要使用原则

**复用已有资源原则**：在使用此 skill 时，应遵循以下原则：

1. **优先复用已有工作空间和会话**：
   - 如果对话上下文中已经存在工作空间 ID 或 Session ID，应直接使用它们发送任务
   - 不要每次都创建新的工作空间或会话，除非用户明确要求

2. **何时创建新资源**：
   - 用户明确要求切换到新的工作空间或项目
   - 用户明确要求创建新的会话
   - 当前没有可用的工作空间或会话

3. **推荐工作流程**：
   ```
   # 首次使用时
   1. health-check.sh → 检查服务连接
   2. workspace-list.sh → 获取当前工作空间
   3. session-list.sh 或 session-create.sh → 获取/创建会话
   4. task-send.sh → 发送任务
   
   # 后续使用时（已有 sessionId）
   直接使用 task-send.sh <已有sessionId> <任务内容>
   ```

4. **上下文感知**：
   - 关注对话历史中已经使用过的 workspaceId 和 sessionId
   - 记录并复用这些 ID，避免重复创建

## ⚠️ 多工作空间操作说明

**默认情况下，任务只能发送给第一个主工作空间（Coordinator 所在的工作空间）。**

如果需要操作多个工作空间，请按以下步骤开启多 Worker 模式：

1. 在 CodeFlicker 中输入：`/settings 开启 DebugServer 多 worker 自启动`
2. 等待任务完成
3. 重启 CodeFlicker

重启后，每个打开的工作空间都会自动启动 Worker 并注册到 Coordinator，从而支持跨工作空间的任务分发和管理。

**验证方式**：运行 `workspace-list.sh`，检查返回的 `workspaces` 数组中是否有多个工作空间且 `connected: true`。

## Prerequisites

### Service Requirements

1. **IDE Plugin Debug Server** must be running:
   - Open CodeFlicker command palette (`Cmd+Shift+P`)
   - Execute: `codeflicker.debugServer.start`
   - HTTP API runs at: `http://localhost:3459`

2. **Verify Connection**:
   ```bash
   ~/.codeflicker/skills/agent-session-controller/scripts/health-check.sh
   ```

3. **如果服务未启动**：
   
   当 `health-check.sh` 返回连接失败时，需要启动 CodeFlicker/VSCode。
   
   **Step 1: 查找 CodeFlicker 可执行命令路径**
   
   ```bash
   # 优先查找 CodeFlicker.app 中的命令
   CODEFLICKER_CLI="/Applications/CodeFlicker.app/Contents/Resources/app/bin/code"
   
   if [ -x "$CODEFLICKER_CLI" ]; then
       echo "Found CodeFlicker CLI: $CODEFLICKER_CLI"
       IDE_CMD="$CODEFLICKER_CLI"
   elif command -v codeflicker &> /dev/null; then
       echo "Found codeflicker in PATH"
       IDE_CMD="codeflicker"
   elif command -v code &> /dev/null; then
       echo "Found code (VSCode) in PATH"
       IDE_CMD="code"
   else
       echo "Error: Neither CodeFlicker nor VSCode CLI found"
       exit 1
   fi
   ```
   
   **Step 2: 使用找到的命令启动 IDE**
   
   ```bash
   # 使用找到的命令打开项目目录
   "$IDE_CMD" /path/to/your/project
   
   # 等待 IDE 完全启动（约 3-5 秒）
   sleep 5
   
   # 重新检查服务状态
   ~/.codeflicker/skills/agent-session-controller/scripts/health-check.sh
   ```
   
   **查找优先级**：
   1. `/Applications/CodeFlicker.app/Contents/Resources/app/bin/code` (macOS CodeFlicker)
   2. `codeflicker` 命令 (如果已添加到 PATH)
   3. `code` 命令 (VSCode fallback)

## Script Location

All scripts are located in:
```
~/.codeflicker/skills/agent-session-controller/scripts/
```

Set environment variable for custom API URL:
```bash
export DUET_API_URL=http://localhost:3459
```

---

## 基础层 (Basic Layer)

### 1. Workspace Management

#### 1.1 List Workspaces

**Script**: `workspace-list.sh`

```bash
./workspace-list.sh
```

**Returns**:
```json
{
  "success": true,
  "data": {
    "workspaces": [
      {"workspaceId": "ws-abc123", "name": "my-project", "path": "/path/to/project", "connected": true}
    ],
    "currentWorkspaceId": "ws-abc123"
  }
}
```

---

#### 1.2 Open Workspace

**Script**: `workspace-open.sh`

```bash
./workspace-open.sh <folder_path>
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `folder_path` | ✅ | Absolute path to folder |

---

#### 1.3 Close Workspace

**Script**: `workspace-close.sh`

```bash
./workspace-close.sh <workspace_id>
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `workspace_id` | ✅ | Workspace ID to close |

⚠️ **Important**: `workspace-open.sh` 返回的 `workspaceId` 是临时值 `"vscode-ws-new"`，不能直接用于关闭。必须先用 `workspace-list.sh` 获取真实的 `workspaceId`，然后再调用 `workspace-close.sh`。

**正确流程**:
```bash
# 1. 打开工作空间（返回临时 ID）
./workspace-open.sh /path/to/project

# 2. 获取真实的 workspaceId
./workspace-list.sh
# 从返回的 workspaces 数组中找到对应路径的 workspaceId

# 3. 使用真实 ID 关闭
./workspace-close.sh ws-abc123
```

---

#### 1.4 Reload Workspace

**Script**: `workspace-reload.sh`

```bash
./workspace-reload.sh <workspace_id>
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `workspace_id` | ✅ | Workspace ID to reload |

**功能说明**:
- 重新加载指定工作空间，效果等同于 VSCode 的 "Developer: Reload Window" 命令
- 适用于需要刷新扩展状态或应用配置更改的场景

**返回示例**:
```json
{
  "success": true,
  "data": {
    "workspaceId": "ws-abc123",
    "message": "Workspace reload triggered successfully"
  }
}
```

**注意事项**:
- ❗ 默认不能重载 Coordinator 自身的工作空间（会返回错误 `cannot reload coordinator workspace`）
- 重载过程中该工作空间会暂时断开连接，完成后自动重新注册

**强制重载 Coordinator**:

如果确实需要重载 Coordinator 自身，可以使用 `force=true` 参数：

```bash
./workspace-reload.sh <coordinator_workspace_id> --force
```

或直接调用 API：
```bash
curl -X POST "http://localhost:3459/api/workspaces/<workspace_id>/reload" \
    -H "Content-Type: application/json" \
    -d '{"force": true}'
```

⚠️ **强制重载注意事项**：
1. **不要关注返回结果** - 由于重载会立即中断服务，响应可能无法送达
2. **服务会中断** - 所有 HTTP API、WebSocket 连接、Worker 注册表都会丢失
3. **需要等待恢复** - Coordinator 重载完成后（约 5-10 秒），服务才会恢复
4. **适用场景** - 仅用于应用配置更改、插件更新等必须重载的情况

---

### 2. Session Management (CRUD)

#### 2.1 List Sessions

**Script**: `session-list.sh`

```bash
./session-list.sh
```

**Returns**:
```json
{
  "success": true,
  "data": {
    "sessionList": [
      {"sessionId": "uuid", "sessionName": "会话名", "agentMode": "agent", "sessionTimestamp": 1708300000000}
    ]
  }
}
```

---

#### 2.2 Create Session

**Script**: `session-create.sh`

```bash
./session-create.sh [session_name] [agent_mode]
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `session_name` | ❌ | "New Session" | Session display name |
| `agent_mode` | ❌ | "agent" | `"agent"` or `"ask"` |

**Returns**: JSON with generated `sessionId`

---

#### 2.3 Get Session

**Script**: `session-get.sh`

```bash
./session-get.sh <session_id>
```

---

#### 2.4 Update Session

**Script**: `session-update.sh`

```bash
./session-update.sh <session_id> <new_name>
```

---

#### 2.5 Delete Session

**Script**: `session-delete.sh`

```bash
./session-delete.sh <session_id>
```

---

### 3. AI Task

#### 3.1 Send Task

**Script**: `task-send.sh`

```bash
./task-send.sh <session_id> <task_content> [agent_mode]
./task-send.sh <session_id> --file <task_file> [agent_mode]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `session_id` | ✅ | Target session ID |
| `task_content` | ✅ | Task content / question |
| `--file` | ❌ | Read task from file |
| `agent_mode` | ❌ | `"agent"` (default), `"ask"`, `"plan"`, `"jam"` |

**⚠️ For complex content** (newlines, quotes), use `--file`:
```bash
echo "Multi-line
task content" > /tmp/task.txt
./task-send.sh <session_id> --file /tmp/task.txt
```

---

#### 3.2 Stop Task

**Script**: `task-stop.sh`

```bash
./task-stop.sh <session_id>
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `session_id` | ✅ | Target session ID |

**Returns**:
```json
{
  "success": true,
  "data": {
    "sessionId": "uuid",
    "message": "Task stopped successfully",
    "wasRunning": true
  }
}
```

**Behavior**:
- Stops the currently running AI task
- If no task is running, returns `wasRunning: false`
- Idempotent operation (safe to call multiple times)

---

#### 3.3 Respond to Blocking UI

**Script**: `task-respond.sh`

```bash
./task-respond.sh <session_id> <action> <ask_type> [response]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `session_id` | ✅ | Target session ID |
| `action` | ✅ | `"approve"`, `"reject"`, or `"skip"` |
| `ask_type` | ✅ | `"command"`, `"mcp"`, `"plan"`, `"ask_user_questions"` |
| `response` | ❌ | User response (required for `ask_user_questions`) |

**Action Support Matrix**:
| ask_type | approve | reject | skip |
|----------|---------|--------|------|
| `command` | ✅ Execute | ✅ Reject | ✅ Skip |
| `mcp` | ✅ Execute | ✅ Reject | ❌ |
| `plan` | ✅ Execute | ✅ Abandon | ❌ |
| `ask_user_questions` | ✅ Submit | ❌ | ❌ |

**Returns**:
```json
{
  "success": true,
  "data": {
    "sessionId": "uuid",
    "message": "Response submitted successfully",
    "action": "approve",
    "askType": "command"
  }
}
```

**Usage Flow**:
```bash
# 1. Check if session is waiting for input
./session-status.sh <session_id>
# Returns: {"waitingForUserInput": true, "askType": "command", "blockingContext": {...}}

# 2. Respond based on askType
./task-respond.sh <session_id> approve command

# 3. For ask_user_questions, provide response
./task-respond.sh <session_id> approve ask_user_questions "Use TypeScript"
```

---

### 4. Messages

#### 4.1 Search Messages

**Script**: `messages-search.sh`

```bash
./messages-search.sh <session_id> [options_json]
```

**默认行为**（精简模式）：
- 只返回用户输入和 agent 正式输出（`text`, `completion_result`, `user_feedback`）
- 自动过滤掉中间 ReAct 信息（`tool`, `thinking`, `api_req_started`, `command` 等）
- 如需查看所有消息，传入空对象：`'{}'`

**常用示例**：
```bash
# 默认：只看用户输入和 agent 正式输出（推荐）
./messages-search.sh <session_id>

# 查看所有消息（包括 tool 调用等）
./messages-search.sh <session_id> '{}'

# 自定义过滤
./messages-search.sh <session_id> '{"filters":{"say":["text","tool"]}}'
```

**Options JSON**:
```json
{
  "filters": {
    "role": "assistant",
    "say": ["text", "completion_result"],
    "contains": "关键词",
    "chatId": "chat-uuid"
  },
  "options": {
    "limit": 50,
    "order": "desc"
  },
  "textLimits": {
    "perMessage": 2000,
    "total": 50000
  }
}
```

**Filter Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `role` | string | `"user"` or `"assistant"` |
| `say` | string/array | `"text"`, `"completion_result"`, `"tool"`, `"thinking"`, `"error"` |
| `contains` | string | Full-text search (case-insensitive) |
| `chatId` | string | Filter by conversation turn |
| `startTime` / `endTime` | number | Timestamp filter (ms) |

---

### 5. Session Status

#### 5.1 Get Session Status

**Script**: `session-status.sh`

```bash
./session-status.sh <session_id>
```

**Returns**:
```json
{
  "success": true,
  "data": {
    "sessionId": "uuid",
    "isRunning": true,
    "currentChatId": "chat-uuid",
    "lastMessageTs": 1708300000000,
    "lastMessageSay": "tool",
    "waitingForUserInput": false,
    "askType": "command",
    "blockingContext": {
      "command": "rm -rf ./node_modules",
      "isDestructive": true
    }
  }
}
```

**Status Interpretation**:
- `isRunning=true`: Task in progress
- `isRunning=false` + `lastMessageSay="completion_result"`: Completed
- `isRunning=false` + `lastMessageSay="error"`: Failed
- `waitingForUserInput=true`: Waiting for user response (use `task-respond.sh`)
- `askType`: Type of blocking UI (`command`, `mcp`, `plan`, `ask_user_questions`)
- `blockingContext`: Context info about what's being asked

---

### 6. System Info

#### 6.1 Health Check

**Script**: `health-check.sh`

```bash
./health-check.sh
```

---

#### 6.2 System Information

**Script**: `system-info.sh`

```bash
./system-info.sh
```

**Returns**: Coordinator port, registered workspaces, handlers, uptime, etc.

---

## 功能层 (Feature Layer)

### 1. Wait for Task Completion

**Script**: `task-wait.sh`

```bash
./task-wait.sh <session_id> [timeout_seconds] [poll_interval]
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `session_id` | ✅ | - | Session UUID |
| `timeout_seconds` | ❌ | 120 | Max wait time |
| `poll_interval` | ❌ | 2 | Poll interval (seconds) |

**Behavior**:
- Displays status: `.` = waiting, `s` = streaming
- Returns final status when complete

**Exit Codes**:
| Code | Meaning |
|------|---------|
| 0 | Task completed successfully |
| 1 | Task failed with errors |
| 2 | Timeout reached |

---

### 2. Fuzzy Find and Open Workspace

**Script**: `workspace-find-open.sh`

```bash
./workspace-find-open.sh <search_pattern> [base_path]
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `search_pattern` | ✅ | - | Directory name pattern |
| `base_path` | ❌ | `~` | Search base path |

**Functionality**:
1. Checks if matching workspace is already open → returns existing info
2. If not, searches filesystem for matching directory
3. Opens the found directory as workspace

**Returns**:
```json
{
  "success": true,
  "action": "existing|opened",
  "workspace": {...},
  "foundPath": "/path/to/dir"
}
```

---

### 3. Fuzzy Find Session

**Script**: `session-find.sh`

```bash
./session-find.sh <search_pattern>
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `search_pattern` | ✅ | Session name pattern |

**Functionality**:
1. Gets all sessions from current workspace
2. Fuzzy matches session name or ID
3. Returns matching sessions with workspace info

**Returns**:
```json
{
  "success": true,
  "matches": [
    {
      "session": {"sessionId": "...", "sessionName": "..."},
      "workspace": {"workspaceId": "...", "name": "...", "path": "..."}
    }
  ],
  "count": 1
}
```

---

## Common Workflows

### Workflow 1: Create Session and Execute Task

```bash
# 1. Create session
result=$(./session-create.sh "My Task" agent)
session_id=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('sessionId',''))")

# 2. Send task
./task-send.sh "$session_id" "帮我分析这个项目"

# 3. Wait for completion
./task-wait.sh "$session_id" 120 2

# 4. Get results
./messages-search.sh "$session_id" '{"filters":{"say":"completion_result"},"options":{"limit":1}}'
```

### Workflow 2: Find and Use Existing Session

```bash
# 1. Find session by name
./session-find.sh "my-task"

# 2. If found, send new task to it
./task-send.sh "<found_session_id>" "继续上次的任务"
```

### Workflow 3: Open Project and Start Task

```bash
# 1. Find and open project directory
./workspace-find-open.sh "my-project" ~/code

# 2. Create session in that workspace
./session-create.sh "Analysis Task"

# 3. Send task
./task-send.sh "<session_id>" "分析项目架构"
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Cannot connect to service` | Debug server not running | Run `codeflicker.debugServer.start` |
| `Session not found` | Invalid session ID | Use `./session-list.sh` to get valid IDs |
| `Timeout` | Task took too long | Increase timeout or check task complexity |

---

## Reference Documentation

For detailed API documentation, see:
- `references/api-reference.md` - Complete HTTP API endpoint reference (based on F012-api-reference.md)

---

## Notes

- All scripts return JSON output that can be parsed with `jq` or `python -m json.tool`
- Text content may be truncated to control response size (configurable via `textLimits`)
- **Use `--file` option for complex task content** to avoid shell escaping issues
- Workspace operations affect VS Code windows (opens/closes editor windows)

---

## 浏览器端 Webview UI 访问

除了通过 HTTP API 控制 Agent Session 外，还可以**在浏览器中直接访问完整的 Webview UI**。

### 访问地址

| 页面 | URL | 说明 |
|------|-----|------|
| **Webview UI** | `http://localhost:3458` | 完整的 AI Agent 对话界面 |
| **Setting UI** | `http://localhost:3458/setting` | 设置页面 |

**前置条件**：确保 Debug Server 已启动（`health-check.sh` 返回成功）

---

### 支持的功能

浏览器端 Webview UI 与 VSCode 中的插件界面功能一致：

| 功能 | 说明 |
|------|------|
| **AI 对话** | 发送任务、接收流式响应、查看对话历史 |
| **会话管理** | 创建、切换、删除会话 |
| **工具调用展示** | 查看 Agent 使用的工具及执行结果 |
| **代码编辑展示** | 查看代码修改的 Diff 视图 |
| **命令执行审批** | 批准/拒绝 Agent 请求执行的命令 |
| **MCP 工具审批** | 批准/拒绝 MCP 工具调用 |
| **Plan 审批** | 审批 Agent 生成的执行计划 |
| **用户提问响应** | 回答 Agent 提出的澄清问题 |
| **历史记录** | 查看和切换历史会话 |
| **用户状态** | 复用 VSCode 登录状态，无需重新登录 |

---

### 使用场景

1. **可视化调试**：通过 API 控制 Agent 时，在浏览器中实时观察执行过程
2. **多窗口协作**：浏览器与 VSCode 共享状态，可作为独立监控窗口
3. **演示分享**：向他人演示 AI Agent 功能，便于截图录屏
