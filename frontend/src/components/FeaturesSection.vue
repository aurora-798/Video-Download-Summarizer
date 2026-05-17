<script setup>
const features = [
  {
    title: '1000+ 平台全覆盖',
    desc: 'YouTube / Bilibili / 抖音 / TikTok / 小红书 / X / Instagram 等主流站点全部支持，持续扩展。',
    grad: 'from-brand-500 to-accent-500',
    icon: 'M3 6h18M3 12h18M3 18h18',
  },
  {
    title: '极速并发引擎',
    desc: '自研多分片并发下载引擎，跑满本地带宽，告别"30 KB/s"折磨，10MB/s 起飞。',
    grad: 'from-amber-400 to-orange-500',
    icon: 'M13 2L3 14h7l-1 8 10-12h-7l1-8z',
  },
  {
    title: '4K · 8K 高清画质',
    desc: '原画无损保存，告别压缩劣化。视频与音频流自动合并，开箱即享影院级体验。',
    grad: 'from-fuchsia-500 to-pink-500',
    icon: 'M4 4h16v12H4zM2 20h20',
  },
  {
    title: '批量队列下载',
    desc: '一次粘贴多个链接，按优先级排队执行；下班回家时一切已经妥妥躺在硬盘里。',
    grad: 'from-emerald-400 to-teal-500',
    icon: 'M4 6h16M4 12h10M4 18h16',
  },
  {
    title: '手机也能下载',
    desc: '完美响应式，在 iPhone Safari / 安卓 Chrome / 微信内置浏览器都能用，无需任何 App。',
    grad: 'from-sky-400 to-cyan-500',
    icon: 'M7 2h10v20H7zM11 18h2',
  },
  {
    title: '无水印 · 仅音频',
    desc: '一键去除平台水印；支持只提取音频导出为 MP3，做听书 / 学英语 / 剪混音都方便。',
    grad: 'from-indigo-500 to-purple-500',
    icon: 'M9 18V5l12-2v13M6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6zM18 19a3 3 0 1 1 0-6 3 3 0 0 1 0 6z',
  },
]
</script>

<template>
  <section id="features" class="relative py-20 md:py-28 bg-[#FAF7F2]">
    <div class="max-w-6xl mx-auto px-4 md:px-8">
      <div class="text-center max-w-2xl mx-auto">
        <span class="inline-block text-xs font-medium tracking-[0.2em] text-brand-500 uppercase">Features</span>
        <h2 class="mt-3 text-3xl md:text-4xl font-serif font-semibold text-ink">
          为何选择 <span class="text-grad">VidGrabPro</span>
        </h2>
        <p class="mt-4 text-muted text-base font-light leading-relaxed">
          全网视频"一粘即下"的最简单方式，没有套路、没有水印、没有 App。
        </p>
      </div>

      <div class="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        <div
          v-for="f in features"
          :key="f.title"
          class="group relative card p-6 hover:shadow-hover hover:-translate-y-1 transition"
        >
          <div
            class="h-12 w-12 rounded-2xl text-white grid place-items-center shadow-soft bg-gradient-to-br"
            :class="f.grad"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path :d="f.icon"/>
            </svg>
          </div>
          <h3 class="mt-5 text-lg font-bold">{{ f.title }}</h3>
          <p class="mt-2 text-sm text-slate-500 leading-relaxed">{{ f.desc }}</p>
        </div>
      </div>
    </div>
  </section>
</template>
