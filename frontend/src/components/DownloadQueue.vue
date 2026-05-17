<script setup>
import { onMounted, onUnmounted, reactive, watch } from 'vue'
import { getProgress, fileUrl } from '../api'

const props = defineProps({
  jobs: { type: Array, required: true },
})
defineEmits(['open-vip'])

// Reactive job-level progress map: { [jobId]: { status, percent, ... } }
const progress = reactive({})

let timer = null

async function pollOnce() {
  await Promise.all(
    props.jobs.map(async (j) => {
      const cur = progress[j.jobId]
      if (cur && (cur.status === 'finished' || cur.status === 'error' || cur.status === 'downloaded')) {
        return
      }
      try {
        const data = await getProgress(j.jobId)
        progress[j.jobId] = data
      } catch (e) {
        progress[j.jobId] = {
          status: 'error',
          error: e?.response?.data?.detail || e.message,
        }
      }
    })
  )
}

onMounted(() => {
  pollOnce()
  timer = setInterval(pollOnce, 1000)
})
onUnmounted(() => clearInterval(timer))

watch(
  () => props.jobs.length,
  () => pollOnce()
)

function fmtSpeed(s) {
  if (!s) return ''
  if (s > 1024 * 1024) return (s / 1024 / 1024).toFixed(2) + ' MB/s'
  if (s > 1024) return (s / 1024).toFixed(1) + ' KB/s'
  return s.toFixed(0) + ' B/s'
}
function fmtETA(s) {
  if (!s && s !== 0) return ''
  if (s < 60) return s + ' 秒'
  if (s < 3600) return Math.floor(s / 60) + ' 分'
  return Math.floor(s / 3600) + ' 小时'
}
function statusLabel(p) {
  if (!p) return '排队中'
  switch (p.status) {
    case 'queued':
      return '排队中'
    case 'downloading':
      return '下载中'
    case 'processing':
      return '合并处理中'
    case 'finished':
      return '已完成'
    case 'downloaded':
      return '已保存'
    case 'error':
      return '失败'
    default:
      return p.status
  }
}
function statusColor(p) {
  switch (p?.status) {
    case 'finished':
    case 'downloaded':
      return 'bg-emerald-500'
    case 'error':
      return 'bg-red-500'
    case 'processing':
      return 'bg-vip-500'
    default:
      return 'bg-cta-grad'
  }
}

function saveFile(j) {
  // Trigger native browser download. Backend cleans up after sending.
  const a = document.createElement('a')
  a.href = fileUrl(j.jobId)
  a.download = ''
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Mark as "downloaded" locally so we hide the button
  if (progress[j.jobId]) progress[j.jobId].status = 'downloaded'
}
</script>

<template>
  <div class="card p-5 md:p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-bold text-lg flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-brand-500">
          <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/>
        </svg>
        下载队列
        <span class="text-xs font-normal text-slate-400 ml-1">({{ jobs.length }})</span>
      </h3>
      <button class="text-xs text-vip-600 hover:underline" @click="$emit('open-vip')">
        想要批量并发更快？开通 VIP →
      </button>
    </div>

    <ul class="space-y-3">
      <li v-for="j in jobs" :key="j.jobId" class="flex items-center gap-4 rounded-xl bg-slate-50 ring-1 ring-slate-100 p-3 md:p-4">
        <img
          v-if="j.thumbnail"
          :src="j.thumbnail"
          referrerpolicy="no-referrer"
          class="hidden sm:block w-20 h-12 rounded-md object-cover ring-1 ring-slate-200 shrink-0"
          alt=""
        />
        <div class="flex-1 min-w-0">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-medium text-ink truncate">{{ j.title }}</p>
              <p class="text-xs text-slate-500 mt-0.5">
                {{ j.formatLabel }}
                <span class="ml-2">· {{ statusLabel(progress[j.jobId]) }}</span>
              </p>
            </div>
            <button
              v-if="progress[j.jobId]?.status === 'finished'"
              class="btn-primary !py-2 !px-4 text-xs whitespace-nowrap"
              @click="saveFile(j)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              保存到本地
            </button>
            <span
              v-else-if="progress[j.jobId]?.status === 'downloaded'"
              class="text-xs text-emerald-600 font-medium whitespace-nowrap flex items-center gap-1"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              已保存
            </span>
          </div>

          <div class="mt-2 h-1.5 w-full rounded-full bg-slate-200 overflow-hidden">
            <div
              class="h-full transition-all duration-300"
              :class="statusColor(progress[j.jobId])"
              :style="{ width: (progress[j.jobId]?.percent || 0) + '%' }"
            ></div>
          </div>
          <div class="mt-1.5 flex items-center justify-between text-xs text-slate-400">
            <span>{{ (progress[j.jobId]?.percent || 0).toFixed(1) }}%</span>
            <span v-if="progress[j.jobId]?.speed">
              {{ fmtSpeed(progress[j.jobId].speed) }}
              <span v-if="progress[j.jobId].eta" class="ml-1">· 剩 {{ fmtETA(progress[j.jobId].eta) }}</span>
            </span>
            <span v-if="progress[j.jobId]?.error" class="text-red-500 truncate max-w-[60%]" :title="progress[j.jobId].error">
              {{ progress[j.jobId].error }}
            </span>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
