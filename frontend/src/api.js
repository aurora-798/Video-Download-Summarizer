import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60_000,
})

export async function parseVideo(url) {
  const { data } = await api.post('/parse', { url })
  return data
}

export async function getHealth() {
  const { data } = await api.get('/health')
  return data
}

export async function startDownload({ url, format_id = null, audio_only = false }) {
  const { data } = await api.post('/download', { url, format_id, audio_only })
  return data.job_id
}

export async function getProgress(jobId) {
  const { data } = await api.get(`/progress/${jobId}`)
  return data
}

export function fileUrl(jobId) {
  return `/api/file/${jobId}`
}
