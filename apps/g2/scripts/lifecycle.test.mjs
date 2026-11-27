import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

function harness() {
  let source = readFileSync(new URL('../src/main.ts', import.meta.url), 'utf8')
  source = source.replace(/^import \{[^\n]+\} from '@evenrealities\/even_hub_sdk'\s*/m, 'const { waitForEvenAppBridge, TextContainerProperty, CreateStartUpPageContainer, TextContainerUpgrade, OsEventTypeList, DeviceConnectType } = globalThis.sdk\n')
  source = source.replace('import.meta.env.VITE_API_BASE_URL', "''")
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText
  const controls = { '#url': { value: 'http://localhost:8000' }, '#token': { value: 'fixture-code' }, '#status': { textContent: '' }, '#connect': {} }
  const root = { innerHTML: '', querySelector: key => controls[key] }
  const documentListeners = {}, windowListeners = {}, timers = new Map()
  let nextTimer = 0, eventHandler, deviceHandler, resolveStart
  const calls = [], unsubscribed = [], requests = []
  const bridge = {
    createStartUpPageContainer: async () => 0,
    textContainerUpgrade: async () => true,
    audioControl: enabled => { calls.push(enabled); return enabled ? new Promise(resolve => { resolveStart = resolve }) : Promise.resolve(true) },
    onEvenHubEvent: handler => { eventHandler = handler; return () => unsubscribed.push('event') },
    onDeviceStatusChanged: handler => { deviceHandler = handler; return () => unsubscribed.push('device') },
  }
  const types = { CLICK_EVENT: 0, SCROLL_TOP_EVENT: 1, SCROLL_BOTTOM_EVENT: 2, DOUBLE_CLICK_EVENT: 3, FOREGROUND_EXIT_EVENT: 5, ABNORMAL_EXIT_EVENT: 6, SYSTEM_EXIT_EVENT: 7 }
  const klass = class { constructor(value) { Object.assign(this, value) } }
  const sdk = { waitForEvenAppBridge: async () => bridge, TextContainerProperty: klass, CreateStartUpPageContainer: klass, TextContainerUpgrade: klass, OsEventTypeList: types, DeviceConnectType: { Disconnected: 'disconnected', ConnectionFailed: 'connectionFailed' } }
  const win = { addEventListener: (name, fn) => { windowListeners[name] = fn }, setTimeout: (fn, ms) => { const id = ++nextTimer; timers.set(id, { fn, ms }); return id }, clearTimeout: id => timers.delete(id) }
  const doc = { querySelector: () => root, visibilityState: 'visible', addEventListener: (name, fn) => { documentListeners[name] = fn } }
  const fetch = async (url, init = {}) => {
    let data
    if (url.endsWith('/pair')) data = { token: 'test-token' }
    else if (url.endsWith('/projects')) data = [{ id: 'project', title: 'Demo' }, { id: 'project-b', title: 'Other' }]
    else if (url.endsWith('/transcribe')) data = { transcript: 'fixture phrase' }
    else if (url.endsWith('/assist')) {
      const body = JSON.parse(init.body); requests.push(body)
      data = { transcript: body.transcript, title: body.transcript, category: 'Idea', project_title: 'Demo', mode: body.mode, connection: 'Related', connection_type: 'related', ai_status: 'ok', action_id: 'fixture-action', destination: 'Notion Ideas', sources: [] }
    } else data = { status: 'cancelled' }
    return { ok: true, json: async () => data }
  }
  const context = { sdk, document: doc, window: win, console: { log() {} }, fetch, clearTimeout: win.clearTimeout, Blob, FormData }
  context.globalThis = context
  vm.runInNewContext(code, context)
  const flush = () => new Promise(resolve => setImmediate(resolve))
  async function click() { eventHandler({ sysEvent: {} }); const timer = [...timers.entries()].find(([, value]) => value.ms === 400); assert.ok(timer); timers.delete(timer[0]); timer[1].fn(); await flush() }
  return { controls, calls, requests, unsubscribed, windowListeners, documentListeners, doc, bridge, flush, click, event: value => eventHandler(value), device: value => deviceHandler(value), resolveStart: value => resolveStart(value), timers }
}

test('background during a pending microphone start stops it again if start resolves late', async () => {
  const h = harness()
  await h.controls['#connect'].onclick()
  await h.click() // select project
  await h.click() // request recording; start remains unresolved
  assert.deepEqual(h.calls, [true])
  h.event({ sysEvent: { eventType: 5 } })
  await h.flush()
  assert.deepEqual(h.calls, [true, false])
  h.resolveStart(true)
  await h.flush()
  assert.deepEqual(h.calls, [true, false, false])
  h.windowListeners.pagehide()
  await h.flush()
  assert.deepEqual(h.unsubscribed.sort(), ['device', 'event'])
})

test('disconnect and maximum duration both issue a stop while start is pending', async () => {
  for (const interruption of ['disconnect', 'timeout']) {
    const h = harness()
    await h.controls['#connect'].onclick(); await h.click(); await h.click()
    if (interruption === 'disconnect') h.device({ connectType: 'disconnected' })
    else { const timer = [...h.timers.values()].find(value => value.ms === 30000); assert.ok(timer); timer.fn() }
    await h.flush(); h.resolveStart(true); await h.flush()
    assert.deepEqual(h.calls, [true, false, false])
  }
})

test('hidden page stops recording and disposes both listeners on unload', async () => {
  const h = harness()
  await h.controls['#connect'].onclick(); await h.click(); await h.click()
  h.doc.visibilityState = 'hidden'; h.documentListeners.visibilitychange()
  await h.flush(); h.resolveStart(true); await h.flush()
  assert.deepEqual(h.calls, [true, false, false])
  h.windowListeners.beforeunload(); await h.flush()
  assert.deepEqual(h.unsubscribed.sort(), ['device', 'event'])
})

test('conversation history is bounded to the active project', async () => {
  const h = harness()
  await h.controls['#connect'].onclick(); await h.click() // select first project
  async function capture() {
    await h.click(); h.resolveStart(true); await h.flush()
    h.event({ audioEvent: { audioPcm: [1, 0] } })
    await h.click(); await h.flush()
  }
  await capture()
  assert.equal(h.requests.length, 1)
  assert.equal(h.requests[0].history.length, 0)
  h.event({ sysEvent: { eventType: 3 } }); await h.flush() // discard review
  await capture()
  assert.equal(h.requests[1].history.length, 1)
  h.event({ sysEvent: { eventType: 3 } }); await h.flush()
  for (let i = 0; i < 3; i++) h.event({ textEvent: { eventType: 2 } }) // Projects menu
  await h.click(); h.event({ textEvent: { eventType: 2 } }); await h.click()
  for (let i = 0; i < 1; i++) h.event({ textEvent: { eventType: 2 } }) // Projects wraps to Capture
  await capture()
  assert.equal(h.requests[2].project_id, 'project-b')
  assert.equal(h.requests[2].history.length, 0)
})
