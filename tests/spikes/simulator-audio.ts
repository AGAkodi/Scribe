import { waitForEvenAppBridge, TextContainerProperty, CreateStartUpPageContainer, TextContainerUpgrade, OsEventTypeList } from '@evenrealities/even_hub_sdk'
const oldLog = console.log.bind(console)
console.log = (...args: unknown[]) => { if (typeof args[0] === 'string' && args[0].includes('EvenHub event') && JSON.stringify(args).includes('audioEvent')) return; oldLog(...args) }
document.body.textContent = 'Phase 0 simulator spike. Tap starts a five-second microphone test. No audio is saved.'
const bridge = await waitForEvenAppBridge()
const display = new TextContainerProperty({ xPosition: 0, yPosition: 0, width: 576, height: 288, borderWidth: 0, borderColor: 5, paddingLength: 4, containerID: 1, containerName: 'main', content: 'Scribe test\nTap to test microphone', isEventCapture: 1 })
const result = await bridge.createStartUpPageContainer(new CreateStartUpPageContainer({ containerTotalNum: 1, textObject: [display] }))
console.log('SPIKE page result', result)
async function show(content: string) { console.log('SPIKE display update', await bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: 1, containerName: 'main', content }))) }
let recording = false, frames = 0, bytes = 0, nonzero = 0
let sizes = new Set<number>()
bridge.onEvenHubEvent(event => {
 const pcm = event.audioEvent?.audioPcm
 if (pcm && recording) { frames++; bytes += pcm.length; sizes.add(pcm.length); for (const sample of pcm) if (sample !== 0) nonzero++ }
 const type = event.sysEvent ? (event.sysEvent.eventType ?? OsEventTypeList.CLICK_EVENT) : null
 const textType = event.textEvent ? (event.textEvent.eventType ?? OsEventTypeList.CLICK_EVENT) : null
 if ((type === OsEventTypeList.CLICK_EVENT || textType === OsEventTypeList.CLICK_EVENT) && !recording) {
  recording = true; frames = 0; bytes = 0; nonzero = 0; sizes = new Set()
  void show('Recording test...\nStops in 5 seconds')
  void bridge.audioControl(true).then(v => console.log('SPIKE audio start', v))
  window.setTimeout(async () => { await bridge.audioControl(false); recording = false; console.log('SPIKE audio summary', JSON.stringify({ frames, bytes, nonzero, sizes: [...sizes] })); await show(`Test complete\nFrames: ${frames}`) }, 5000)
 } else if (textType === OsEventTypeList.SCROLL_TOP_EVENT || textType === OsEventTypeList.SCROLL_BOTTOM_EVENT) { console.log('SPIKE scroll', textType); void show(`Scroll event: ${textType}\nTap for mic test`) }
})
