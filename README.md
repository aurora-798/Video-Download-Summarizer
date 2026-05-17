# VidGrabPro · 万能视频下载 & AI 总结

> 粘贴链接，一键下载 + 一键 AI 总结。抖音 / B 站**开箱即用**（自研解析，无需 cookies）；YouTube 等其余站点由下载引擎驱动。`AI 总结`走「字幕优先 + 语音转写兜底 + LLM 结构化笔记」标准流水线（对标 bibigpt.co）。

![tech](https://img.shields.io/badge/Backend-FastAPI-009688)
![tech](https://img.shields.io/badge/Frontend-Vue3-42b883)
![tech](https://img.shields.io/badge/Engine-yt--dlp-red)
![tech](https://img.shields.io/badge/Douyin-自研直采-000000)
![tech](https://img.shields.io/badge/Bilibili-自研WBI-pink)
![tech](https://img.shields.io/badge/ASR-faster--whisper-purple)
![tech](https://img.shields.io/badge/LLM-DeepSeek-2F73FF)

---

## 特性

| 能力 | 说明 |
|------|------|
| **抖音零配置** | 收藏夹弹窗链接、`/video/`、短链均可解析；无水印 mp4 直下 |
| **B 站零配置** | BV/av 链接、短链 `b23.tv`；WBI 接口取流 + ffmpeg 合并，优先 H.264 |
| **1000+ 站点** | 其余平台走通用引擎，随上游更新 |
| **ffmpeg 随 pip 安装** | `imageio-ffmpeg` 提供静态二进制，**不必** `brew install ffmpeg` |
| **AI 一键总结** | 字幕优先（YouTube）+ 本地 Whisper 兜底（抖音/B 站）→ DeepSeek 结构化 markdown，SSE 流式呈现 |
| **思维导图** | 总结同步生成 mermaid `mindmap`，前端折叠渲染 |
| **用户无感** | 不要求导出 cookies、不要求手动装系统依赖 |

---

## 项目结构

```
video_download_project/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md      # 架构、平台分流、扩展指南
│   ├── AI_SUMMARY.md        # AI 总结：配置、流水线、验收、排障
│   ├── DELIVERY.md          # 功能清单与验收步骤
│   └── CHANGELOG.md         # 版本记录
├── backend/
│   ├── requirements.txt
│   ├── env.example          # 复制为 .env 后填 DeepSeek key
│   └── app/
│       ├── main.py
│       ├── downloader.py    # 解析/下载编排
│       ├── jobs.py
│       ├── schemas.py
│       ├── ffmpeg_check.py
│       ├── url_normalizer.py
│       ├── subtitle.py      # 【AI 总结】平台字幕抓取（yt-dlp + 解析 vtt/srv3/json3）
│       ├── transcriber.py   # 【AI 总结】faster-whisper 本地 / OpenAI Whisper API
│       ├── llm_client.py    # 【AI 总结】OpenAI 兼容流式 Chat 客户端
│       ├── summarizer.py    # 【AI 总结】pipeline 编排 + SSE 事件
│       ├── summary_jobs.py  # 【AI 总结】内存任务 + 事件队列
│       └── platforms/
│           ├── douyin.py    # 抖音 iesdouyin 直采
│           └── bilibili.py  # B 站 WBI playurl 直采
└── frontend/                # Vite + Vue3 + TailwindCSS + marked + mermaid
```

---

## 快速开始

### 环境

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端（推荐 3.12） |
| Node.js | 18+ | 前端 |

### 1. 后端（`:8765`）

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # 含 yt-dlp、imageio-ffmpeg、faster-whisper（首次会下载静态 ffmpeg）

# AI 总结要先配置 LLM key（仅总结功能需要，下载功能不依赖）
cp env.example .env
# 用编辑器把 OPENAI_API_KEY 改成自己的 DeepSeek key（默认）
#  也可改 OPENAI_BASE_URL/OPENAI_MODEL 切换 Moonshot/Qwen/SiliconFlow/OpenAI

python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

> 首次点击「AI 总结」**抖音/B 站**视频时，后端会下载 faster-whisper `base` 模型（~70MB）到 `~/.cache/huggingface/`，仅一次。后续秒响应。可以在 `.env` 里改 `WHISPER_MODEL=small/medium/large-v3` 提高中文识别精度，或 `WHISPER_BACKEND=api` 切到 SiliconFlow/OpenAI 的 Whisper 远程接口。

### 2. 前端（`:5173`）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 [http://localhost:5173](http://localhost:5173)。

**试一条抖音链接**（无需任何额外配置）：

```
https://www.douyin.com/user/self?modal_id=7630823840629022577&showTab=favorite_collection
```

或任意 `https://www.douyin.com/video/{数字}` / 分享短链。

**试 B 站**：

```
https://www.bilibili.com/video/BV1GJ411x7h7/
```

**B 站**：与抖音相同，走自研解析（`platforms/bilibili.py` → WBI 接口 + 直链下载 + ffmpeg 合并），**无需**管理员配置 cookies 文件。

> Vite 已将 `/api` 代理到 `127.0.0.1:8765`，开发时无 CORS 问题。

### 生产构建

```bash
cd frontend && npm run build    # → frontend/dist/
```

由 Nginx 托管静态资源，并将 `/api` 反代到 FastAPI 即可。

---

## API 一览

| 方法 | 路径 | 作用 |
|------|------|------|
| `POST` | `/api/parse` | `{ "url" }` → 标题、封面、格式列表 |
| `POST` | `/api/download` | `{ "url", "format_id?", "audio_only?" }` → `{ "job_id" }` |
| `GET` | `/api/progress/{job_id}` | 进度、速度、状态 |
| `GET` | `/api/file/{job_id}` | 触发浏览器下载并清理临时文件 |
| `POST` | `/api/summarize` | `{ "url" }` → `{ "task_id" }` 启动 AI 总结 |
| `GET` | `/api/summarize/{task_id}` | 总结快照（含累计 markdown、stage、source 等） |
| `GET` | `/api/summarize/{task_id}/stream` | SSE 事件流：`stage` / `meta` / `source` / `transcript` / `delta` / `done` / `error` |
| `GET` | `/api/health` | 健康检查 + ffmpeg + LLM/Whisper 配置状态 |

模型定义见 [`backend/app/schemas.py`](backend/app/schemas.py)。

---

## 平台支持（摘要）

| 平台 | 方式 | 用户要做的 |
|------|------|------------|
| **抖音** | 自研 `iesdouyin` 分享页解析 | **无** |
| Bilibili / YouTube 等 | yt-dlp + ffmpeg 合并 | **无**（`pip install` 即可） |

细节与失效排查见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 设计取舍（MVP）

1. **抖音单独实现**：yt-dlp 的 Douyin 抽取器依赖 cookie/签名，体验差；分享页 SSR 更稳定。
2. **其余站点不分叉 yt-dlp**：库调用、随上游升级。
3. **无数据库**：Job 内存存储，文件下完即删。
4. **VIP 仅前端**：邮箱占座写 `localStorage`，后端未校验额度。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 解析/下载流程、模块职责、扩展新平台 |
| [`docs/AI_SUMMARY.md`](docs/AI_SUMMARY.md) | **AI 总结**：`.env` 配置、平台矩阵、SSE、D-1～D-3 验收、排障 |
| [`docs/DELIVERY.md`](docs/DELIVERY.md) | 功能清单、5 分钟验收、已知限制 |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | 版本与补丁历史 |

---

## License & 免责

- 仅供学习与个人合理使用；下载与版权责任由用户自行承担。
- 请遵守各平台服务条款与当地法律。
