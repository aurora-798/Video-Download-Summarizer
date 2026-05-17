<script setup>
import { ref, computed } from 'vue'
import { parseVideo } from '../api'

const props = defineProps({
  parsing: Boolean,
  parsed: Object,
  error: String,
})
const emit = defineEmits(['update:parsing', 'update:parsed', 'update:error'])

const url = ref('')
const platforms = [
  { name: 'YouTube', tone: 'bg-red-400/70' },
  { name: 'Bilibili', tone: 'bg-pink-400/70' },
  { name: '抖音', tone: 'bg-stone-500/70' },
  { name: 'TikTok', tone: 'bg-stone-600/70' },
  { name: '小红书', tone: 'bg-rose-400/70' },
  { name: 'X', tone: 'bg-stone-500/70' },
  { name: 'Instagram', tone: 'bg-fuchsia-400/70' },
  { name: '微博', tone: 'bg-orange-400/70' },
]

const canSubmit = computed(() => url.value.trim().length > 4 && !props.parsing)

async function onParse() {
  if (!canSubmit.value) return
  emit('update:error', '')
  emit('update:parsed', null)
  emit('update:parsing', true)
  try {
    const data = await parseVideo(url.value.trim())
    emit('update:parsed', data)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '未知错误'
    emit('update:error', msg)
  } finally {
    emit('update:parsing', false)
  }
}

async function onPasteAndParse() {
  try {
    const text = await navigator.clipboard.readText()
    if (text && /^https?:\/\//i.test(text.trim())) {
      url.value = text.trim()
      onParse()
    } else {
      url.value = text || ''
    }
  } catch {
    /* clipboard permission denied */
  }
}
</script>

<template>
  <section class="relative overflow-hidden bg-hero-grad paper-grain pb-24 md:pb-32">
    <div class="absolute inset-0 bg-paper-texture opacity-40 pointer-events-none" />

    <div class="absolute -top-32 left-1/2 -translate-x-1/2 w-[min(900px,90vw)] h-64 rounded-full bg-brand-100/50 blur-3xl pointer-events-none" />
    <div class="absolute bottom-0 right-0 w-72 h-72 rounded-full bg-accent-400/15 blur-3xl pointer-events-none" />

    <div class="relative max-w-3xl mx-auto px-4 md:px-8 pt-20 md:pt-28 text-center">
      <p class="divider-ornament font-serif">
        <span>览影知意</span>
      </p>

      <h1 class="mt-8 font-serif font-semibold tracking-wide text-4xl md:text-[2.75rem] leading-[1.35] text-ink">
        粘贴链接，<span class="text-grad">静候一方笔记</span>
      </h1>

      <p class="mt-6 text-base md:text-lg text-muted leading-relaxed max-w-xl mx-auto font-light">
        万能下载与 AI 结构化总结 — 支持主流平台，字幕优先、语音兜底，助你快速把握视频要义。
      </p>

      <form @submit.prevent="onParse" class="mt-12 mx-auto max-w-2xl">
        <div class="flex flex-col md:flex-row items-stretch gap-3 md:gap-0 bg-white/85 backdrop-blur-md rounded-2xl md:rounded-full shadow-soft ring-1 ring-[#E5DDD2] p-2 md:pl-6 md:pr-2">
          <div class="flex-1 flex items-center gap-3 min-w-0">
            <svg class="hidden md:block shrink-0 text-brand-400" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 10a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            <input
              v-model="url"
              type="url"
              placeholder="粘贴视频链接，如 bilibili.com/video/BV…"
              class="w-full bg-transparent py-3.5 md:py-4 text-sm md:text-[15px] text-ink placeholder:text-brand-300 outline-none font-light"
              :disabled="parsing"
            />
          </div>
          <div class="flex gap-2 shrink-0">
            <button type="button" class="btn-ghost !text-xs md:!text-sm" @click="onPasteAndParse" :disabled="parsing">
              粘贴
            </button>
            <button type="submit" class="btn-primary !px-6 !py-3" :disabled="!canSubmit">
              <span v-if="!parsing">开始解析</span>
              <span v-else class="flex items-center gap-2">
                <span class="inline-block h-3.5 w-3.5 rounded-full border-2 border-white/50 border-t-transparent animate-spin"></span>
                解析中
              </span>
            </button>
          </div>
        </div>
      </form>

      <div class="mt-10 flex flex-wrap items-center justify-center gap-2">
        <span class="text-[11px] text-brand-400 tracking-widest uppercase mr-1">平台</span>
        <span
          v-for="p in platforms"
          :key="p.name"
          class="chip !py-1 !px-3"
          @click="url = 'https://'; document.querySelector('input[type=url]')?.focus()"
        >
          <span class="h-1 w-1 rounded-full" :class="p.tone"></span>
          {{ p.name }}
        </span>
      </div>
    </div>
  </section>
</template>
