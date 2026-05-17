<script setup>
import { ref } from 'vue'

const faqs = ref([
  {
    q: '为什么 VidGrabPro 能下载这么多平台的视频？',
    a: '我们自研了通用视频解析引擎，深度适配了主流 1000+ 视频平台，并由专业团队每日跟进平台改版，保证可用性。整个流程不依赖你登录或安装任何客户端，粘贴链接即用。',
    open: true,
  },
  {
    q: '下载下来的视频会保存在你们的服务器上吗？',
    a: '不会。视频在你按下"立即下载"后，由后端临时下载到本地缓存，传给你的浏览器后立即清理。我们既不存档，也不索引，更不会监控你下载了什么。',
    open: false,
  },
  {
    q: '免费用户和 VIP 的区别？',
    a: '免费版限制最高 720p、每日 5 次、单条下载；VIP 解锁 4K/8K、无限批量、AI 视频总结与字幕翻译（即将上线）、去广告、优先客服。',
    open: false,
  },
  {
    q: '手机上能用吗？要不要装 App？',
    a: '完美适配手机浏览器（iOS Safari / 安卓 Chrome / 微信内置浏览器都行），无需安装任何 App，粘贴链接即可下载到手机相册。',
    open: false,
  },
  {
    q: '下载失败了怎么办？',
    a: '常见原因：1) 链接需要登录（试试公开链接）；2) 视频平台临时改版（我们的引擎一般会在 24 小时内适配恢复）；3) 网络环境不稳定，刷新重试即可。VIP 用户可以一键联系客服优先处理。',
    open: false,
  },
])

function toggle(i) {
  faqs.value[i].open = !faqs.value[i].open
}
</script>

<template>
  <section id="faq" class="relative py-20 md:py-28 bg-white">
    <div class="max-w-3xl mx-auto px-4 md:px-8">
      <div class="text-center">
        <span class="inline-block text-xs font-semibold tracking-widest text-brand-600 uppercase">FAQ</span>
        <h2 class="mt-3 text-3xl md:text-4xl font-extrabold">常见问题</h2>
      </div>

      <div class="mt-10 space-y-3">
        <div
          v-for="(f, i) in faqs"
          :key="i"
          class="card overflow-hidden"
        >
          <button
            class="w-full flex items-center justify-between gap-4 text-left px-5 py-4 md:px-6 md:py-5 hover:bg-slate-50/70 transition"
            @click="toggle(i)"
          >
            <span class="font-semibold text-ink">{{ f.q }}</span>
            <svg
              :class="['text-slate-400 transition-transform', f.open ? 'rotate-180' : '']"
              width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          <div v-show="f.open" class="px-5 md:px-6 pb-5 text-sm text-slate-600 leading-relaxed">
            {{ f.a }}
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
