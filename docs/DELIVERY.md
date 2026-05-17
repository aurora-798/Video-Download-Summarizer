# 交付报告 · VidGrabPro

> **当前版本**：0.1.2（2026-05-18）  
> **范围**：MVP — 解析 / 下载 / 队列 / VIP 前端付费墙  
> **架构说明**：[`ARCHITECTURE.md`](ARCHITECTURE.md) · **变更记录**：[`CHANGELOG.md`](CHANGELOG.md)

---

## 一、已完成功能清单

### 后端

- [x] `POST /api/parse` — 解析 URL，返回元信息与格式列表
- [x] `POST /api/download` — 后台下载，返回 `job_id`
- [x] `GET /api/progress/{job_id}` — 进度（`queued` → `downloading` → `processing` → `finished` / `error`）
- [x] `GET /api/file/{job_id}` — 流式下发文件并清理临时目录
- [x] `GET /api/health` — `{ ok, ffmpeg }` 状态
- [x] **抖音自研解析** — `platforms/douyin.py`，无 cookies / 无 ffmpeg / 无水印选项
- [x] **通用站点** — yt-dlp + `imageio-ffmpeg` 静态合并
- [x] 错误中文化 — `_friendly_error`，不向终端用户索要安装步骤

### 前端

- [x] 首屏：渐变标题、胶囊粘贴框、平台 chips、一键粘贴
- [x] `VideoResultCard`：封面、清晰度、VIP 锁（>720p）、双 CTA
- [x] `DownloadQueue`：进度条、速度/ETA、「保存到本地」
- [x] `PricingSection` / `VipModal`：三档价格、邮箱占座
- [x] 响应式：移动端胶囊上下布局、模态底部抽屉

### 工程文档

- [x] `README.md` — 快速上手
- [x] `docs/ARCHITECTURE.md` — 架构与扩展
- [x] `docs/CHANGELOG.md` — 版本记录
- [x] 本文件 — 验收与路线图

---

## 二、人工验收步骤（约 5 分钟）

> **前置**：`pip install -r backend/requirements.txt`、`npm install`。**不需要** `brew install ffmpeg`，**不需要** 放置 `cookies.txt`。

### 启动

```bash
# 终端 1
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload

# 终端 2
cd frontend && npm run dev
```

访问 http://localhost:5173

### A. 抖音（核心回归）

- [ ] 粘贴  
  `https://www.douyin.com/user/self?modal_id=7630823840629022577&showTab=favorite_collection`  
  或任意 `/video/{id}` 链接 → **立即解析**
- [ ] 约 2–5 秒内出现视频卡：标题、作者、封面、`Douyin` 标签
- [ ] 清晰度含「无水印 · 原画质」
- [ ] **立即下载视频** → 队列进度 → 100% → **保存到本地** → 得到可播放 mp4

### B. Bilibili

- [ ] 粘贴 `https://www.bilibili.com/video/BV1GJ411x7h7/` → 解析成功
- [ ] 选择 ≤720p 或 **仅下载音频** → 下载完成并可保存

### C. UI / VIP

- [ ] 顶部「开通 VIP」、价格区按钮可打开金色模态框
- [ ] 邮箱占座后显示「已为你预留 VIP 名额」
- [ ] 开发者工具 iPhone 12 宽度下布局正常

### 命令行抽检（可选）

```bash
# 健康检查
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool

# 抖音解析
curl -s -X POST http://127.0.0.1:8765/api/parse \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.douyin.com/video/7630823840629022577"}' \
  | python3 -m json.tool | head -30
```

---

## 三、测试记录

| 用例 | 结果 | 版本 |
|------|------|------|
| `GET /api/health` | ✅ | 0.1.0 |
| Bilibili 解析 + 音频下载 | ✅ | 0.1.0 |
| 抖音 `modal_id` 收藏夹 URL 解析 | ✅ | 0.1.2 |
| 抖音无水印 mp4 下载 (~12MB) | ✅ | 0.1.2 |
| 前端解析 → 队列 → 保存 | ✅ | 0.1.0+ |
| VIP 弹窗 | ✅ | 0.1.0 |

---

## 四、已知限制

| 项 | 说明 | 升级方向 |
|----|------|----------|
| 抖音 JSON 路径 | 依赖 `_ROUTER_DATA` 结构，抖音大改版需维护 `douyin.py` | 监控 + 单测夹具 |
| 无数据库 | 重启丢任务 | SQLite + 用户表 |
| VIP 未后端校验 | 前端硬编码 720p 锁 | JWT + 额度 API |
| 无真支付 | 邮箱占座 | 微信/支付宝/Stripe |
| 小红书等 | 仍走 yt-dlp，部分需登录 | 按需加 `platforms/` 直采 |
| Job / 文件 | 内存 + 临时目录 | OSS + 下载历史 |

---

## 五、关键文件速查

| 文件 | 职责 |
|------|------|
| [`backend/app/main.py`](../backend/app/main.py) | 路由入口 |
| [`backend/app/downloader.py`](../backend/app/downloader.py) | 平台路由、yt-dlp / 抖音下载 |
| [`backend/app/platforms/douyin.py`](../backend/app/platforms/douyin.py) | 抖音 iesdouyin 解析 |
| [`backend/app/ffmpeg_check.py`](../backend/app/ffmpeg_check.py) | ffmpeg 路径 |
| [`backend/app/jobs.py`](../backend/app/jobs.py) | Job 状态机 |
| [`frontend/src/components/HeroSection.vue`](../frontend/src/components/HeroSection.vue) | 粘贴与解析 |
| [`frontend/src/components/VideoResultCard.vue`](../frontend/src/components/VideoResultCard.vue) | 结果卡与下载 |
| [`frontend/src/components/DownloadQueue.vue`](../frontend/src/components/DownloadQueue.vue) | 进度与保存 |

---

## 六、后续路线（优先级）

### P0 · 商业化

1. 微信扫码登录 + JWT  
2. 支付宝 / 微信 H5 / Stripe  
3. 后端 VIP 校验（720p、日次数、并发）

### P1 · 体验

4. 批量粘贴多 URL  
5. 下载历史（仅元数据）  
6. 暗色模式

### P2 · 溢价

7. AI 摘要（Whisper + LLM）  
8. 字幕翻译导出 SRT  
9. 云端转码 + OSS

### P3 · 工程

10. Docker Compose（含静态 ffmpeg）  
11. 限流 + Turnstile  
12. i18n

---

## 七、历史补丁（摘要）

完整记录见 [`CHANGELOG.md`](CHANGELOG.md)。

| 版本 | 要点 |
|------|------|
| **0.1.2** | 抖音 iesdouyin 直采；`imageio-ffmpeg`；取消用户侧 ffmpeg/cookies 操作 |
| **0.1.1** | URL 规范化、`ffmpeg_available`、错误中文化（cookies 方案已由 0.1.2 替代） |
| **0.1.0** | MVP 首发，Bilibili 验收通过 |
