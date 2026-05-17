<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { marked } from 'marked'
import mermaid from 'mermaid'
import { MERMAID_CONFIG, polishMindmapSvg } from '../mermaid-theme'
import { getSummary, openSummaryStream, startSummarize } from '../api'

const props = defineProps({
  video: { type: Object, required: true },
})
const emit = defineEmits(['close'])

mermaid.initialize(MERMAID_CONFIG)

const taskId = ref('')
const stage = ref('queued')
const stageMsg = ref('准备开始…')
const percent = ref(0)
const source = ref(null)
const language = ref(null)
const summaryMd = ref('')
const errorMsg = ref('')
const finished = ref(false)
const transcript = ref([])
const showTranscript = ref(false)
const showMindmap = ref(true)
const copied = ref(false)
let es = null

const stageLabel = computed(() => {
  if (errorMsg.value) return '未能完成'
  if (finished.value) return '已成稿'
  switch (stage.value) {
    case 'queued': return '候稿中'
    case 'fetching_meta': return '识读视频'
    case 'fetching_subtitle': return '寻索字幕'
    case 'downloading_audio': return '撷取音轨'
    case 'transcribing': return '听写转录'
    case 'summarizing': return '执笔成文'
    case 'finished': return '已成稿'
    default: return stage.value
  }
})

const sourceLabel = computed(() => {
  if (source.value === 'subtitle') return '平台字幕 · 依原文'
  if (source.value === 'asr') return '语音转写 · AI 听写'
  return ''
})

const steps = [
  { key: 'fetching_meta', label: '识读' },
  { key: 'fetching_subtitle', label: '字幕' },
  { key: 'downloading_audio', label: '音轨' },
  { key: 'transcribing', label: '转写' },
  { key: 'summarizing', label: '成文' },
]

const currentStepIdx = computed(() => {
  if (finished.value) return steps.length
  if (errorMsg.value) return -1
  const idx = steps.findIndex((s) => s.key === stage.value)
  return idx >= 0 ? idx : 0
})

const rendered = computed(() => {
  if (!summaryMd.value) return { intro: '', mermaidSrc: '' }
  return splitSections(summaryMd.value)
})

watch(() => rendered.value.mermaidSrc, async (src) => {
  if (!src || !taskId.value) return
  await nextTick()
  const el = document.getElementById(`mm-${taskId.value}`)
  if (!el) return
  try {
    const { svg } = await mermaid.render(`mmsvg-${taskId.value}-${Date.now()}`, src)
    el.innerHTML = polishMindmapSvg(svg)
  } catch {
    if (el) {
      el.innerHTML = '<p class="text-sm text-brand-400 font-serif py-6 text-center">导图绘制中…</p>'
    }
  }
})

async function begin() {
  reset()
  if (!props.video?.webpage_url) {
    errorMsg.value = '缺少视频链接'
    return
  }
  try {
    taskId.value = await startSummarize(props.video.webpage_url)
  } catch (e) {
    errorMsg.value = e?.response?.data?.detail || e.message
    return
  }
  attachStream()
}

function attachStream() {
  if (es) { es.close(); es = null }
  es = openSummaryStream(taskId.value, (name, data) => {
    if (!data) return
    switch (name) {
      case 'snapshot':
        stage.value = data.stage || stage.value
        stageMsg.value = data.stage_msg || stageMsg.value
        percent.value = data.percent || 0
        source.value = data.source || source.value
        language.value = data.language || language.value
        summaryMd.value = data.summary_md || ''
        if (data.error) errorMsg.value = data.error
        if (data.stage === 'finished') finished.value = true
        break
      case 'stage':
        stage.value = data.stage || stage.value
        stageMsg.value = data.message || stageMsg.value
        if (typeof data.percent === 'number') percent.value = data.percent
        break
      case 'source':
        source.value = data.source || source.value
        language.value = data.language || language.value
        break
      case 'transcript':
        transcript.value = data.transcript || []
        break
      case 'delta':
        summaryMd.value += data.chunk || ''
        break
      case 'done':
        if (data.summary_md) summaryMd.value = data.summary_md
        finished.value = true
        stage.value = 'finished'
        stageMsg.value = '总结完成'
        percent.value = 100
        closeStream()
        break
      case 'error':
        errorMsg.value = data.error || '未知错误'
        closeStream()
        break
      case 'close':
        closeStream()
        break
      case 'connection_error':
        if (!finished.value && !errorMsg.value) pollOnce()
        break
    }
  })
}

async function pollOnce() {
  if (!taskId.value) return
  try {
    const data = await getSummary(taskId.value)
    stage.value = data.stage
    stageMsg.value = data.stage_msg
    percent.value = data.percent || 0
    source.value = data.source
    language.value = data.language
    summaryMd.value = data.summary_md || summaryMd.value
    if (data.error) errorMsg.value = data.error
    if (data.stage === 'finished') finished.value = true
  } catch {}
}

function reset() {
  taskId.value = ''
  stage.value = 'queued'
  stageMsg.value = '准备开始…'
  percent.value = 0
  source.value = null
  language.value = null
  summaryMd.value = ''
  errorMsg.value = ''
  finished.value = false
  transcript.value = []
  copied.value = false
  closeStream()
}

function closeStream() {
  if (es) { es.close(); es = null }
}

async function copyMarkdown() {
  try {
    await navigator.clipboard.writeText(summaryMd.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch {}
}

onBeforeUnmount(() => closeStream())

function splitSections(md) {
  let mermaidSrc = ''
  const intro = md.replace(/```mermaid\s*([\s\S]*?)```/i, (_, code) => {
    mermaidSrc = code.trim()
    return ''
  })
  return { intro, mermaidSrc }
}

function renderMd(src) {
  if (!src) return ''
  marked.setOptions({ breaks: true, gfm: true })
  const html = marked.parse(src)
  return html.replace(
    /\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]/g,
    (m) => `<span class="mm-ts">${m}</span>`,
  )
}

defineExpose({ begin, reset })

function fmtTs(sec) {
  const s = Math.floor(sec || 0)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}
</script>

<template>
  <article class="card-elegant overflow-hidden">
    <!-- Header -->
    <header class="px-5 md:px-7 pt-6 pb-4 border-b border-[#E5DDD2]/60 bg-gradient-to-r from-[#FAF7F2] to-white">
      <div class="flex items-start justify-between gap-4">
        <div class="flex items-start gap-3">
          <span class="inline-grid place-items-center w-10 h-10 rounded-xl bg-summary-grad text-white shadow-soft shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
              <path d="M12 20h9"/>
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
            </svg>
          </span>
          <div>
            <h3 class="font-serif text-lg md:text-xl font-semibold text-ink tracking-wide">AI 阅要</h3>
            <p class="text-xs text-muted mt-1 font-light leading-relaxed">
              字幕或听写 → 结构化笔记
              <span v-if="sourceLabel" class="text-brand-600"> · {{ sourceLabel }}</span>
              <span v-if="language" class="text-brand-400"> · {{ language }}</span>
            </p>
          </div>
        </div>
        <button
          type="button"
          class="text-xs text-brand-400 hover:text-brand-700 px-2 py-1 rounded-lg hover:bg-brand-50 transition shrink-0"
          @click="emit('close')"
        >
          收起
        </button>
      </div>
    </header>

    <div class="px-5 md:px-7 py-5 md:py-6">
      <!-- Progress -->
      <div v-if="!finished && !errorMsg" class="rounded-xl bg-[#FAF7F2] ring-1 ring-[#E5DDD2] p-4 md:p-5">
        <div class="flex items-center justify-between text-sm">
          <span class="font-serif text-brand-700">{{ stageLabel }}</span>
          <span class="text-xs text-brand-400 tabular-nums">{{ Math.round(percent) }}%</span>
        </div>
        <div class="mt-3 h-1 w-full rounded-full bg-[#E5DDD2]/80 overflow-hidden">
          <div
            class="h-full rounded-full bg-gradient-to-r from-brand-500 via-brand-400 to-accent-500 transition-all duration-500 ease-out"
            :style="{ width: percent + '%' }"
          />
        </div>
        <p class="mt-2.5 text-xs text-muted truncate font-light">{{ stageMsg }}</p>
        <ol class="mt-4 flex flex-wrap gap-2">
          <li
            v-for="(s, i) in steps"
            :key="s.key"
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] transition"
            :class="i < currentStepIdx
              ? 'bg-accent-400/20 text-accent-600 ring-1 ring-accent-400/30'
              : i === currentStepIdx
                ? 'bg-brand-100 text-brand-700 ring-1 ring-brand-300'
                : 'bg-white/60 text-brand-300 ring-1 ring-[#E5DDD2]'"
          >
            <span class="font-serif">{{ i + 1 }}</span>
            {{ s.label }}
          </li>
        </ol>
      </div>

      <!-- Error -->
      <div v-if="errorMsg" class="mt-0 rounded-xl border border-wine-400/30 bg-wine-400/5 px-4 py-4">
        <p class="font-serif text-sm text-wine-600">成稿未果</p>
        <pre class="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-muted font-mono">{{ errorMsg }}</pre>
        <button type="button" class="mt-3 btn-ghost !py-1.5 !px-3 text-xs" @click="begin">重试</button>
      </div>

      <!-- Summary body -->
      <div v-if="summaryMd && !errorMsg" class="mt-6 space-y-6">
        <div class="flex items-center justify-end gap-2">
          <span v-if="!finished" class="text-xs text-accent-600 inline-flex items-center gap-1.5 font-light">
            <span class="w-1.5 h-1.5 rounded-full bg-accent-500 animate-pulse"></span>
            执笔中
          </span>
          <button type="button" class="btn-ghost !py-1.5 !px-3 text-xs" @click="copyMarkdown">
            {{ copied ? '已复制' : '复制全文' }}
          </button>
        </div>

        <div class="prose-summary" v-html="renderMd(rendered.intro)" />

        <!-- Mindmap -->
        <div v-if="rendered.mermaidSrc" class="rounded-xl overflow-hidden ring-1 ring-[#E5DDD2] bg-[#FAF7F2]">
          <button
            type="button"
            class="w-full flex items-center justify-between px-4 py-3 text-sm font-serif text-brand-700 hover:bg-[#F3EDE4] transition"
            @click="showMindmap = !showMindmap"
          >
            <span class="inline-flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="text-accent-600">
                <circle cx="6" cy="6" r="2.5"/>
                <circle cx="6" cy="18" r="2.5"/>
                <circle cx="18" cy="12" r="2.5"/>
                <path d="M8.5 6h5a3 3 0 0 1 3 3v3"/>
                <path d="M8.5 18h5a3 3 0 0 0 3-3v-3"/>
              </svg>
              意旨导图
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-brand-400 transition" :class="{ 'rotate-180': showMindmap }">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </button>
          <div v-show="showMindmap" class="px-4 pb-5 pt-1 bg-white border-t border-[#E5DDD2]/50">
            <div :id="`mm-${taskId}`" class="mindmap-elegant flex justify-center min-h-[120px]" />
          </div>
        </div>

        <!-- Transcript -->
        <div v-if="transcript.length" class="rounded-xl overflow-hidden ring-1 ring-[#E5DDD2] bg-[#FAF7F2]">
          <button
            type="button"
            class="w-full flex items-center justify-between px-4 py-3 text-sm font-serif text-brand-700 hover:bg-[#F3EDE4] transition"
            @click="showTranscript = !showTranscript"
          >
            <span>原文脚本 <span class="text-brand-400 font-sans font-normal text-xs">（{{ transcript.length }} 段）</span></span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-brand-400 transition" :class="{ 'rotate-180': showTranscript }">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </button>
          <div v-show="showTranscript" class="max-h-72 overflow-y-auto px-4 pb-4 bg-white border-t border-[#E5DDD2]/50">
            <ul class="space-y-2 pt-2">
              <li v-for="(c, i) in transcript" :key="i" class="flex gap-3 text-sm leading-relaxed">
                <time class="shrink-0 font-mono text-[11px] text-brand-400 w-11 pt-0.5">{{ fmtTs(c.start) }}</time>
                <span class="text-ink/90 font-light">{{ c.text }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.prose-summary {
  color: #3d3832;
  line-height: 1.85;
  word-break: break-word;
  font-weight: 300;
}
.prose-summary :deep(h2) {
  font-family: 'Noto Serif SC', 'Songti SC', serif;
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 1.5rem;
  margin-bottom: 0.6rem;
  color: #2c2825;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid #e5ddd2;
  letter-spacing: 0.02em;
}
.prose-summary :deep(h2:first-child) { margin-top: 0; }
.prose-summary :deep(h3) {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.95rem;
  font-weight: 500;
  margin-top: 1rem;
  color: #6f5c45;
}
.prose-summary :deep(p) { margin: 0.5rem 0; }
.prose-summary :deep(ul),
.prose-summary :deep(ol) { padding-left: 1.35rem; margin: 0.5rem 0; }
.prose-summary :deep(li) { margin: 0.35rem 0; }
.prose-summary :deep(strong) { color: #2c2825; font-weight: 500; }
.prose-summary :deep(code) {
  background: #f3ede4;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
  color: #8b6356;
}
.prose-summary :deep(.mm-ts) {
  display: inline-block;
  background: #ede6db;
  color: #6f5c45;
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 0.35rem;
  margin-right: 0.35rem;
  vertical-align: middle;
}
</style>
