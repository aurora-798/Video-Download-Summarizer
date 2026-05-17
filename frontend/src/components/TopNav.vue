<script setup>
const emit = defineEmits(['open-vip'])
</script>

<template>
  <header
    class="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-100"
  >
    <div class="max-w-6xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button
          aria-label="menu"
          class="md:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
            <path d="M4 7h16M4 12h16M4 17h16"/>
          </svg>
        </button>
        <a href="/" class="flex items-center gap-2">
          <span class="inline-flex h-9 w-9 rounded-xl bg-cta-grad items-center justify-center shadow-soft">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12"/>
              <path d="M7 10l5 5 5-5"/>
              <path d="M5 21h14"/>
            </svg>
          </span>
          <span class="font-extrabold text-lg tracking-tight">
            VidGrab<span class="text-grad">Pro</span>
          </span>
        </a>
      </div>

      <nav class="hidden md:flex items-center gap-7 text-sm font-medium text-slate-600">
        <a href="#features" class="hover:text-brand-600 transition">功能</a>
        <a href="#pricing" class="hover:text-brand-600 transition">价格</a>
        <a href="#faq" class="hover:text-brand-600 transition">FAQ</a>
        <a href="#" class="hover:text-brand-600 transition">帮助中心</a>
      </nav>

      <div class="flex items-center gap-3">
        <button class="btn-vip text-xs md:text-sm !px-4 !py-2 md:!px-5 md:!py-2.5" @click="emit('open-vip')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M5 16l-2-8 6 3 3-7 3 7 6-3-2 8H5zm0 2h14v2H5v-2z"/></svg>
          开通 VIP
        </button>
      </div>
    </div>
  </header>
</template>
