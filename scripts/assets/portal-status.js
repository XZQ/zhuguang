/* Observed Worker health is independent from the animated scenario demonstration. */
(function (root) {
  'use strict';
  const names = ['orchestrator', 'sentry', 'diagnoser', 'executor', 'auditor'];
  const maxAge = 120000;
  function fresh(value, now) {
    const time = Date.parse(value);
    return Number.isFinite(time) && now - time <= maxAge && now - time >= -30000;
  }
  function evaluate(data, now = Date.now(), expectedModel = '') {
    if (!data || data.schema_version !== 1 || !Array.isArray(data.workers)) {
      return {state: 'unknown', label: '运行状态未知 · 尚无有效观测', workers: {}};
    }
    const workers = {};
    for (const name of names) {
      const matching = data.workers.filter(item => item && item.name === name);
      const record = matching.length === 1 ? matching[0] : null;
      let state = 'unknown';
      if (record && record.observed_at) {
        state = fresh(record.observed_at, now) ? record.status : 'stale';
      }
      if (!['online', 'offline', 'unknown', 'stale'].includes(state)) state = 'unknown';
      workers[name] = {state, model: record && typeof record.model === 'string' ? record.model : null};
    }
    const rows = Object.values(workers);
    const online = rows.filter(row => row.state === 'online').length;
    const known = rows.filter(row => ['online', 'offline'].includes(row.state)).length;
    const mismatch = rows.some(row => row.model && expectedModel && row.model !== expectedModel);
    let state = 'unknown';
    if (rows.some(row => row.state === 'stale')) state = 'stale';
    else if (known === names.length) state = online === names.length ? 'healthy' : 'degraded';
    if (data.health === 'degraded' && state === 'healthy') state = 'degraded';
    if (mismatch && state === 'healthy') state = 'degraded';
    const detail = {unknown: '其余未观测', stale: '观测已过期', healthy: '观测正常', degraded: '存在异常'};
    return {state, online: known === names.length ? online : null, workers,
            label: `${online}/5 Workers 已确认在线 · ${detail[state]}${mismatch ? ' · 模型配置不一致' : ''}`};
  }
  function render(view, document) {
    const label = document.getElementById('runtime-status-label');
    label.textContent = view.label;
    label.dataset.state = view.state;
    const indicator = document.getElementById('runtime-indicator');
    if (indicator) indicator.style.background = view.state === 'healthy' ? '#10b981' : '#f59e0b';
    for (const card of document.querySelectorAll('.worker-card')) {
      const name = card.querySelector('h4').textContent.toLowerCase();
      const row = view.workers[name] || {state: view.state};
      const badge = card.querySelector('.badge');
      badge.textContent = {online: '已观测在线', offline: '已观测离线', stale: '观测过期'}[row.state] || '未观测';
      badge.className = row.state === 'online' ? 'badge badge-ok' : 'badge';
    }
  }
  function start(document, fetcher = root.fetch.bind(root)) {
    const expected = document.querySelector('meta[name="configured-model"]').content;
    async function refresh() {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      try {
        const response = await fetcher('./status.json', {cache: 'no-store', signal: controller.signal});
        if (!response.ok) throw new Error('status unavailable');
        render(evaluate(await response.json(), Date.now(), expected), document);
      } catch (_) {
        render({state: 'offline', label: '状态源不可达 · Worker 状态未知', workers: {}}, document);
      } finally {
        clearTimeout(timeout);
      }
    }
    refresh();
    return setInterval(refresh, 15000);
  }
  root.DianxunStatus = {evaluate, start};
  if (typeof module !== 'undefined') module.exports = root.DianxunStatus;
})(globalThis);
