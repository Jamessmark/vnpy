# Duet Protocol External API Reference

> **版本**: 2.0  
> **基于**: F012-api-reference.md

---

## 基础信息

### 端口分配

| 端口 | 用途 | 说明 |
|------|------|------|
| **3456** | WebSocket 服务 | Coordinator 主服务 |
| **3459** | HTTP API 服务 | 统一 HTTP 接口（本 skill 使用） |

### 环境变量

```bash
export DUET_API_URL=http://localhost:3459
```

---

## REST API 接口

### 1. 工作空间接口

#### GET /api/workspaces
获取工作空间列表

```bash
curl http://localhost:3459/api/workspaces
```

**响应**:
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

#### POST /api/workspaces
打开新工作空间

```bash
curl -X POST http://localhost:3459/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{"folderPath": "/path/to/workspace"}'
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `folderPath` | string | ✅ | 要打开的文件夹路径 |

---

#### DELETE /api/workspaces/{workspaceId}
关闭工作空间

```bash
curl -X DELETE http://localhost:3459/api/workspaces/ws-abc123
```

---

### 2. Session 接口

#### GET /api/sessions
获取 Session 列表

```bash
curl http://localhost:3459/api/sessions
```

**响应**:
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

#### POST /api/sessions
创建 Session

```bash
curl -X POST http://localhost:3459/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "uuid", "sessionName": "新会话", "isComposer": true, "agentMode": "agent"}'
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sessionId` | string | ✅ | Session UUID |
| `sessionName` | string | ✅ | Session 名称 |
| `isComposer` | boolean | ❌ | 是否为 Composer 会话，默认 true |
| `agentMode` | string | ❌ | `"agent"` 或 `"ask"`，默认 `"agent"` |

---

#### GET /api/sessions/{sessionId}
获取单个 Session

```bash
curl http://localhost:3459/api/sessions/session-uuid
```

---

#### PUT /api/sessions/{sessionId}
更新 Session

```bash
curl -X PUT http://localhost:3459/api/sessions/session-uuid \
  -H "Content-Type: application/json" \
  -d '{"name": "新名称"}'
```

---

#### DELETE /api/sessions/{sessionId}
删除 Session

```bash
curl -X DELETE http://localhost:3459/api/sessions/session-uuid
```

---

### 3. AI 任务接口

#### POST /api/sessions/{sessionId}/tasks
发送 AI 任务

```bash
curl -X POST http://localhost:3459/api/sessions/session-uuid/tasks \
  -H "Content-Type: application/json" \
  -d '{"taskContent": "请帮我写一个 Hello World", "agentMode": "agent"}'
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskContent` | string | ✅ | 任务内容 |
| `chatId` | string | ❌ | 对话轮次 ID，不填自动生成 |
| `agentMode` | string | ❌ | `"agent"` 或 `"ask"` |
| `isAskMode` | boolean | ❌ | 是否提问模式 |
| `contextItems` | array | ❌ | 上下文项 |

---

#### GET /api/sessions/{sessionId}/messages
获取 Session 消息列表

```bash
curl http://localhost:3459/api/sessions/session-uuid/messages
```

---

#### POST /api/sessions/{sessionId}/messages/search
搜索 Session 消息

```bash
curl -X POST http://localhost:3459/api/sessions/session-uuid/messages/search \
  -H "Content-Type: application/json" \
  -d '{"filters": {"role": "assistant", "contains": "Hello"}, "options": {"limit": 10}}'
```

**请求参数**:
```json
{
  "filters": {
    "role": "user|assistant",
    "say": "text|tool|thinking|error|completion_result",
    "contains": "搜索关键词",
    "chatId": "chat-uuid",
    "partial": false,
    "startTime": 1708300000000,
    "endTime": 1708400000000
  },
  "options": {
    "limit": 50,
    "offset": 0,
    "order": "asc|desc"
  },
  "fields": ["ts", "role", "say", "text"],
  "textLimits": {
    "perMessage": 2000,
    "total": 50000
  }
}
```

---

#### GET /api/sessions/{sessionId}/status
获取 Session 任务运行状态

```bash
curl http://localhost:3459/api/sessions/session-uuid/status
```

**响应**:
```json
{
  "success": true,
  "data": {
    "sessionId": "uuid",
    "isRunning": true,
    "currentChatId": "chat-uuid",
    "lastMessageTs": 1708300000000,
    "lastMessageType": "say",
    "lastMessageSay": "tool",
    "waitingForUserInput": false
  }
}
```

**状态判断**:
| 状态 | 条件 |
|------|------|
| 运行中 | `isRunning=true` |
| 完成 | `isRunning=false` + `lastMessageSay="completion_result"` |
| 失败 | `isRunning=false` + `lastMessageSay="error"` |
| 等待输入 | `waitingForUserInput=true` |

---

### 4. 系统接口

#### GET /api/health
健康检查

```bash
curl http://localhost:3459/api/health
```

---

#### GET /api/system/info
获取系统信息

```bash
curl http://localhost:3459/api/system/info
```

**响应**:
```json
{
  "success": true,
  "data": {
    "coordinatorPort": 3456,
    "httpApiPort": 3459,
    "workspaceId": "ws-abc123",
    "registeredWorkspaces": [...],
    "defaultWorkspaceId": "ws-abc123",
    "workspaceCount": 1,
    "wsConnections": 2,
    "handlers": [...],
    "handlerCount": 15,
    "uptime": 3600.5
  }
}
```

---

#### GET /api/handlers
获取 Handler 列表

```bash
curl http://localhost:3459/api/handlers
```

---

## 消息类型

| say 类型 | 说明 |
|----------|------|
| `text` | 用户消息或 AI 文本回复 |
| `thinking` | AI 思考过程 |
| `tool` | 工具调用（readFile、writeFile 等） |
| `command` | 终端命令执行 |
| `completion_result` | 任务完成 |
| `error` | 错误发生 |

---

## 错误响应

```json
{
  "success": false,
  "error": "错误描述信息",
  "timestamp": 1708300000000
}
```

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Bridge not available` | 插件未初始化 | 等待插件启动 |
| `Handler not found: xxx` | Handler 不存在 | 检查 Handler 名称 |
| `sessionId is required` | 缺少必要参数 | 检查请求参数 |
