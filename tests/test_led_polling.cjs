// Exercise delayed network responses against the actual page script.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: '', style: {}, attributes: {}, clientWidth: 600, setAttribute(name, value) { this.attributes[name] = String(value); }}]));
let now = 0;
const requests = [];
const timers = [];
function deferred() { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; }
function FakeUPlot(options, data, element) {
    this.options = options;
    this.data = data;
    this.element = element;
    this.scales = {x: {}, y: {}};
    this.setData = nextData => { this.data = nextData; };
    this.setScale = (key, limits) => { this.scales[key] = limits; };
    this.setSize = size => { this.size = size; };
}
const context = vm.createContext({
    performance: {now: () => now}, AbortController, uPlot: FakeUPlot,
    document: {getElementById: id => elements[id]},
    fetch(url, options) {
        const gate = deferred();
        requests.push({url, options, gate});
        return gate.promise;
    },
    setTimeout(fn, ms) { const timer = {fn, ms, cleared: false}; timers.push(timer); return timer; },
    clearTimeout(timer) {if (timer) timer.cleared = true;},
    console: {log() {}, error() {}}, alert() {}
});
const settle = () => new Promise(setImmediate);
const response = value => ({ok: true, json: async () => value});
(async () => {
    vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
    assert.equal(requests.filter(r => r.url === '/api/data').length, 1);
    const join = context.updateLedStatus();
    assert.equal(requests.filter(r => r.url === '/api/led/status').length, 1);
    // A slow sensor call does not prevent the independent warning snapshot.
    requests.find(r => r.url === '/api/led/status').gate.resolve(response({available: true, alert_active: true}));
    await join;
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/);
    // An old sensor snapshot must never re-enable the LED button.
    requests.find(r => r.url === '/api/data').gate.resolve(response({led: {available: true, alert_active: false}}));
    await settle();
    assert.equal(elements.ledButton.disabled, true);
    assert.ok(timers.some(t => t.ms === 200 && !t.cleared));
    assert.ok(timers.some(t => t.ms === 1000 && !t.cleared));
    const timed = context.updateLedStatus();
    const slowRequest = requests.filter(r => r.url === '/api/led/status').at(-1);
    const timeout = timers.filter(t => t.ms === 1000 && !t.cleared).at(-1);
    timeout.fn();
    await timed;
    assert.equal(slowRequest.options.signal.aborted, true);
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/);
    slowRequest.gate.resolve(response({available: true, alert_active: true}));
    await settle();
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/); // Late response ignored.
    const recovery = context.updateLedStatus();
    requests.filter(r => r.url === '/api/led/status').at(-1).gate.resolve(response({available: true, alert_active: false}));
    await recovery;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.ledAlertStatus.textContent, 'LED 可操作');
    // A single failure preserves a recently confirmed operable state.
    const transient = context.updateLedStatus();
    timers.filter(t => t.ms === 1000 && !t.cleared).at(-1).fn();
    await transient;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.ledAlertStatus.textContent, 'LED 可操作');
    assert.equal(context.getLedDiagnostics().failureCount, 1);
    // A sensor success proves connection health, never refreshes LED validity.
    now = 5001;
    const healthySensor = context.updateData();
    requests.filter(r => r.url === '/api/data').at(-1).gate.resolve(response({light: 123, led: {available:true, alert_active:false}}));
    await healthySensor;
    const initialLight = context.getLightChartDiagnostics();
    assert.equal(initialLight.ready, true);
    assert.equal(initialLight.sampleCount, 1);
    assert.equal(initialLight.scaleMax, 2048);
    assert.equal(initialLight.xMax, 1);
    context.updateLightChart(4095);
    context.updateLightChart(0);
    const expandedLight = context.getLightChartDiagnostics();
    assert.equal(expandedLight.ready, true);
    assert.equal(expandedLight.sampleCount, 3);
    assert.equal(expandedLight.scaleMax, 4095);
    assert.equal(expandedLight.xMax, 2);
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /LED 狀態更新異常/);
    now += 5001;
    context.renderLedStatus();
    assert.match(elements.ledAlertStatus.textContent, /連線狀態無法確認/);
    // An unchanged LED snapshot still constitutes a fresh confirmation.
    const same = context.updateLedStatus();
    requests.filter(r => r.url === '/api/led/status').at(-1).gate.resolve(response({available:true, alert_active:false}));
    await same;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(context.getLedDiagnostics().failureCount, 0);
    // Manual refresh while a sensor request is active cannot overlap it.
    const sensor = context.updateData();
    await context.updateData();
    assert.equal(requests.filter(r => r.url === '/api/data').length, 3);
    requests.filter(r => r.url === '/api/data').at(-1).gate.resolve(response({}));
    await sensor;
    console.log('Independent LED polling, single flight, stale response and timeout: PASS');
})().catch(error => {console.error(error); process.exitCode = 1;});
