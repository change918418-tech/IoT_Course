// Execute the actual page script against a small fake DOM and HTTP responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
const ids = [...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]);
ids.forEach(id => elements[id] = { textContent: '', style: {}, attributes: {}, clientWidth: 600, setAttribute(name, value) { this.attributes[name] = String(value); } });
let fail = false;
let now = 0;
let rfid = {status: 'ready', last_uid: '0102030404', last_read_at: '2026-10-06 00:30:00', recent_reads: [{uid: '0102030404', read_at: '2026-10-06 00:30:00'}], error: null};
let motion = {sensor_status: 'ready', detected: false, count: 0, last_detected_at: null, recent_detections: [], music_status: 'idle'};
let motionStatus = motion;
let led = {available: true, alert_active: false, alert_flash_count: 1, alert_flash_total: 5, alert_flash_log: [{sequence: 1, time: '2026-10-06 00:35:00'}]};
let posts = 0;
let postStatus = 202;
let commandStatus = 'executed';
function FakeUPlot(options, data, element) {
    this.options = options;
    this.data = data;
    this.element = element;
    this.setData = nextData => { this.data = nextData; };
    this.setScale = () => {};
    this.setSize = () => {};
}
const context = vm.createContext({
    uPlot: FakeUPlot,
    document: { getElementById(id) { assert.ok(elements[id], `Missing element ${id}`); return elements[id]; } },
    fetch: async (url, options) => {
        if (fail) throw Error('offline');
        if (options?.method === 'POST') {
            posts++;
            if (postStatus === 409) led.alert_active = true;
            return {ok: postStatus === 202, status: postStatus, json: async () => ({id: 9, status: postStatus === 202 ? 'accepted' : 'rejected', reason: 'busy'})};
        }
        if (url === '/api/led/status') return {ok: true, json: async () => ({...led})};
        if (url === '/api/motion/status') return {ok: true, json: async () => ({...motionStatus})};
        if (url.startsWith('/api/led/commands/')) return {ok: true, json: async () => ({id: 9, status: commandStatus, reason: 'alert_started'})};
        return {ok: true, json: async () => ({temp: 0, humidity: 0, light: 0, light_thresholds: {trigger: 500, reset: 1100}, rfid, motion, led})};
    },
    performance: {now: () => now}, AbortController, setTimeout() {return 1;}, clearTimeout() {}, alert() {}, console: {log() {}, error() {}}
});
(async () => {
    vm.runInContext(source, context);
    await new Promise(setImmediate);
    await new Promise(setImmediate);
    async function refresh() { await context.updateData(); await context.updateLedStatus(); }
    await refresh();
    assert.equal(elements.rfidHistory.textContent, '0102030404：2026-10-06 00:30:00');
    assert.equal(elements.ledFlashCount.textContent, '閃紅次數：1');
    assert.equal(elements.ledFlashHistory.textContent, '閃紅1：2026-10-06 00:35:00');
    const lightDiagnostics = context.getLightChartDiagnostics();
    assert.equal(lightDiagnostics.ready, true);
    assert.ok(lightDiagnostics.sampleCount >= 1);
    assert.equal(lightDiagnostics.scaleMax, 2048);
    assert.equal(lightDiagnostics.thresholds.trigger, 500);
    assert.equal(lightDiagnostics.thresholds.reset, 1100);
    assert.equal(elements.tempCard.textContent, 0);
    assert.equal(elements.ledButton.disabled, false);
    led.alert_active = true;
    await refresh();
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/);
    await context.toggleLED();
    assert.equal(posts, 0);
    led.alert_active = false;
    await refresh();
    postStatus = 409; // A warning begins after the last browser refresh.
    await context.toggleLED();
    assert.equal(posts, 1);
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/);
    postStatus = 202;
    led.alert_active = false;
    await refresh();
    await context.toggleLED();
    assert.equal(posts, 2);
    assert.match(elements.ledCommandStatus.textContent, /已執行/);
    commandStatus = 'rejected';
    await context.toggleLED();
    assert.match(elements.ledCommandStatus.textContent, /rejected.*alert_started/);
    commandStatus = 'executed';
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.motionMessage.textContent, '等待移動');
    assert.equal(elements.motionCount.textContent, 0);
    motionStatus = {...motion, detected: true, count: 1, last_detected_at: '2026-10-06 02:41:04',
        recent_detections: ['2026-10-06 02:41:04'], music_status: 'playing'};
    await context.updateMotionStatus();
    assert.equal(elements.motionMessage.textContent, '偵測到移動物');
    assert.equal(elements.musicStatus.textContent, '播放中');
    motionStatus = motion;
    motion = {...motion, detected: true, count: 1, last_detected_at: '2026-10-06 02:41:04', recent_detections: ['2026-10-06 02:41:04'], music_status: 'playing'};
    await refresh();
    assert.equal(elements.motionMessage.textContent, '偵測到移動物');
    assert.equal(elements.musicStatus.textContent, '播放中');
    assert.equal(elements.motionHistory.textContent, '移動1：' + motion.last_detected_at);
    motion = {...motion, detected: false, music_status: 'completed'};
    await refresh();
    assert.equal(elements.motionMessage.textContent, '等待移動');
    assert.equal(elements.motionCount.textContent, 1);
    assert.equal(elements.musicStatus.textContent, '播放完成');
    rfid = {status: 'init_error', last_uid: null, last_read_at: null, recent_reads: [], error: '<not html>'};
    await refresh();
    assert.equal(elements.rfidHistory.textContent, '尚未讀卡');
    assert.equal(elements.rfidStatus.textContent, '初始化失敗');
    assert.equal(elements.rfidError.textContent, '<not html>');
    fail = true;
    now += 5001;
    await refresh();
    assert.equal(elements.status.textContent, '🔴 連接失敗');
    assert.equal(elements.ledButton.disabled, true);
    assert.equal(elements.musicStatus.textContent, '連接失敗，狀態未知');
    fail = false;
    await refresh();
    assert.equal(elements.status.textContent, '🟢 正常');
    motion = {...motion, sensor_status: 'error', sensor_error: '<sensor error>', music_status: 'error', music_error: 'bad "note"'};
    await refresh();
    assert.equal(elements.motionMessage.textContent, 'PIR 讀取異常');
    assert.equal(elements.musicStatus.textContent, '播放失敗');
    assert.equal(elements.motionError.textContent, '<sensor error>；bad "note"');
    console.log('RFID page script: PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
