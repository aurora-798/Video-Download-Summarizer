# 更新日志

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [0.2.0] - 2026-05-18

### 修复

- **`transcriber.py`**：本地 Whisper 在 `vad_filter=True` 返回 0 段时，自动以 `vad_filter=False` 重试（修复 B 站 DASH 音频 / MV 类内容转写失败）

### 新增 — AI 视频总结

- **`POST /api/summarize`** + **`GET /api/summarize/{id}/stream`** (SSE)：URL → 结构化中文 markdown 总结
- **`backend/app/subtitle.py`**：yt-dlp 抓字幕（手动 + 自动）+ vtt/srv3/json3/srt/ttml 解析，自动选择中文/英文优先
- **`backend/app/transcriber.py`**：faster-whisper 本地（默认，`base` 模型 ~70MB）+ OpenAI 兼容 Whisper API 二选一
- **`backend/app/llm_client.py`**：httpx 流式 Chat Completions（默认 DeepSeek，OpenAI 兼容任意切换）
- **`backend/app/summarizer.py`**：pipeline 编排 — 字幕优先 → ASR 兜底 → LLM 流式；提取抖音/B 站音频（复用 platforms 模块）
- **`backend/app/summary_jobs.py`**：内存任务 + 事件队列，软上限 64 条 LRU
- **`backend/env.example`**：DeepSeek / Moonshot / Qwen / SiliconFlow / OpenAI 端点模板
- **`frontend/src/components/VideoSummaryCard.vue`**：marked + mermaid 流式渲染；步骤进度条；字幕折叠；思维导图折叠；复制 Markdown
- **`frontend/src/components/VideoResultCard.vue`**：新增「AI 一键总结」紫色按钮，emit `summarize` 事件
- **`frontend/src/api.js`**：`startSummarize` / `getSummary` / `openSummaryStream`（EventSource）
- **`/api/health`** 增加 `summary.llm` / `summary.whisper` 字段，便于排查配置

### LLM Prompt 设计（参考 bibigpt 输出结构）

输出包含：摘要（30 字一句话）/ 内容亮点（5-8 条）/ 思考与启发（Q&A）/ 关键术语 / 时间线章节（带 `[mm:ss]`）/ mermaid 思维导图。

### 平台覆盖说明

| 平台 | 字幕 | ASR | 备注 |
|---|---|---|---|
| YouTube | ✅ 手动 + 自动字幕 | — | 无 LLM key 也能跳到字幕阶段，最便宜路径 |
| 抖音 / 小红书 | ❌（视频数据无字幕轨） | ✅ | 复用现有下载链路抓音频 |
| B 站 | ❌（游客字幕被 B 站封禁，2023+） | ✅ | 已实测 `x/player/v2`、`x/player/wbi/v2`、`conclusion/get` 全要登录态 |

### 文档

- `README.md`：项目结构、API 一览、`.env` 配置说明
- `docs/ARCHITECTURE.md` §8：AI 总结流水线 / SSE 协议 / 任务管理
- `docs/DELIVERY.md`：新增 D-1/D-2/D-3 验收用例
- `docs/AI_SUMMARY.md`：AI 总结专册（配置、决策树、平台矩阵、SSE、自动化测试记录、排障、成本参考）

---

## [0.1.3] - 2026-05-18

### 新增

- **B 站自研解析器** `backend/app/platforms/bilibili.py`：WBI 签名 + `playurl`（`try_look=1`）+ 分轨直拉；**无需** cookies 文件。
- 支持 URL：`/video/BV…`、`/video/av…`、`b23.tv` 短链、多 P 参数 `?p=`。
- **`mp4_compat.py`**：合并后 QuickTime 兼容（`+faststart`、HEVC `hvc1` 标签、AV1 转 H.264）；解析列表优先 H.264。
- `ParseResponse` 增加 `max_height`、`hd_hint`（游客画质说明）。

### 变更

- `downloader.py`：B 站走 `_parse_bilibili` / `_run_bilibili_download`（urllib 双轨 + ffmpeg 合并），与抖音并列分流。
- 前端 `VideoResultCard`：默认最高可用清晰度；移除 >720p 假 VIP 下载拦截；合并/画质提示优化。
- `main.py`：启动时日志提示 ffmpeg 是否就绪。

### 修复

- B 站 BV 号 **大小写敏感**：不再 `.upper()` 整段 ID，修复接口返回「啥都木有」导致解析失败。
- B 站合并 MP4 在 macOS QuickTime **仅有声无画**（AV1/HEVC 标签与编码兼容）。
- `imageio-ffmpeg` 未安装时 B 站仅暴露音频轨的问题（文档与启动日志已强调依赖）。

---

## [0.1.2] - 2026-05-18

### 新增

- **抖音自研解析器** `backend/app/platforms/douyin.py`：通过 `iesdouyin.com/share/video/{id}/` 移动端 SSR 页提取 `_ROUTER_DATA`，无需 cookies、无需 ffmpeg。
- 支持 URL：`/video/`、`/note/`、`?modal_id=`、`v.douyin.com` 短链、收藏夹弹窗链接。
- 下载格式：`douyin-nwm`（无水印）、`douyin-wm`（带水印兜底）。
- `imageio-ffmpeg` 依赖：pip 安装时自动获取静态 ffmpeg，供 yt-dlp 合并 B 站等分轨视频。

### 变更

- `downloader.py`：按平台路由；抖音用 `urllib` 直拉 mp4 + 进度上报。
- `ffmpeg_check.py`：优先系统 ffmpeg，回退 `imageio_ffmpeg.get_ffmpeg_exe()`。
- 前端：移除「请安装 ffmpeg / 请放置 cookies」类用户操作提示。

### 修复

- 抖音 `Unsupported URL`（收藏夹 `modal_id` 链接）。
- 抖音 `Fresh cookies are needed`（不再依赖 yt-dlp DouyinIE）。

---

## [0.1.1] - 2026-05-18

### 新增

- `url_normalizer.py`：抖音 `modal_id` / `/note/` URL 规范化。
- `ffmpeg_check.py` 与 `/api/health` 的 `ffmpeg` 字段。
- `ParseResponse.ffmpeg_available`；无 ffmpeg 时过滤 video-only 格式。

### 变更

- 错误信息 `_friendly_error` 中文化（后续 0.1.2 改为不向用户索要操作）。

> 注：0.1.1 中 cookies 文件方案已在 0.1.2 被抖音直采方案替代，**不再推荐使用**。

---

## [0.1.0] - 2026-05-18

### 新增

- MVP：FastAPI + yt-dlp 解析/下载、Vue3 前端、VIP 付费墙 UI、下载队列与进度轮询。
- Bilibili 公开视频解析与音频下载验收通过。
