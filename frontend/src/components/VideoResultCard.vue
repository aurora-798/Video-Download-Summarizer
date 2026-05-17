<script setup>
import { computed, ref } from 'vue'
import { startDownload } from '../api'

const props = defineProps({
  video: { type: Object, required: true },
})
const emit = defineEmits(['download', 'open-vip', 'summarize'])

function fmtBytes(n) {
  if (!n && n !== 0) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`
}
function fmtDuration(s) {
  if (!s) return ''
  s = Math.round(s)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

function codecScore(f) {
  const v = (f.vcodec || '').toLowerCase()
  if (v.startsWith('avc') || v.includes('h264')) return 3
  if (v.startsWith('hev') || v.startsWith('hvc')) return 2
  if (v.startsWith('av01') || v.includes('av1')) return 1
  return 0
}

// Filter to a friendly list:
//  - All combined / video-only formats (we'll add bestaudio server-side)
//  - One best audio-only as the "MP3 仅音频" choice
// Prefer H.264 over HEVC/AV1 at the same resolution (QuickTime on macOS).
const videoOptions = computed(() => {
  const list = (props.video.formats || []).filter((f) => !f.is_audio_only)
  const seen = new Map()
  for (const f of list) {
    const key = `${f.height || 0}-${f.ext || ''}`
    const prev = seen.get(key)
    if (
      !prev ||
      codecScore(f) > codecScore(prev) ||
      (codecScore(f) === codecScore(prev) && (f.tbr || 0) > (prev.tbr || 0))
    ) {
      seen.set(key, f)
    }
  }
  const arr = Array.from(seen.values())
  arr.sort((a, b) => (b.height || 0) - (a.height || 0) || (b.tbr || 0) - (a.tbr || 0))
  return arr
})

const audioOption = computed(() => {
  const list = (props.video.formats || []).filter((f) => f.is_audio_only)
  if (!list.length) return null
  return list.reduce((best, f) => ((f.tbr || 0) > (best.tbr || 0) ? f : best), list[0])
})

const maxHeight = computed(() => props.video.max_height || 0)

const selectedId = ref(videoOptions.value[0]?.format_id || '')
const downloadingAudio = ref(false)
const downloading = ref(false)

const selectedFmt = computed(
  () => videoOptions.value.find((f) => f.format_id === selectedId.value) || null
)

function platformIconClass(extractor) {
  const e = (extractor || '').toLowerCase()
  if (e.includes('youtube')) return 'bg-red-500'
  if (e.includes('bili')) return 'bg-pink-500'
  if (e.includes('douyin') || e.includes('tiktok')) return 'bg-slate-800'
  if (e.includes('xiaohongshu') || e.includes('red')) return 'bg-red-500'
  if (e.includes('twitter') || e.includes('x.com')) return 'bg-slate-800'
  if (e.includes('instagram')) return 'bg-fuchsia-500'
  if (e.includes('weibo')) return 'bg-orange-500'
  return 'bg-brand-500'
}

async function onDownloadSelected() {
  if (!selectedFmt.value) return
  downloading.value = true
  try {
    const jobId = await startDownload({
      url: props.video.webpage_url,
      format_id: selectedFmt.value.format_id,
    })
    emit('download', {
      jobId,
      title: props.video.title,
      thumbnail: props.video.thumbnail,
      formatLabel: `${selectedFmt.value.height || ''}p ${(selectedFmt.value.ext || '').toUpperCase()}`,
      kind: 'video',
    })
  } catch (e) {
    alert('启动下载失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    downloading.value = false
  }
}

const mergeReady = computed(() => props.video.ffmpeg_available !== false)
const hasVideoOnlyStreams = computed(
  () => videoOptions.value.length > 0 && videoOptions.value.every((f) => f.is_video_only)
)

async function onDownloadAudio() {
  if (!audioOption.value) return
  downloadingAudio.value = true
  try {
    const jobId = await startDownload({
      url: props.video.webpage_url,
      format_id: audioOption.value.format_id,
      audio_only: true,
    })
    emit('download', {
      jobId,
      title: props.video.title,
      thumbnail: props.video.thumbnail,
      formatLabel: '仅音频 ' + (audioOption.value.ext || 'M4A').toUpperCase(),
      kind: 'audio',
    })
  } catch (e) {
    alert('启动下载失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    downloadingAudio.value = false
  }
}
</script>

<template>
  <div class="card p-5 md:p-6 lg:p-7">
    <div class="flex flex-col md:flex-row gap-5 md:gap-7">
      <!-- Thumbnail -->
      <div class="relative shrink-0 mx-auto md:mx-0">
        <img
          v-if="video.thumbnail"
          :src="video.thumbnail"
          referrerpolicy="no-referrer"
          class="w-full md:w-72 aspect-video object-cover rounded-xl ring-1 ring-slate-200"
          alt=""
        />
        <div
          v-else
          class="w-full md:w-72 aspect-video rounded-xl bg-slate-100 grid place-items-center text-slate-400"
        >
          <span class="text-sm">无缩略图</span>
        </div>
        <span
          v-if="video.duration"
          class="absolute bottom-2 right-2 rounded-md bg-black/70 text-white text-xs px-2 py-0.5"
        >
          {{ fmtDuration(video.duration) }}
        </span>
      </div>

      <!-- Info & actions -->
      <div class="flex-1 min-w-0 flex flex-col">
        <div class="flex items-start gap-2 flex-wrap">
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-white"
            :class="platformIconClass(video.extractor)"
          >
            {{ video.extractor || 'Video' }}
          </span>
          <span v-if="video.uploader" class="text-xs text-slate-500 py-1">
            👤 {{ video.uploader }}
          </span>
          <span v-if="video.view_count" class="text-xs text-slate-500 py-1">
            · 👁 {{ video.view_count.toLocaleString() }}
          </span>
        </div>

        <h3 class="mt-2 text-lg md:text-xl font-bold text-ink line-clamp-2">
          {{ video.title }}
        </h3>

        <div class="mt-5 space-y-3">
          <div v-if="videoOptions.length">
            <label class="block text-xs font-medium text-slate-500 mb-1.5">视频清晰度</label>
            <div class="relative">
              <select
                v-model="selectedId"
                class="w-full appearance-none rounded-xl bg-slate-50 ring-1 ring-slate-200 px-4 py-3 text-sm font-medium pr-9 focus:ring-brand-400 focus:bg-white outline-none"
              >
                <option
                  v-for="f in videoOptions"
                  :key="f.format_id"
                  :value="f.format_id"
                >
                  {{ f.height ? f.height + 'p' : f.resolution || f.format_id }}
                  {{ f.ext ? '· ' + f.ext.toUpperCase() : '' }}
                  {{ f.filesize ? '· ' + fmtBytes(f.filesize) : '' }}

                </option>
              </select>
              <svg class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </div>
            <p
              v-if="hasVideoOnlyStreams && mergeReady"
              class="mt-1.5 text-xs text-slate-400"
            >
              该站点为分轨画质，下载时将自动合并最佳音质。
            </p>
          </div>

          <div
            v-else-if="audioOption"
            class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
          >
            <div class="font-semibold">
              {{ mergeReady ? '该视频暂只能下载音频' : '高清视频需服务端合并组件' }}
            </div>
            <div class="mt-1 text-amber-800/80 text-xs leading-relaxed">
              <template v-if="!mergeReady">
                B 站等平台将画面与声音分轨存储，需 ffmpeg 合并后才能下载完整 MP4。请在服务器执行
                <code class="rounded bg-white/70 px-1">pip install -r requirements.txt</code>
                （含 imageio-ffmpeg）或安装系统 ffmpeg 后重启后端。
              </template>
              <template v-else>
                当前视频源未提供已合并好的单文件流，建议先用下方「仅下载音频」，或联系管理员检查合并服务。
              </template>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              v-if="videoOptions.length"
              class="btn-primary w-full !py-3.5"
              :disabled="downloading || !selectedFmt"
              @click="onDownloadSelected"
            >
              <svg v-if="!downloading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v12"/>
                <path d="M7 10l5 5 5-5"/>
                <path d="M5 21h14"/>
              </svg>
              <span v-if="!downloading">立即下载视频</span>
              <span v-else>排队中…</span>
            </button>

            <button
              v-if="audioOption"
              class="btn-ghost w-full !py-3.5"
              :class="{ 'sm:col-span-2': !videoOptions.length }"
              :disabled="downloadingAudio"
              @click="onDownloadAudio"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 18V5l12-2v13"/>
                <circle cx="6" cy="18" r="3"/>
                <circle cx="18" cy="16" r="3"/>
              </svg>
              <span>{{ downloadingAudio ? '排队中…' : '仅下载音频' }}</span>
            </button>
          </div>

          <button
            class="btn-summary w-full !py-3.5"
            @click="$emit('summarize', video)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2 L12 4"/>
              <path d="M12 20 L12 22"/>
              <path d="M4.93 4.93 L6.34 6.34"/>
              <path d="M17.66 17.66 L19.07 19.07"/>
              <path d="M2 12 L4 12"/>
              <path d="M20 12 L22 12"/>
              <circle cx="12" cy="12" r="4"/>
            </svg>
            <span>AI 一键总结 · 提取要点 / 时间线 / 思维导图</span>
          </button>

          <div
            v-if="video.hd_hint"
            class="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-xs text-sky-900 leading-relaxed"
          >
            {{ video.hd_hint }}
          </div>
          <p v-else-if="maxHeight >= 720" class="text-xs text-slate-400">
            已选择高清画质，下载时将自动合并音轨并优化 macOS 播放兼容性。
          </p>
          <p v-else class="text-xs text-slate-400">
            已自动选择当前可用的最高画质（部分视频在游客权限下最高约 480p）。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
