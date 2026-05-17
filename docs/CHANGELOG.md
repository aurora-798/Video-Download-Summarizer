# 更新日志

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

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
