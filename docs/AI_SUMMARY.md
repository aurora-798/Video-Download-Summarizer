# AI 视频总结 · 使用与运维手册

> **版本**：0.2.0（2026-05-18）  
> **关联**：[架构 §8](ARCHITECTURE.md#8-ai-总结流水线新) · [验收清单](DELIVERY.md#d-ai-总结核心新功能) · [变更记录](CHANGELOG.md)

---

## 1. 功能概览

在解析出视频信息后，点击 **「AI 一键总结」**，后端自动完成：

1. **解析元数据**（标题、封面、时长 — 复用现有 `parse_video`）
2. **获取文本**：平台字幕优先 → 无字幕则下载音频 + `faster-whisper` 转写
3. **LLM 总结**：DeepSeek（默认）流式输出结构化 Markdown（摘要 / 亮点 / Q&A / 术语 / 时间线 / mermaid 思维导图）
4. **前端展示**：SSE 实时进度 + `marked` 渲染 + `mermaid` 脑图

对标 [bibigpt.co](https://bibigpt.co/) 的信息结构；B 站 / 抖音与 bibigpt 一样走 **ASR 兜底**（游客无法拿到 B 站字幕）。

---

## 2. 五分钟启用

```bash
cd backend
cp env.example .env
# 编辑 .env，填入 DeepSeek API Key：
#   OPENAI_API_KEY=sk-xxxxxxxx
#   OPENAI_BASE_URL=https://api.deepseek.com   # 默认，可不改
#   OPENAI_MODEL=deepseek-chat                 # 默认，可不改

source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

```bash
cd frontend && npm run dev
```

打开 http://localhost:5173 → 粘贴链接 → 解析 → **AI 一键总结**。

### 2.1 仅下载、不总结

下载功能 **不依赖** `.env` 与 LLM Key；只有 `/api/summarize` 需要配置 `OPENAI_API_KEY`。

### 2.2 健康检查

```bash
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool
```

关注 `summary.llm.configured`（应为 `true`）与 `summary.whisper`（本地默认可用）。

---

## 3. 流水线（决策树）

```
粘贴 URL
    │
    ▼
parse_video() ──► meta（标题/封面/时长）
    │
    ▼
subtitle.fetch_subtitle()
    │
    ├─ YouTube / TED 等：yt-dlp 字幕轨 → 解析 vtt/srv3/json3
    │       └─ source=subtitle，跳过 ASR（快、省 token）
    │
    └─ B 站 / 抖音 / 小红书：直接跳过（无游客字幕）
            │
            ▼
        下载音频（复用 platforms + yt-dlp）
            │
            ▼
        transcriber.transcribe()  ← faster-whisper 本地 或 Whisper API
            │
            ▼ source=asr
        llm_client.stream_chat()  ← DeepSeek / 任意 OpenAI 兼容
            │
            ▼
        结构化 Markdown + SSE 推送到前端
```

### 阶段（`stage` 字段）

| stage | 含义 |
|-------|------|
| `fetching_meta` | 解析视频信息 |
| `fetching_subtitle` | 尝试 yt-dlp 字幕 |
| `downloading_audio` | 下载音频（ASR 路径） |
| `transcribing` | 语音转写（含首次模型加载提示） |
| `summarizing` | LLM 流式生成 |
| `done` | 完成 |
| `error` | 失败（含友好中文说明） |

---

## 4. 平台能力矩阵

| 平台 | 字幕 | ASR 兜底 | 典型耗时（参考） | 说明 |
|------|------|----------|------------------|------|
| **YouTube** | ✅ 手动 + 自动（含中文翻译轨） | 可选 | 字幕路径 ~10–30s + LLM | 最便宜、最快 |
| **抖音** | ❌ 无字幕轨 | ✅ | 首次 +1–2min 下模型；转写视时长 | 复用 iesdouyin 音频直链 |
| **B 站** | ❌ 游客被封（2023+） | ✅ | 同抖音，音频略大 | 已实测 WBI/player/conclusion 均需登录 |
| **小红书等** | 视 yt-dlp | 常走 ASR | — | 通用引擎 |

---

## 5. 环境变量速查

复制模板：[`backend/env.example`](../backend/env.example) → `backend/.env`（已 gitignore）。

### LLM（必填，总结功能）

| 变量 | 默认 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | — | DeepSeek / Moonshot / Qwen / OpenAI 等 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容 Chat Completions 根地址 |
| `OPENAI_MODEL` | `deepseek-chat` | 模型名 |

### 语音转写（可选）

| 变量 | 默认 | 说明 |
|------|------|------|
| `WHISPER_BACKEND` | `local` | `local` = faster-whisper；`api` = 远程 Whisper 兼容接口 |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cuda` 需 GPU 环境 |
| `WHISPER_BASE_URL` | — | `WHISPER_BACKEND=api` 时必填 |
| `WHISPER_API_KEY` | — | 同上 |

**提速建议**：长视频或机器较慢时，设 `WHISPER_BACKEND=api` 走 SiliconFlow / OpenAI Whisper，避免本机 CPU 久等。

---

## 6. API 与 SSE

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/api/summarize` | `{"url":"..."}` → `{"task_id":"..."}` |
| `GET` | `/api/summarize/{task_id}` | 轮询快照（断线恢复） |
| `GET` | `/api/summarize/{task_id}/stream` | SSE 事件流 |

### SSE 事件

| 事件 | 用途 |
|------|------|
| `snapshot` | 连接时全量状态 |
| `stage` | 进度条 |
| `meta` | 视频卡片信息 |
| `source` | `subtitle` / `asr` |
| `transcript` | 带时间戳全文 |
| `delta` | LLM 增量 token |
| `done` | 最终 `summary_md` |
| `error` | 错误信息 |
| `close` | 流结束 |

每 30s 发送 `: keep-alive` 心跳，避免代理超时。

### 命令行抽检

```bash
# 启动任务
TASK=$(curl -s -X POST http://127.0.0.1:8765/api/summarize \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# 轮询状态
curl -s "http://127.0.0.1:8765/api/summarize/$TASK" | python3 -m json.tool

# SSE（另开终端）
curl -N "http://127.0.0.1:8765/api/summarize/$TASK/stream"
```

---

## 7. 人工验收（D-1 / D-2 / D-3）

完整勾选表见 [`DELIVERY.md` §D](DELIVERY.md#d-ai-总结核心新功能)。

| 用例 | 链接示例 | 预期路径 | 关键观察点 |
|------|----------|----------|------------|
| **D-1** | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | 字幕 → LLM | 进度含「尝试字幕」且 `source=subtitle`；流式 Markdown + mermaid |
| **D-2** | 任意抖音 `/video/{id}` | ASR → LLM | 提示「无可用字幕」→ 下载音频 → 转写 → 总结 |
| **D-3** | 短 B 站 BV（&lt;5min） | ASR → LLM | 同 D-2；「复制 Markdown」格式正确 |

**前置**：`backend/.env` 中已配置有效 `OPENAI_API_KEY`。

---

## 8. 自动化测试记录（2026-05-18）

在无 `.env` / 无 LLM Key 环境下，已验证流水线至 LLM 前一步；LLM 步骤返回友好错误（符合预期）。

| 用例 | 结果 | 备注 |
|------|------|------|
| `GET /api/health` | ✅ | `llm.configured=false`，`whisper` 本地 base/cpu |
| YouTube `fetch_subtitle` | ✅ | `lang=en` `source=manual` **60** 段 |
| YouTube `POST /api/summarize` | ✅ 至 LLM | `source=subtitle` `transcript_count=60`，`stage=error` 提示配置 Key |
| B 站 / 抖音 `fetch_subtitle` | ✅ 跳过 | 返回 `None`，日志跳过探测 |
| 抖音 ASR 全链路（无 Key） | ✅ 至 LLM | 模型加载 → 转写 **15** 段 → `source=asr` → LLM 配置错误 |
| D-1 YouTube：DeepSeek 流式 + mermaid + 字幕 60 段 | ✅ 2026-05-18 浏览器 | 3–5s；source=subtitle；完整 Markdown + mermaid |
| D-2 抖音：ASR → DeepSeek 中文总结 | ✅ 2026-05-18 浏览器 | ~20s；source=asr；10 段转写 |
| D-3 B 站：ASR + 总结 | ✅ 2026-05-18 API | VAD 空结果时自动 `vad_filter=False` 重试；24 段 |
| 前端 `VideoSummaryCard` | ✅ | 进度条、错误重试、SSE 接入、复制 Markdown |

---

## 9. 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `未设置 OPENAI_API_KEY` | 未创建或未加载 `.env` | `cp env.example .env` 填 Key；**重启 uvicorn** |
| 卡在「首次加载语音模型」 | 首次下载 ~70MB | 等待 1–2 分钟；或 `WHISPER_BACKEND=api` |
| 转写很慢 | CPU + 长视频 | 换 `small` 以上模型更慢；建议 API 或 `WHISPER_DEVICE=cuda` |
| B 站「转写空结果」 | faster-whisper VAD 把音乐/部分 m4a 判为无声 | **已修复**：空结果时自动关闭 VAD 重试 |
| B 站一直走 ASR | 设计如此 | 游客无字幕；非 bug |
| SSE 断开但页面有内容 | 正常 | 用 `GET /api/summarize/{id}` 拉快照 |
| 同音字多 | Whisper 局限 | 可换 `WHISPER_MODEL=small` 或 API 模型 |

---

## 10. 成本参考（DeepSeek）

- 约 **10 分钟** 视频字幕 + 总结：token 量级约数千～一万，DeepSeek 单价极低（约 **¥0.01–0.05** 量级，以官网为准）。
- **YouTube 字幕路径**不消耗 Whisper，仅 LLM token。
- **抖音/B 站**仅消耗本机算力（Whisper）+ LLM token。

---

## 11. 源码索引

| 文件 | 职责 |
|------|------|
| [`subtitle.py`](../backend/app/subtitle.py) | yt-dlp 字幕列表 + 多格式解析 |
| [`transcriber.py`](../backend/app/transcriber.py) | faster-whisper / Whisper API |
| [`llm_client.py`](../backend/app/llm_client.py) | 流式 Chat Completions |
| [`summarizer.py`](../backend/app/summarizer.py) | Pipeline 编排 + Prompt |
| [`summary_jobs.py`](../backend/app/summary_jobs.py) | 任务状态 + 事件队列 |
| [`VideoSummaryCard.vue`](../frontend/src/components/VideoSummaryCard.vue) | SSE + marked + mermaid |

---

## 12. 后续增强（未实现）

- 总结历史持久化（SQLite）
- 重新生成 / 换模型
- 字幕导出 SRT
- 异步分段下载音频（长视频进度更平滑）

见 [`DELIVERY.md` §六](DELIVERY.md#六后续路线优先级)。
