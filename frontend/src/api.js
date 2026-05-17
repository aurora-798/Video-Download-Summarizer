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

// --- AI summary --------------------------------------------------------

export async function startSummarize(url) {
  const { data } = await api.post('/summarize', { url })
  return data.task_id
}

export async function getSummary(taskId) {
  const { data } = await api.get(`/summarize/${taskId}`)
  return data
}

/**
 * Open an SSE connection to the summary stream. Calls onEvent(name, data)
 * for every event ('snapshot' | 'stage' | 'meta' | 'source' | 'transcript'
 * | 'delta' | 'done' | 'error' | 'close'). Returns the EventSource so the
 * caller can close it.
 */
export function openSummaryStream(taskId, onEvent) {
  const es = new EventSource(`/api/summarize/${taskId}/stream`)
  const handler = (name) => (e) => {
    let payload = null
    try { payload = e.data ? JSON.parse(e.data) : null } catch { payload = e.data }
    onEvent(name, payload)
  }
  ;['snapshot', 'stage', 'meta', 'source', 'transcript', 'delta', 'done', 'error', 'close']
    .forEach((name) => es.addEventListener(name, handler(name)))
  es.onerror = () => onEvent('connection_error', null)
  return es
}
