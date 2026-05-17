<script setup>
const emit = defineEmits(['open-vip'])
</script>

<template>
  <header class="sticky top-0 z-30 bg-paper/85 backdrop-blur-md border-b border-[#E5DDD2]/80">
    <div class="max-w-6xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button
          aria-label="menu"
          class="md:hidden p-2 -ml-2 rounded-lg hover:bg-brand-50 text-muted"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M4 7h16M4 12h16M4 17h16"/>
          </svg>
        </button>
        <a href="/" class="flex items-center gap-2.5 group">
          <span class="inline-flex h-9 w-9 rounded-xl bg-cta-grad items-center justify-center shadow-soft ring-1 ring-white/20">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12"/>
              <path d="M7 10l5 5 5-5"/>
              <path d="M5 21h14"/>
            </svg>
          </span>
          <span class="font-serif font-semibold text-lg tracking-wide text-ink">
            VidGrab<span class="text-grad">Pro</span>
          </span>
        </a>
      </div>

      <nav class="hidden md:flex items-center gap-8 text-sm text-muted">
        <a href="#features" class="hover:text-brand-700 transition font-light">功能</a>
        <a href="#pricing" class="hover:text-brand-700 transition font-light">价格</a>
        <a href="#faq" class="hover:text-brand-700 transition font-light">常见问题</a>
      </nav>

      <div class="flex items-center gap-3">
        <button class="btn-vip text-xs md:text-sm !px-4 !py-2 md:!px-5 md:!py-2.5" @click="emit('open-vip')">
          会员
        </button>
      </div>
    </div>
  </header>
</template>
