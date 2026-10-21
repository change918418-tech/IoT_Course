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
    this.bbox = {left: 0, top: 0, width: 600, height: 280};
    this.ctx = {
        strokeCount: 0,
        fillTextCount: 0,
        labels: [],
        save() {},
        restore() {},
        setLineDash() {},
        beginPath() {},
        moveTo() {},
        lineTo() {},
        stroke: () => { this.ctx.strokeCount += 1; },
        fillText: text => {
            this.ctx.fillTextCount += 1;
            this.ctx.labels.push(text);
        }
    };
    this.valToPos = (value, key) => {
        const [min, max] = this.options.scales[key].range;
        return this.bbox.top + this.bbox.height * (1 - (value - min) / (max - min));
    };
    this.setData = nextData => { this.data = nextData; };
    this.setScale = (key, limits) => { this.scales[key] = limits; };
    this.setSize = size => { this.size = size; };
    FakeUPlot.instance = this;
    this.options.hooks?.draw?.forEach(hook => hook(this));
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
const response = (value, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => value
});
(async () => {
    vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
    assert.equal(requests.filter(r => r.url === '/api/data').length, 1);
    const join = context.updateLedStatus();
    assert.equal(requests.filter(r => r.url === '/api/led/status').length, 1);
    // A slow sensor call does not prevent the independent warning snapshot.
    requests.find(r => r.url === '/api/led/status').gate.resolve(response({
        available: true, alert_active: true, active_effect: 'low_light_alert'
    }));
    await join;
    assert.equal(elements.ledButton.disabled, true);
    assert.equal(elements.greenFlashButton.disabled, true);
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
    slowRequest.gate.resolve(response({
        available: true, alert_active: true, active_effect: 'low_light_alert'
    }));
    await settle();
    assert.match(elements.ledAlertStatus.textContent, /紅燈警示中/); // Late response ignored.
    const recovery = context.updateLedStatus();
    requests.filter(r => r.url === '/api/led/status').at(-1).gate.resolve(response({available: true, alert_active: false}));
    await recovery;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.greenFlashButton.disabled, false);
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
    requests.filter(r => r.url === '/api/data').at(-1).gate.resolve(response({
        light: 1110,
        light_thresholds: {trigger: 2200, reset: 1600, dark_when_high: true},
        led: {available:true, alert_active:false}
    }));
    await healthySensor;
    const initialLight = context.getLightChartDiagnostics();
    assert.equal(initialLight.ready, true);
    assert.equal(initialLight.sampleCount, 1);
    assert.equal(initialLight.scaleMax, 4095);
    assert.equal(initialLight.xMax, 1);
    assert.equal(initialLight.thresholds.trigger, 2200);
    assert.equal(initialLight.thresholds.reset, 1600);
    assert.equal(initialLight.thresholds.darkWhenHigh, true);
    assert.equal(context.uPlot.instance.ctx.strokeCount, 2);
    assert.equal(context.uPlot.instance.ctx.fillTextCount, 2);
    assert.deepEqual(context.uPlot.instance.ctx.labels.slice(-2), ['暗 > 2200', '亮 ≤ 1600']);
    context.updateLightChart(4095);
    context.updateLightChart(0);
    const expandedLight = context.getLightChartDiagnostics();
    assert.equal(expandedLight.ready, true);
    assert.equal(expandedLight.sampleCount, 3);
    assert.equal(expandedLight.scaleMax, 4095);
    assert.equal(expandedLight.xMax, 2);
    for (let value = 0; value < 80; value++) context.updateLightChart(value);
    const rollingLight = context.getLightChartDiagnostics();
    assert.equal(rollingLight.sampleCount, 80);
    assert.equal(rollingLight.xMax, 79);
    assert.equal(elements.ledButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /暫停操作/);
    now += 5001;
    context.renderLedStatus();
    assert.match(elements.ledAlertStatus.textContent, /連線狀態無法確認/);
    // An unchanged LED snapshot still constitutes a fresh confirmation.
    const same = context.updateLedStatus();
    requests.filter(r => r.url === '/api/led/status').at(-1).gate.resolve(response({available:true, alert_active:false}));
    await same;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.greenFlashButton.disabled, false);
    assert.equal(context.getLedDiagnostics().failureCount, 0);
    // Manual refresh while a sensor request is active cannot overlap it.
    const sensor = context.updateData();
    await context.updateData();
    assert.equal(requests.filter(r => r.url === '/api/data').length, 3);
    requests.filter(r => r.url === '/api/data').at(-1).gate.resolve(response({}));
    await sensor;
    context.showLedStatus({
        available: true,
        alert_active: true,
        active_effect: 'green_flash_alert'
    });
    assert.equal(elements.ledButton.disabled, true);
    assert.equal(elements.greenFlashButton.disabled, true);
    assert.match(elements.ledAlertStatus.textContent, /綠燈效果中/);
    context.showLedStatus({
        available: true,
        alert_active: false,
        active_effect: null
    });

    const greenRun = context.flashGreen();
    const greenSubmit = requests.at(-1);
    assert.equal(greenSubmit.url, '/api/led/commands');
    assert.equal(greenSubmit.options.method, 'POST');
    assert.deepEqual(
        JSON.parse(greenSubmit.options.body),
        {kind: 'green_flash_alert'});
    assert.equal(elements.ledButton.disabled, true);
    assert.equal(elements.greenFlashButton.disabled, true);
    greenSubmit.gate.resolve(response({
        id: 303,
        request_id: 303,
        status: 'accepted'
    }, 202));
    await settle();
    const greenResult = requests.at(-1);
    assert.equal(greenResult.url, '/api/led/commands/303');
    greenResult.gate.resolve(response({
        id: 303,
        request_id: 303,
        status: 'executed'
    }));
    await settle();
    const greenRefresh = requests.at(-1);
    assert.equal(greenRefresh.url, '/api/led/status');
    greenRefresh.gate.resolve(response({
        available: true,
        alert_active: false,
        active_effect: null
    }));
    await greenRun;
    assert.equal(elements.ledButton.disabled, false);
    assert.equal(elements.greenFlashButton.disabled, false);
    assert.equal(elements.ledCommandStatus.textContent, '命令 303 已執行');
    console.log('Independent LED polling, single flight, stale response and timeout: PASS');
})().catch(error => {console.error(error); process.exitCode = 1;});
