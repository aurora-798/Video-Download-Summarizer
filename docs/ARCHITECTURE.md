# 架构说明 · VidGrabPro

> 面向维护者与二次开发。产品验收与发布清单见 [`DELIVERY.md`](DELIVERY.md)。

---

## 1. 总览

```
┌─────────────┐     POST /api/parse      ┌──────────────────────────────────┐
│  Vue3 前端   │ ───────────────────────► │         FastAPI (main.py)         │
│  localhost  │     POST /api/download   │                                   │
│    :5173    │ ◄── GET /api/progress ── │  downloader.parse_video()         │
└─────────────┘     GET  /api/file       │         │                │          │
                                         │  抖音?    B站?       其他 URL       │
                                         │    │       │            │           │
                                         │    ▼       ▼            ▼           │
                                         │  douyin  bilibili    yt-dlp API     │
                                         │  直链mp4  WBI+DASH   (+ ffmpeg)     │
                                         └──────────────────────────────────┘
```

**设计原则**

| 原则 | 说明 |
|------|------|
| 用户零配置 | 不要求安装 ffmpeg、不要求导出 cookies；`pip install -r requirements.txt` 即可 |
| 平台分流 | 抖音 / B 站走自研直采；其余平台继续用 yt-dlp，跟随上游升级 |
| 无状态 MVP | Job 存内存，文件下完即删，不接 DB / Redis |

---

## 2. 解析与下载流程

### 2.1 统一入口

| 阶段 | 函数 | 文件 |
|------|------|------|
| 解析 | `parse_video(url)` | `backend/app/downloader.py` |
| 下载 | `start_download(url, format_id, audio_only)` → 后台线程 `_run_download` | 同上 |

`parse_video` 先做 `normalize_url()`（`url_normalizer.py`，处理抖音 `modal_id` 等 wrapper），再按域名路由：

```python
if douyin.is_douyin_url(url):
    return _parse_douyin(url)
if bilibili.is_bilibili_url(url):
    return _parse_bilibili(url)
return _parse_with_ytdlp(url)
```

### 2.2 抖音分支（零 cookies / 零 ffmpeg）

**为何不用 yt-dlp 的 `DouyinIE`？**

- 官方抽取器请求 `www.douyin.com/aweme/v1/web/aweme/detail/`，需要 `s_v_web_id` 等 cookie 或 `a_bogus` 签名。
- 用户未登录、未在浏览器访问过抖音时，无法满足上述条件。

**自研方案**（`backend/app/platforms/douyin.py`）：

```
任意抖音 URL
    │  extract_aweme_id()：/video/、/note/、?modal_id=、v.douyin.com 短链
    ▼
GET https://www.iesdouyin.com/share/video/{aweme_id}/
    │  User-Agent：移动端 Safari（触发 SSR，非 jsvmprt 空壳）
    ▼
HTML 内嵌 _ROUTER_DATA = { ... }
    │  loaderData → video_(id)/page → videoInfoRes → item_list[0]
    ▼
item.video.play_addr.url_list[0]
    │  /playwm/ → /play/  得到无水印直链
    ▼
返回 2 个 format：douyin-nwm（无水印）、douyin-wm（兜底）
```

**下载**：`_run_douyin_download` 用标准库 `urllib.request` 流式写入 `downloads/{job_id}/{title}.mp4`，通过 `jobs.update` 上报进度。视频已是音画合一的 mp4，**不需要 ffmpeg**。

**支持的 URL 形态**

| 形态 | 示例 |
|------|------|
| 视频页 | `https://www.douyin.com/video/7630823840629022577` |
| 收藏夹弹窗 | `https://www.douyin.com/user/self?modal_id=7630823840629022577&showTab=...` |
| 笔记 | `https://www.douyin.com/note/{id}` |
| 分享页 | `https://www.iesdouyin.com/share/video/{id}/` |
| 短链 | `https://v.douyin.com/xxxxx/`（自动跟随 302） |

### 2.3 B 站分支（零 cookies / 需 ffmpeg 合并）

**为何自研？**

- 不向用户索要 `cookies.txt`；与抖音一样「粘贴即用」。
- 可控合并与 macOS QuickTime 兼容（见 `mp4_compat.py`）。

**流程**（`backend/app/platforms/bilibili.py`）：

```
BV/av/b23.tv URL
    │  extract_bvid()：保留 BV 大小写（仅规范前缀 BV）
    ▼
GET x/web-interface/view?bvid=…  →  cid、标题、封面
    ▼
WBI nav → 签名 → x/player/wbi/playurl（try_look=1, fnval=16|4048）
    ▼
DASH video[] + audio[]  →  按高度去重，优先 avc1(H.264)
    ▼
下载：urllib 拉 video.m4s + audio.m4s → ffmpeg copy 合并 → ensure_quicktime_compatible
```

**注意**

- BV 号**大小写敏感**；`BV1abc` 与 `BV1ABC` 可能是不同稿件。
- 游客权限下常见最高 **480p**；网页端更高画质多为登录/大会员流，接口不一定返回。

### 2.4 通用分支（yt-dlp）

YouTube、TikTok 等由 yt-dlp 负责元数据与多格式列表。

**ffmpeg 用途**：许多站点将高清视频流与音频流分离（DASH），需合并为可播放 mp4。

**ffmpeg 解析顺序**（`ffmpeg_check.py`）：

1. 系统 `PATH` 中的 `ffmpeg`（若用户已 `brew install`）
2. `imageio-ffmpeg` 包内预编译静态二进制（`pip install` 时自动下载）

yt-dlp 通过 `ffmpeg_location` 指向上述路径。无 ffmpeg 时：解析结果会过滤掉 `video-only` 格式，仅保留已合流或纯音频。

---

## 3. 目录与模块职责

```
backend/app/
├── main.py              # FastAPI 路由、CORS、错误友好化
├── downloader.py        # 解析/下载编排、yt-dlp 与抖音分支、进度回调
├── jobs.py              # 线程安全内存 Job 表
├── schemas.py           # Pydantic 请求/响应模型
├── ffmpeg_check.py      # ffmpeg 路径探测（系统 + imageio-ffmpeg）
├── url_normalizer.py    # 非抖音专有的 URL 预处理（modal_id → /video/）
├── mp4_compat.py        # 合并后 QuickTime 兼容、H.264 优选
└── platforms/
    ├── douyin.py        # 抖音 iesdouyin 分享页解析
    └── bilibili.py      # B 站 WBI playurl + DASH 解析
```

| 前端组件 | 职责 |
|----------|------|
| `HeroSection.vue` | 粘贴框、解析请求 |
| `VideoResultCard.vue` | 格式选择、VIP 锁（height>720）、发起下载 |
| `DownloadQueue.vue` | 轮询 progress、触发 `/api/file` 保存 |

---

## 4. HTTP 接口契约

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/parse` | Body: `{ "url": "..." }` → 视频元信息 + `formats[]` + `ffmpeg_available` |
| `POST` | `/api/download` | Body: `{ "url", "format_id?", "audio_only?" }` → `{ "job_id" }` |
| `GET` | `/api/progress/{job_id}` | `status`: `queued` \| `downloading` \| `processing` \| `finished` \| `error` |
| `GET` | `/api/file/{job_id}` | 文件流；响应后 `BackgroundTasks` 清理 job 目录 |
| `GET` | `/api/health` | `{ "ok": true, "ffmpeg": { "available", "path", "hint" } }` |

**`ParseResponse` 关键字段**

- `formats[].format_id`：下载时原样传回 `POST /api/download`
- `formats[].is_video_only` / `is_audio_only`：前端筛选项
- `ffmpeg_available`：宿主机是否具备合并能力（抖音直链场景下对用户无感）

---

## 5. 平台能力矩阵（当前）

| 平台 | 解析引擎 | 需 ffmpeg | 需用户 cookies | 备注 |
|------|----------|-----------|----------------|------|
| **抖音** | `platforms/douyin` | 否 | 否 | 无水印 + 带水印两档；原画质单档 |
| **B 站** | `platforms/bilibili` | 是 | 否 | DASH 合并；游客常见 480p/360p |
| YouTube 等 | yt-dlp | 是（高清） | 视地区/年龄限制 | 跟随 yt-dlp 上游 |
| 小红书等 | yt-dlp | 视格式 | 部分需登录 | 未单独实现直采 |

---

## 6. 运维与扩展

### 6.1 本地启动

```bash
# 后端
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # 含 imageio-ffmpeg，首次会拉静态 ffmpeg
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload \
  --app-dir "$(pwd)"

# 前端
cd frontend && npm install && npm run dev
```

国内 pip 慢可加镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple`

### 6.2 B 站解析失效时排查

1. 确认链接中 **BV 号与浏览器地址栏完全一致**（勿改大小写）。
2. `curl /api/health` 确认 `ffmpeg.available` 为 true。
3. 若仅返回音频轨：检查是否安装 `imageio-ffmpeg`（`pip install -r requirements.txt`）。
4. 接口「啥都木有」：多为 BV 错误或稿件已删除。

### 6.3 抖音解析失效时排查

1. 用移动端 UA 请求 `iesdouyin.com/share/video/{id}/`，确认 HTML 仍含 `_ROUTER_DATA`。
2. 若改为纯 CSR / 空壳，需更新 `douyin.py` 中 JSON 路径或换入口。
3. 若 CDN 直链 403，检查 `Referer: https://www.douyin.com/` 是否仍有效。

### 6.4 新增「自研平台」的建议步骤

1. 在 `backend/app/platforms/` 新增 `{platform}.py`，实现 `is_*_url(url)` + `fetch(url) -> (meta, formats)`。
2. 在 `downloader.parse_video` / `_run_download` 增加路由分支。
3. 若返回格式含 `_direct_url`，下载可走 urllib 直拉，避免 ffmpeg。
4. 更新本文「平台能力矩阵」与 `DELIVERY.md` 验收用例。

---

## 7. 已知限制

| 项 | 说明 |
|----|------|
| 抖音 JSON 结构 | 依赖 `_ROUTER_DATA` 字段路径，抖音前端大版本升级时需维护 |
| CDN 签名时效 | 直链含时效参数，解析缓存（`_DOUYIN_PLAN_CACHE`）过期后会自动再解析 |
| 内存 Job | 进程重启任务丢失 |
| VIP / 支付 | 纯前端占位，后端未校验 |
| 抖音无多清晰度 | 仅原画质；`height=None` 避免误触 VIP 锁 |

---

## 8. 相关文档

- [`README.md`](../README.md) — 快速上手
- [`DELIVERY.md`](DELIVERY.md) — 功能清单与验收步骤
- [`CHANGELOG.md`](CHANGELOG.md) — 版本与补丁记录
