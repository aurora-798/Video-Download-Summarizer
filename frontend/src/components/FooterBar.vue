<script setup>
const year = new Date().getFullYear()
</script>

<template>
  <footer class="bg-slate-900 text-slate-300">
    <div class="max-w-6xl mx-auto px-4 md:px-8 py-12 grid md:grid-cols-4 gap-8">
      <div class="md:col-span-2">
        <div class="flex items-center gap-2">
          <span class="inline-flex h-9 w-9 rounded-xl bg-cta-grad items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12"/>
              <path d="M7 10l5 5 5-5"/>
              <path d="M5 21h14"/>
            </svg>
          </span>
          <span class="font-extrabold text-lg text-white">VidGrabPro</span>
        </div>
        <p class="mt-4 text-sm text-slate-400 leading-relaxed max-w-md">
          一站式万能视频下载工具，让世界每一段值得保存的画面，都能稳稳落进你的硬盘。
        </p>
        <div class="mt-4 flex items-center gap-3 text-xs text-slate-500">
          <span class="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-2.5 py-1">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>服务正常
          </span>
          <span>已为 <b class="text-slate-200">10w+</b> 用户下载视频 <b class="text-slate-200">500w+</b> 条</span>
        </div>
      </div>

      <div>
        <h4 class="font-semibold text-white mb-3 text-sm">产品</h4>
        <ul class="space-y-2 text-sm">
          <li><a href="#features" class="hover:text-white transition">功能介绍</a></li>
          <li><a href="#pricing" class="hover:text-white transition">价格方案</a></li>
          <li><a href="#faq" class="hover:text-white transition">常见问题</a></li>
        </ul>
      </div>

      <div>
        <h4 class="font-semibold text-white mb-3 text-sm">资源</h4>
        <ul class="space-y-2 text-sm">
          <li><a href="#" class="hover:text-white transition">帮助中心</a></li>
          <li><a href="#" class="hover:text-white transition">商务合作</a></li>
          <li><a href="#" class="hover:text-white transition">使用条款</a></li>
        </ul>
      </div>
    </div>

    <div class="border-t border-slate-800">
      <div class="max-w-6xl mx-auto px-4 md:px-8 py-5 text-xs text-slate-500 flex flex-col md:flex-row items-center justify-between gap-2">
        <span>© {{ year }} VidGrabPro · Powered by yt-dlp · 仅供学习与个人合理使用</span>
        <span>本网站不存储任何视频文件，下载与版权责任由用户自行承担</span>
      </div>
    </div>
  </footer>
</template>
