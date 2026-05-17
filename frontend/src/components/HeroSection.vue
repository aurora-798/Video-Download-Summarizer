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
  { name: 'YouTube', color: 'text-red-500' },
  { name: 'Bilibili', color: 'text-pink-500' },
  { name: '抖音', color: 'text-slate-800' },
  { name: 'TikTok', color: 'text-slate-800' },
  { name: '小红书', color: 'text-red-500' },
  { name: 'X / Twitter', color: 'text-slate-800' },
  { name: 'Instagram', color: 'text-fuchsia-500' },
  { name: '微博', color: 'text-orange-500' },
  { name: 'Facebook', color: 'text-blue-600' },
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
  <section class="relative overflow-hidden bg-hero-grad pb-20 md:pb-28">
    <div class="absolute inset-0 dot-grid opacity-60 pointer-events-none"></div>

    <div class="absolute -top-20 -left-20 h-72 w-72 rounded-full bg-brand-200/40 blur-3xl pointer-events-none"></div>
    <div class="absolute top-20 -right-24 h-80 w-80 rounded-full bg-accent-400/30 blur-3xl pointer-events-none"></div>

    <div class="relative max-w-5xl mx-auto px-4 md:px-8 pt-16 md:pt-24 text-center">
      <div class="inline-flex items-center gap-2 rounded-full bg-white/70 backdrop-blur px-4 py-1.5 text-xs font-medium text-brand-700 ring-1 ring-brand-100 shadow-soft">
        <span class="inline-block h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse"></span>
        已稳定服务 10w+ 用户 · 每日更新平台适配
      </div>

      <h1 class="mt-6 font-extrabold tracking-tight text-4xl md:text-6xl leading-tight">
        <span class="text-grad">万能视频下载</span>
        <span class="text-ink">， 一粘即下</span>
      </h1>
      <p class="mt-5 text-base md:text-xl text-slate-500 max-w-2xl mx-auto">
        支持 <b class="text-ink">1000+</b> 平台 · 4K/8K 高清 · 批量并发 · 手机也能用 · 无水印
      </p>

      <form @submit.prevent="onParse" class="mt-10 mx-auto max-w-3xl">
        <div class="flex flex-col md:flex-row items-stretch gap-3 md:gap-2 bg-white rounded-3xl md:rounded-full shadow-soft ring-1 ring-slate-100 p-2 md:pl-6">
          <div class="flex-1 flex items-center gap-3">
            <svg class="hidden md:block text-slate-400" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 14a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 10a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            <input
              v-model="url"
              type="url"
              placeholder="粘贴视频链接，如：https://www.bilibili.com/video/BVxxxx"
              class="w-full bg-transparent py-3 md:py-4 text-sm md:text-base placeholder-slate-400 outline-none"
              :disabled="parsing"
            />
          </div>
          <div class="flex gap-2">
            <button
              type="button"
              class="btn-ghost shrink-0"
              @click="onPasteAndParse"
              :disabled="parsing"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="8" y="2" width="8" height="4" rx="1"/>
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
              </svg>
              粘贴
            </button>
            <button
              type="submit"
              class="btn-primary shrink-0 !px-7 !py-3 md:!py-3.5"
              :disabled="!canSubmit"
            >
              <span v-if="!parsing">立即解析</span>
              <span v-else class="flex items-center gap-2">
                <span class="inline-block h-4 w-4 rounded-full border-2 border-white/60 border-t-transparent animate-spin"></span>
                解析中…
              </span>
            </button>
          </div>
        </div>
      </form>

      <div class="mt-8 flex flex-wrap items-center justify-center gap-2 text-slate-500">
        <span class="text-xs mr-1">热门平台：</span>
        <span
          v-for="p in platforms"
          :key="p.name"
          class="chip"
          @click="url = 'https://'; document.querySelector('input[type=url]')?.focus()"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-current" :class="p.color"></span>
          {{ p.name }}
        </span>
      </div>
    </div>
  </section>
</template>
