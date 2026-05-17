<script setup>
import { nextTick, ref, provide, useTemplateRef, watch } from 'vue'
import TopNav from './components/TopNav.vue'
import HeroSection from './components/HeroSection.vue'
import VideoResultCard from './components/VideoResultCard.vue'
import DownloadQueue from './components/DownloadQueue.vue'
import VideoSummaryCard from './components/VideoSummaryCard.vue'
import FeaturesSection from './components/FeaturesSection.vue'
import PricingSection from './components/PricingSection.vue'
import FAQSection from './components/FAQSection.vue'
import VipModal from './components/VipModal.vue'
import FooterBar from './components/FooterBar.vue'

const parsedVideo = ref(null)
const parseError = ref('')
const parsing = ref(false)
const queue = ref([]) // list of jobs: { jobId, title, thumbnail, formatLabel, ... }

const summaryVideo = ref(null)
const summaryCardRef = useTemplateRef('summaryCardRef')
async function onSummarize(video) {
  summaryVideo.value = video
  await nextTick()
  // Auto-scroll into view and kick off the pipeline.
  summaryCardRef.value?.begin?.()
  document.getElementById('summary-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function closeSummary() {
  summaryCardRef.value?.reset?.()
  summaryVideo.value = null
}
watch(parsedVideo, () => { closeSummary() })

const vipOpen = ref(false)
const vipReason = ref('')
function openVip(reason = '') {
  vipReason.value = reason
  vipOpen.value = true
}
provide('openVip', openVip)
</script>

<template>
  <div class="min-h-screen flex flex-col bg-paper">
    <TopNav @open-vip="openVip('立即开通会员')" />

    <main class="flex-1">
      <HeroSection
        v-model:parsing="parsing"
        v-model:parsed="parsedVideo"
        v-model:error="parseError"
      />

      <section
        v-if="parseError || parsing || parsedVideo || queue.length"
        class="px-4 md:px-8 max-w-6xl mx-auto -mt-6 md:-mt-10 relative z-10 space-y-6"
      >
        <div
          v-if="parseError"
          class="card border border-red-200 bg-red-50/80 px-5 py-4 text-red-700 text-sm"
        >
          解析失败：{{ parseError }}
        </div>

        <div v-if="parsing" class="card px-6 py-10 text-center text-slate-500 animate-pulse">
          正在解析视频信息，请稍候…
        </div>

        <VideoResultCard
          v-if="parsedVideo && !parsing"
          :video="parsedVideo"
          @download="(payload) => queue.unshift(payload)"
          @open-vip="(reason) => openVip(reason)"
          @summarize="onSummarize"
        />

        <div id="summary-anchor"></div>
        <VideoSummaryCard
          v-if="summaryVideo"
          ref="summaryCardRef"
          :video="summaryVideo"
          @close="closeSummary"
        />

        <DownloadQueue v-if="queue.length" :jobs="queue" @open-vip="openVip('解锁批量并发下载')" />
      </section>

      <FeaturesSection />
      <PricingSection @open-vip="openVip('立即开通 VIP')" />
      <FAQSection />
    </main>

    <FooterBar />

    <VipModal v-model:open="vipOpen" :reason="vipReason" />
  </div>
</template>
