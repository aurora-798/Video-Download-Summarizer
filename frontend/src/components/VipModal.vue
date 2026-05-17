<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  open: Boolean,
  reason: { type: String, default: '' },
})
const emit = defineEmits(['update:open'])

const email = ref('')
const submitted = ref(false)

watch(
  () => props.open,
  (v) => {
    if (v) {
      submitted.value = false
      email.value = ''
    }
  }
)

function close() {
  emit('update:open', false)
}
function submit() {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    alert('请输入正确的邮箱')
    return
  }
  // MVP: just simulate success and stash in localStorage for "lead capture"
  try {
    const list = JSON.parse(localStorage.getItem('vidgrab_leads') || '[]')
    list.push({ email: email.value, at: Date.now(), reason: props.reason })
    localStorage.setItem('vidgrab_leads', JSON.stringify(list))
  } catch {}
  submitted.value = true
}
</script>

<template>
  <transition name="fade">
    <div v-if="open" class="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/50 backdrop-blur-sm p-3 md:p-6" @click.self="close">
      <div class="w-full max-w-lg rounded-3xl bg-white shadow-2xl overflow-hidden">
        <!-- header banner -->
        <div class="relative bg-vip-grad text-white px-6 py-7 md:py-8">
          <button class="absolute top-3 right-3 text-white/80 hover:text-white" @click="close" aria-label="关闭">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
          <div class="flex items-center gap-3">
            <span class="inline-flex h-12 w-12 rounded-2xl bg-white/20 items-center justify-center text-2xl">👑</span>
            <div>
              <h3 class="font-extrabold text-xl md:text-2xl">VIP 即将开启</h3>
              <p class="text-sm text-white/90 mt-0.5">{{ reason || '解锁全部高级功能' }}</p>
            </div>
          </div>
        </div>

        <div class="p-6 md:p-7">
          <template v-if="!submitted">
            <p class="text-sm text-slate-600 leading-relaxed">
              在线付费通道正在接入中（支付宝 / 微信 / 信用卡），
              留下你的邮箱，我们 <b class="text-vip-600">上线即送你 7 天免费 VIP</b>，并额外赠送 5 次 4K 下载额度。
            </p>

            <div class="mt-5 flex flex-col sm:flex-row gap-2">
              <input
                v-model="email"
                type="email"
                placeholder="your@email.com"
                class="flex-1 rounded-full bg-slate-50 ring-1 ring-slate-200 px-5 py-3 text-sm outline-none focus:ring-vip-400 focus:bg-white"
              />
              <button class="btn-vip whitespace-nowrap" @click="submit">
                立即占座
              </button>
            </div>

            <ul class="mt-6 space-y-2 text-sm text-slate-600">
              <li class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                4K / 8K 原画质保存
              </li>
              <li class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                无限批量并发下载
              </li>
              <li class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                AI 视频总结 / 字幕翻译
              </li>
              <li class="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                优先客服 7×24 支持
              </li>
            </ul>
          </template>

          <template v-else>
            <div class="text-center py-4">
              <div class="mx-auto h-14 w-14 rounded-full bg-emerald-100 text-emerald-600 grid place-items-center">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
              <h4 class="mt-4 text-lg font-bold">已为你预留 VIP 名额 🎉</h4>
              <p class="mt-2 text-sm text-slate-500">
                我们会通过 <b>{{ email }}</b> 第一时间通知你上线消息。
              </p>
              <button class="btn-primary mt-6" @click="close">先回去逛逛</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
