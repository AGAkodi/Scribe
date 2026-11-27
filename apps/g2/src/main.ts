import { waitForEvenAppBridge, TextContainerProperty, CreateStartUpPageContainer, TextContainerUpgrade, OsEventTypeList, DeviceConnectType } from '@evenrealities/even_hub_sdk'

// The SDK logs event payloads by default. Suppress them to avoid logging audio.
const originalLog = console.log.bind(console)
console.log = (...args: unknown[]) => { if (typeof args[0] === 'string' && args[0].includes('EvenHub event')) return; originalLog(...args) }
type Project = { id: string; title: string }
type Mode = 'capture' | 'recall' | 'brainstorm'
type Preview = { transcript: string; title: string; category: string; project_title: string; mode: Mode; connection: string; connection_type: 'related' | 'possible_conflict' | 'none'; ai_status: string; action_id: string; destination: string; sources: { title: string; id: string; evidence: string }[] }
const root = document.querySelector<HTMLDivElement>('#app')!
root.innerHTML = `<h1>Scribe setup</h1><p>Audio is sent to Deepgram; project context may be processed by AI. Use demo content.</p><label>API URL <input id="url" value="http://127.0.0.1:18081"></label><br><label>Pairing code <input id="token" type="password"></label><br><button id="connect">Connect</button><p id="status">Enter the server URL and pairing code.</p><p><a id="receipt-link" hidden target="_blank" rel="noopener noreferrer">Open saved note in Notion</a></p>`
const configuredApi = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
if (configuredApi) { const input = root.querySelector<HTMLInputElement>('#url')!; input.value = configuredApi; input.readOnly = true }
const status = (message: string) => { root.querySelector('#status')!.textContent = message }
let base = '', token = '', projects: Project[] = [], project = 0, page = 0, mode = 0
const modes = ['capture', 'recall', 'brainstorm', 'projects'] as const
let history: { mode: Mode; transcript: string; response: string }[] = []
let state: 'setup'|'projects'|'home'|'recording'|'processing'|'review'|'proposal'|'confirm'|'saving'|'receipt'|'error' = 'setup'
let chunks: Uint8Array[] = [], size = 0, timer: number | undefined, preview: Preview | null = null, transcript = ''
let clickTimer: number | undefined
let generation = 0
let pairedBase = ''
let bridge: Awaited<ReturnType<typeof waitForEvenAppBridge>>
let connected = false
let unsubscribeEvents: (() => void) | undefined
let unsubscribeDevice: (() => void) | undefined
let disposed = false
function interruptCapture(message: string) {
  const interrupted = state === 'recording' || state === 'processing'
  generation++; clearTimeout(timer); clearTimeout(clickTimer); clickTimer = undefined
  chunks = []; size = 0
  if (bridge) void bridge.audioControl(false).catch(() => {})
  if (interrupted && !disposed) {
    state = 'error'
    void display(`${message}\n${transcript ? 'Tap: retry' : 'Tap: home'}`).catch(() => {})
  }
}
function dispose() {
  if (disposed) return
  disposed = true
  interruptCapture('Capture stopped')
  unsubscribeEvents?.(); unsubscribeDevice?.()
  connected = false
}
window.addEventListener('pagehide', dispose)
window.addEventListener('beforeunload', dispose)
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') interruptCapture('Capture stopped') })
async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(base + path, { ...init, headers: { Authorization: `Bearer ${token}`, ...init.headers } })
  if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(result.detail || `Request failed (${response.status})`) }
  return response.json()
}
async function display(message: string) {
  status(message.replaceAll('\n', ' · '))
  if (bridge && connected) await bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: 1, containerName: 'main', content: message }))
}
async function showReceipt(result: { notion_id: string; notion_title?: string | null; notion_url?: string | null }) {
  state = 'receipt'
  const link = root.querySelector<HTMLAnchorElement>('#receipt-link')!
  link.hidden = true
  if (result.notion_url) {
    try {
      const url = new URL(result.notion_url)
      if (url.protocol === 'https:' && (url.hostname === 'notion.so' || url.hostname.endsWith('.notion.so') || url.hostname === 'notion.com' || url.hostname.endsWith('.notion.com'))) { link.href = url.href; link.hidden = false }
    } catch { /* Keep the receipt text if Notion did not return a usable URL. */ }
  }
  await display(`Saved in Notion\n${result.notion_title || preview?.title || result.notion_id}\nTap: home`)
}
function reviewText() {
  const text = preview?.transcript || transcript
  const pages = text.match(/[\s\S]{1,160}/g) || ['Empty transcript']
  return `${page + 1}/${pages.length}\n${pages[page]}\nScroll: pages · tap: next`
}
function proposalPages(): string[] {
  if (!preview) return ['No proposal']
  const label = preview.mode === 'brainstorm' ? 'AI suggestion (speculation)' : preview.mode === 'recall' ? 'AI answer' : 'AI connection'
  const sections = [`Title:\n${preview.title}`, `Category: ${preview.category}\nProject: ${preview.project_title}`, `${label}:\n${preview.connection || 'None'}`, ...preview.sources.map((source, index) => `Source ${index + 1}: ${source.title}\n${source.evidence}`)]
  return sections.flatMap(section => section.match(/[\s\S]{1,145}/g) || [''])
}
function proposalText() {
  const pages = proposalPages()
  return `${page + 1}/${pages.length}\n${pages[page]}\nTap: next · double tap: discard`
}
async function prepare(attempt: number) {
  await display('Retrieving context...\nDouble tap: discard')
  const result: Preview = await api('/assist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: projects[project].id, mode: modes[mode], transcript, history }) })
  if (attempt !== generation) { await api(`/actions/${result.action_id}/cancel`, { method: 'POST' }).catch(() => {}); return }
  preview = result
  if (result.ai_status === 'ok' && result.connection_type === 'related') history = [...history, { mode: result.mode, transcript: transcript.slice(0, 1000), response: result.connection }].slice(-4)
  state = 'review'; page = 0; await display(reviewText())
}
async function stop() {
  if (state !== 'recording') return
  const attempt = ++generation
  state = 'processing'; clearTimeout(timer)
  try { await bridge.audioControl(false) } catch { if (attempt === generation) { chunks = []; size = 0; state = 'error'; await display('Microphone stop failed\nTap: home') } return }
  if (attempt !== generation) return
  await display('Transcribing...')
  const data = new Uint8Array(size); let offset = 0
  for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.length }
  chunks = []; size = 0
  try {
    const form = new FormData(); form.append('audio', new Blob([data], { type: 'application/octet-stream' }), 'capture.pcm')
    const recognized: string = (await api('/transcribe', { method: 'POST', body: form })).transcript
    if (attempt !== generation) return
    transcript = recognized
    await prepare(attempt)
  } catch (e) { if (attempt === generation) { state = 'error'; await display(`${(e as Error).message}\n${transcript ? 'Tap: retry · double tap: discard' : 'Tap: home'}`); if (transcript) status(`Unsaved transcript: ${transcript}`) } }
}
async function click() {
  if (state === 'projects') { state = 'home'; await display(`${projects[project].title}\n${modes[mode]}\nScroll: choose · tap: select`) }
  else if (state === 'home' && modes[mode] === 'projects') { state = 'projects'; await display(`Project: ${projects[project].title}\nScroll: choose · tap: select`) }
  else if (state === 'home') {
    state = 'recording'; chunks = []; size = 0; transcript = ''; preview = null
    const attempt = ++generation
    timer = window.setTimeout(() => { if (state === 'recording' && attempt === generation) { interruptCapture('Recording timed out') } }, 30000)
    await display('Recording...\nTap: stop · double tap: cancel')
    try {
      const started = await bridge.audioControl(true)
      if (state !== 'recording' || attempt !== generation || disposed) { await bridge.audioControl(false); return }
      if (!started) { clearTimeout(timer); state = 'error'; await display('Microphone unavailable\nTap: home') }
    } catch { if (attempt === generation && !disposed) { interruptCapture('Microphone unavailable') } }
  }
  else if (state === 'recording') await stop()
  else if (state === 'review') { const pages = Math.max(1, Math.ceil((preview?.transcript.length || 0) / 160)); if (page + 1 < pages) { page++; await display(reviewText()) } else { state = 'proposal'; page = 0; await display(proposalText()) } }
  else if (state === 'proposal') { const pages = proposalPages(); if (page + 1 < pages.length) { page++; await display(proposalText()) } else { state = 'confirm'; await display(`Save original and AI notes to\n${preview?.destination}?\nTap: confirm · double tap: cancel`) } }
  else if (state === 'confirm' && preview) { state = 'saving'; await display('Saving...'); try { const result = await api(`/actions/${preview.action_id}/confirm`, { method: 'POST' }); await showReceipt(result) } catch { state = 'error'; await display('Save status uncertain\nTap: check status') } }
  else if (state === 'error' && preview) { state = 'saving'; await display('Checking save...'); try { const result = await api(`/actions/${preview.action_id}`); if (result.status === 'saved') await showReceipt(result); else { state = 'error'; await display(`Save: ${result.status}\nTap: check again`) } } catch { state = 'error'; await display('Status unavailable\nTap: check again') } }
  else if (state === 'error' && transcript) { state = 'processing'; const attempt = ++generation; try { await prepare(attempt) } catch { if (attempt === generation) { state = 'error'; await display('Retry failed\nTap: retry · double tap: discard'); status(`Unsaved transcript: ${transcript}`) } } }
  else if (state === 'receipt' || state === 'error') { state = 'home'; await display(`${projects[project]?.title || 'Scribe'}\n${modes[mode]}\nScroll: choose · tap: select`) }
}
async function cancel() {
  if (state === 'recording') { generation++; clearTimeout(timer); state = 'home'; chunks = []; size = 0; await bridge.audioControl(false).catch(() => {}); await display('Capture discarded\nTap: capture'); return }
  if (state === 'processing') { generation++; state = 'home'; transcript = ''; await display('Capture discarded\nTap: capture'); return }
  if (state === 'error' && preview) { preview = null; state = 'home'; await display('Check Notion before retrying\nTap: capture'); return }
  if (state === 'error' && transcript) { transcript = ''; state = 'home'; await display('Transcript discarded\nTap: capture'); return }
  if ((state === 'review' || state === 'proposal' || state === 'confirm') && preview) { const actionId = preview.action_id; preview = null; state = 'home'; await display('Discarded\nTap: capture'); await api(`/actions/${actionId}/cancel`, { method: 'POST' }).catch(() => {}) }
}
root.querySelector<HTMLButtonElement>('#connect')!.onclick = async () => {
  try {
    const requestedBase = (root.querySelector<HTMLInputElement>('#url')!.value).replace(/\/$/, ''); const code = root.querySelector<HTMLInputElement>('#token')!.value
    if (configuredApi && requestedBase !== configuredApi) throw new Error('This package is configured for a different server')
    if (token && requestedBase !== pairedBase) throw new Error('Reload to connect to a different server')
    base = requestedBase
    if (!base.startsWith('https://') && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(base)) throw new Error('Use HTTPS except for localhost')
    if (!token) {
      const pairing = await fetch(base + '/pair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) })
      if (!pairing.ok) throw new Error('Pairing failed or code expired')
      token = (await pairing.json()).token; pairedBase = base; root.querySelector<HTMLInputElement>('#token')!.value = ''
    }
    projects = await api('/projects'); if (!projects.length) throw new Error('No authorized projects')
    bridge = await waitForEvenAppBridge()
    const result = await bridge.createStartUpPageContainer(new CreateStartUpPageContainer({ containerTotalNum: 1, textObject: [new TextContainerProperty({ xPosition: 0, yPosition: 0, width: 576, height: 288, borderWidth: 0, borderColor: 5, paddingLength: 4, containerID: 1, containerName: 'main', content: 'Scribe', isEventCapture: 1 })] }))
    if (result !== 0) throw new Error(`Display initialization failed (${result})`)
    connected = true; state = 'projects'; await display(`Project: ${projects[0].title}\nScroll: choose · tap: select`)
    unsubscribeEvents = bridge.onEvenHubEvent(event => {
      if (state === 'recording' && event.audioEvent?.audioPcm) { const chunk = new Uint8Array(event.audioEvent.audioPcm); if (size + chunk.length <= 960000) { chunks.push(chunk); size += chunk.length } }
      const sys = event.sysEvent ? event.sysEvent.eventType ?? OsEventTypeList.CLICK_EVENT : null
      const text = event.textEvent ? event.textEvent.eventType ?? OsEventTypeList.CLICK_EVENT : null
      if (sys === OsEventTypeList.SYSTEM_EXIT_EVENT || sys === OsEventTypeList.ABNORMAL_EXIT_EVENT) { dispose(); return }
      if (sys === OsEventTypeList.FOREGROUND_EXIT_EVENT) { interruptCapture('Capture stopped'); return }
      if (sys === OsEventTypeList.DOUBLE_CLICK_EVENT || text === OsEventTypeList.DOUBLE_CLICK_EVENT) { clearTimeout(clickTimer); clickTimer = undefined; void cancel(); return }
      if (sys === OsEventTypeList.CLICK_EVENT || text === OsEventTypeList.CLICK_EVENT) { if (clickTimer !== undefined) return; clickTimer = window.setTimeout(() => { clickTimer = undefined; void click() }, 400); return }
      if (text === OsEventTypeList.SCROLL_TOP_EVENT || text === OsEventTypeList.SCROLL_BOTTOM_EVENT) {
        const direction = text === OsEventTypeList.SCROLL_BOTTOM_EVENT ? 1 : -1
        if (state === 'projects') { const next = (project + direction + projects.length) % projects.length; if (next !== project) history = []; project = next; void display(`Project: ${projects[project].title}\nScroll: choose · tap: select`) }
        else if (state === 'home') { mode = (mode + direction + modes.length) % modes.length; void display(`${projects[project].title}\n${modes[mode]}\nScroll: choose · tap: select`) }
        else if (state === 'review') { const count = Math.max(1, Math.ceil((preview?.transcript.length || 0) / 160)); page = (page + direction + count) % count; void display(reviewText()) }
        else if (state === 'proposal') { const count = proposalPages().length; page = (page + direction + count) % count; void display(proposalText()) }
      }
    })
    unsubscribeDevice = bridge.onDeviceStatusChanged(device => {
      if (device.connectType === DeviceConnectType.Disconnected || device.connectType === DeviceConnectType.ConnectionFailed) interruptCapture('Glasses disconnected')
    })
  } catch (e) { status((e as Error).message) }
}
// Development only: connect without typing the code. The value comes from
// .env.development.local, which Vite never loads for production builds.
const devAccessCode = import.meta.env.DEV ? import.meta.env.VITE_DEV_ACCESS_CODE : undefined
if (devAccessCode) {
  root.querySelector<HTMLInputElement>('#token')!.value = devAccessCode
  root.querySelector<HTMLButtonElement>('#connect')!.click()
}
