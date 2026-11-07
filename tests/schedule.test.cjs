const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function app(fetcher) {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {
            value: '', innerHTML: '', innerText: '', disabled: true, style: {},
            classList: { add() {}, remove() {} }, scrollIntoView() {},
        });
        return elements.get(id);
    };
    const context = vm.createContext({
        document: { addEventListener() {}, getElementById: element, querySelectorAll: () => [] },
        fetch: fetcher, AbortSignal, console: { error() {} },
        setTimeout: () => 0, setInterval: () => 0, clearInterval() {},
    });
    vm.runInContext(script, context);
    return { run: code => vm.runInContext(code, context), element };
}

function snapshot(run, items, status) {
    return { date: run('targetDateStr'), checkedAt: new Date().toISOString(), branches: {
        GANGNAM_ST: { themes: { MY_ROOM: items }, themeStatus: { MY_ROOM: status } },
    } };
}

const slots = [
    { time: '09:45', num: '1', enable: 'Y' },
    { time: '10:30', num: '2', enable: 'N' },
];

test('valid snapshot enables only open slots and blocks closed selection', async () => {
    let data;
    const { run, element } = app(async () => ({ ok: true, json: async () => data }));
    data = snapshot(run, slots, { state: 'ready' });
    run("currentBranch = branchesData.GANGNAM_ST");
    await run("selectTheme('MY_ROOM')");
    assert.equal(run('isCurrentTimeDisabled(0)'), false);
    assert.equal(run('isCurrentTimeDisabled(1)'), true);
    run('selectTimeByIndex(1, {disabled: false})');
    assert.equal(run('currentTime'), null);
    run('selectTimeByIndex(0, {disabled: false, classList: {add(){}}})');
    assert.equal(element('submitBtn').disabled, false);
    assert.match(element('timeWrapper').innerHTML, /마감/);
});

test('empty legacy snapshot shows refresh state without proxy requests', async () => {
    let data, calls = 0;
    const { run, element } = app(async url => {
        calls++;
        assert.match(url, /^\.\/data\/schedule.json/);
        return { ok: true, json: async () => data };
    });
    data = snapshot(run, []);
    run('currentBranch = branchesData.GANGNAM_ST');
    await run("selectTheme('MY_ROOM')");
    assert.equal(calls, 1);
    assert.match(element('timeWrapper').innerHTML, /갱신을 기다리고/);
    assert.doesNotMatch(element('timeWrapper').innerHTML, /확인 불가/);
    assert.equal(element('submitBtn').disabled, true);
});

test('network failure can recover when retrying', async () => {
    let data, fail = true;
    const { run, element } = app(async () => {
        if (fail) throw new Error('Offline');
        return { ok: true, json: async () => data };
    });
    data = snapshot(run, slots, { state: 'ready' });
    run('currentBranch = branchesData.GANGNAM_ST');
    await run("selectTheme('MY_ROOM')");
    assert.match(element('timeWrapper').innerHTML, /불러오지 못했습니다/);
    fail = false;
    await run("selectTheme('MY_ROOM')");
    assert.equal(run('isCurrentTimeDisabled(0)'), false);
});

test('switching branches while loading does not apply the previous theme', async () => {
    let resolve;
    const { run } = app(() => new Promise(done => { resolve = done; }));
    const data = snapshot(run, slots, { state: 'ready' });
    run('currentBranch = branchesData.GANGNAM_ST');
    const loading = run("selectTheme('MY_ROOM')");
    run("selectBranch('MEMORY')");
    resolve({ ok: true, json: async () => data });
    await loading;
    assert.equal(run('currentTheme'), null);
});

test('preopening status distinguishes opening time and collection delay', async () => {
    let data;
    const { run, element } = app(async () => ({ ok: true, json: async () => data }));
    run('currentBranch = branchesData.GANGNAM_ST');
    data = snapshot(run, [], { state: 'not_open', opensAt: '2099-01-01T11:30:00+09:00' });
    await run("selectTheme('MY_ROOM')");
    assert.match(element('timeWrapper').innerHTML, /오픈 전/);
    data.branches.GANGNAM_ST.themeStatus.MY_ROOM.opensAt = '2000-01-01T11:30:00+09:00';
    await run("selectTheme('MY_ROOM')");
    assert.match(element('timeWrapper').innerHTML, /오픈 후 시간표 갱신/);
});
