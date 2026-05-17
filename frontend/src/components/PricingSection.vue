<script setup>
const emit = defineEmits(['open-vip'])

const free = {
  title: '免费体验',
  price: '0',
  unit: '永久',
  badge: '',
  features: [
    { ok: true, text: '单视频下载，无需注册' },
    { ok: true, text: '最高 720p 清晰度' },
    { ok: true, text: '每日 5 次下载额度' },
    { ok: true, text: '基础平台覆盖（500+）' },
    { ok: false, text: '4K / 8K 超清画质' },
    { ok: false, text: '批量并发 / 队列优先' },
    { ok: false, text: 'AI 视频总结 · 字幕翻译' },
    { ok: false, text: '去广告 / 优先客服' },
  ],
  cta: '当前已是免费版',
  vip: false,
}

const vip = {
  title: 'VIP 会员',
  price: '29',
  origPrice: '49',
  unit: '/ 月',
  badge: '最受欢迎',
  features: [
    { ok: true, text: '一切免费版功能' },
    { ok: true, text: '解锁 1080p · 4K · 8K 原画' },
    { ok: true, text: '无限批量并发下载' },
    { ok: true, text: '全部 1000+ 平台支持' },
    { ok: true, text: 'AI 视频总结（一键摘要）', soon: true },
    { ok: true, text: '字幕翻译（中英 50 国语言）', soon: true },
    { ok: true, text: '去除水印 · 去广告' },
    { ok: true, text: '7×24 优先客服' },
  ],
  cta: '立即升级 VIP',
  vip: true,
}

const yearly = {
  title: 'VIP 年卡',
  price: '198',
  origPrice: '588',
  unit: '/ 年（约 16.5/月）',
  badge: '省 66%',
  features: [
    { ok: true, text: 'VIP 全部功能' },
    { ok: true, text: '一次开通，全年畅享' },
    { ok: true, text: '赠送 200GB 云端中转空间', soon: true },
    { ok: true, text: '专属 Discord/微信群答疑' },
  ],
  cta: '抢年度大额优惠',
  vip: true,
}
</script>

<template>
  <section id="pricing" class="relative py-20 md:py-28 bg-surface">
    <div class="max-w-6xl mx-auto px-4 md:px-8">
      <div class="text-center max-w-2xl mx-auto">
        <span class="inline-block text-xs font-semibold tracking-widest text-vip-600 uppercase">Pricing</span>
        <h2 class="mt-3 text-3xl md:text-4xl font-extrabold">
          选择适合你的 <span class="text-grad">下载力</span>
        </h2>
        <p class="mt-4 text-slate-500 text-base">
          0 元免费体验，升级 VIP 解锁 4K/8K · 批量 · AI 总结 · 字幕翻译。
        </p>
      </div>

      <div class="mt-12 grid grid-cols-1 lg:grid-cols-3 gap-5">
        <!-- Free -->
        <div class="card p-6 md:p-8 flex flex-col">
          <h3 class="text-lg font-bold">{{ free.title }}</h3>
          <div class="mt-3 flex items-baseline gap-1">
            <span class="text-4xl font-extrabold">¥{{ free.price }}</span>
            <span class="text-slate-500 text-sm">{{ free.unit }}</span>
          </div>
          <p class="mt-1 text-xs text-slate-400">无需注册，打开就用</p>
          <ul class="mt-6 space-y-2.5 text-sm">
            <li
              v-for="(f, i) in free.features"
              :key="i"
              class="flex items-start gap-2"
              :class="f.ok ? 'text-slate-700' : 'text-slate-300 line-through'"
            >
              <span class="mt-0.5 inline-flex h-4 w-4 rounded-full items-center justify-center"
                    :class="f.ok ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-400'">
                <svg v-if="f.ok" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
                  <line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/>
                </svg>
              </span>
              <span>{{ f.text }}</span>
            </li>
          </ul>
          <button class="btn-ghost mt-8" disabled>{{ free.cta }}</button>
        </div>

        <!-- VIP Monthly (highlighted) -->
        <div class="relative card p-6 md:p-8 flex flex-col ring-2 ring-vip-400 shadow-vip lg:scale-[1.03]">
          <div class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-vip-grad text-white text-xs font-bold shadow-soft">
            👑 {{ vip.badge }}
          </div>
          <h3 class="text-lg font-bold text-vip-700">{{ vip.title }}</h3>
          <div class="mt-3 flex items-baseline gap-2">
            <span class="text-4xl font-extrabold">¥{{ vip.price }}</span>
            <span class="text-slate-500 text-sm">{{ vip.unit }}</span>
            <span class="text-sm text-slate-400 line-through ml-1">¥{{ vip.origPrice }}</span>
          </div>
          <p class="mt-1 text-xs text-vip-600 font-medium">限时直降 ¥20，新用户首月再 7 折</p>
          <ul class="mt-6 space-y-2.5 text-sm">
            <li v-for="(f, i) in vip.features" :key="i" class="flex items-start gap-2 text-slate-700">
              <span class="mt-0.5 inline-flex h-4 w-4 rounded-full bg-emerald-100 text-emerald-600 items-center justify-center">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </span>
              <span>
                {{ f.text }}
                <span v-if="f.soon" class="ml-1 text-[10px] align-middle text-vip-600 bg-vip-300/40 rounded px-1.5 py-0.5">即将上线</span>
              </span>
            </li>
          </ul>
          <button class="btn-vip mt-8 !py-3.5" @click="emit('open-vip')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M5 16l-2-8 6 3 3-7 3 7 6-3-2 8H5zm0 2h14v2H5v-2z"/></svg>
            {{ vip.cta }}
          </button>
        </div>

        <!-- VIP Yearly -->
        <div class="card p-6 md:p-8 flex flex-col">
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-bold">{{ yearly.title }}</h3>
            <span class="rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold px-2 py-1">{{ yearly.badge }}</span>
          </div>
          <div class="mt-3 flex items-baseline gap-2">
            <span class="text-4xl font-extrabold">¥{{ yearly.price }}</span>
            <span class="text-slate-500 text-sm">{{ yearly.unit }}</span>
          </div>
          <p class="mt-1 text-xs text-slate-400">原价 ¥{{ yearly.origPrice }}/年，限时 1/3 价</p>
          <ul class="mt-6 space-y-2.5 text-sm">
            <li v-for="(f, i) in yearly.features" :key="i" class="flex items-start gap-2 text-slate-700">
              <span class="mt-0.5 inline-flex h-4 w-4 rounded-full bg-emerald-100 text-emerald-600 items-center justify-center">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </span>
              <span>
                {{ f.text }}
                <span v-if="f.soon" class="ml-1 text-[10px] align-middle text-vip-600 bg-vip-300/40 rounded px-1.5 py-0.5">即将上线</span>
              </span>
            </li>
          </ul>
          <button class="btn-primary mt-8 !py-3.5" @click="emit('open-vip')">
            {{ yearly.cta }}
          </button>
        </div>
      </div>

      <p class="mt-8 text-center text-xs text-slate-400">
        所有套餐 7 天无理由退款 · 支持支付宝 / 微信 / 信用卡 · 实际价格以收银台为准
      </p>
    </div>
  </section>
</template>
