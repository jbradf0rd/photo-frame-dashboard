// Agents: Hermes status report, pushed every 5 minutes by frame_agents_push.py on the mini.
// Five cards: scheduled jobs, Hermes usage, fleet, long jobs, power. Zoho work is on the Work tab.
// Counts only: no client names, task titles, mail subjects or job names reach this page.
(function () {
  'use strict';
  var V = { el: null, rep: null, fetched: 0, err: null };
  var COLORS = {
    jobs: ['#2D5BFF', '45 91 255'], usage: ['#7A3FD1', '122 63 209'], fleet: ['#00A36C', '0 163 108'],
    long: ['#E4007C', '228 0 124'], power: ['#FFB000', '255 176 0']
  };

  function esc(s) { return App.esc(String(s == null ? '' : s)); }
  function pst(k) { return '--c:' + COLORS[k][0] + ';--c-rgb:' + COLORS[k][1]; }
  function ago(isoStr) {
    if (!isoStr) return 'never';
    var m = Math.round((Date.now() - new Date(isoStr).getTime()) / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return m + ' min ago';
    if (m < 1440) return Math.floor(m / 60) + ' hr ago';
    return Math.floor(m / 1440) + ' days ago';
  }
  function until(isoStr) {
    if (!isoStr) return '–';
    var m = Math.round((new Date(isoStr).getTime() - Date.now()) / 60000);
    if (m <= 0) return 'now';
    return m < 60 ? 'in ' + m + ' min' : 'in ' + Math.floor(m / 60) + ' hr ' + (m % 60) + ' min';
  }
  function big(n) {
    if (n == null) return '–';
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + 'M';
    if (n >= 1e3) return Math.round(n / 1e3) + 'K';
    return String(n);
  }
  function money(n) { return n == null ? '–' : '$' + (n >= 100 ? Math.round(n) : n.toFixed(2)); }
  function status(ok, text) {
    return '<span class="ag-status' + (ok ? '' : ' is-warn') + '"><i></i>' + esc(text) + '</span>';
  }
  function head(k, title, sub, stat) {
    return '<header class="ag-head"><div class="ag-id"><i class="ag-swatch"></i><b>' + esc(title) + '</b>' +
      (sub ? '<span class="ag-plan">' + esc(sub) + '</span>' : '') + '</div>' + (stat || '') + '</header>';
  }
  function stat(n, label, warn) {
    return '<div class="ag-stat' + (warn ? ' is-warn' : '') + '"><span class="num">' + n + '</span><small>' + esc(label) + '</small></div>';
  }
  function shell(k, inner) { return '<section class="ag-card ag-card--' + k + '" style="' + pst(k) + '">' + inner + '</section>'; }
  function broken(k, title, c) {
    return shell(k, head(k, title, '', status(false, 'No data')) +
      '<div class="ag-empty">' + esc(c && c.error ? 'Could not read this: ' + c.error : 'Waiting for the first report') + '</div>');
  }

  // 1. Scheduled jobs
  function jobs(c) {
    if (!c || !c.ok) return broken('jobs', 'Jobs', c);
    var d = c.data, ok = d.failing === 0;
    return shell('jobs', head('jobs', 'Jobs', '', status(ok, ok ? 'All passing' : d.failing + ' failing')) +
      '<div class="ag-stats">' + stat(d.passing, 'passing') + stat(d.failing, 'failing', d.failing > 0) + stat(d.paused, 'paused') + '</div>' +
      (ok ? '' : '<div class="ag-incident ag-incident--hot">' + App.icon('bolt', 16) + 'Last failure ' + esc(ago(d.lastFailure)) + '. Ask Hermes which job.</div>') +
      '<footer class="ag-foot"><div><span class="num">' + esc(until(d.nextRun)) + '</span><small>next run</small></div>' +
      '<div><span class="num">' + esc(ago(d.lastRun)) + '</span><small>last run</small></div></footer>');
  }

  // 2. Hermes usage
  function usage(c) {
    if (!c || !c.ok) return broken('usage', 'Hermes', c);
    var d = c.data, max = Math.max.apply(null, d.week.map(function (x) { return x.cost; }).concat([0.01]));
    var bars = d.week.map(function (x, i) {
      var day = new Date(x.date + 'T12:00:00');
      return '<div class="ag-col' + (i === 6 ? ' is-today' : '') + '"><b class="ag-colval">' + (x.cost >= 1 ? '$' + Math.round(x.cost) : '') + '</b>' +
        '<div class="ag-stack" style="height:' + Math.max(4, x.cost / max * 100) + '%"><i></i></div>' +
        '<span>' + (i === 6 ? 'Today' : App.fmt.dayShort(day)) + '</span></div>';
    }).join('');
    var src = Object.keys(d.sources || {}).map(function (k) { return esc(k) + ' ' + d.sources[k]; }).join(' · ');
    return shell('usage', head('usage', 'Hermes', 'Usage today', '') +
      '<div class="ag-stats">' + stat(money(d.today.cost), 'cost today') + stat(big(d.today.tokens), 'tokens') + stat(d.today.sessions, 'sessions') + '</div>' +
      '<div class="ag-sub">' + (src || 'No sessions yet today') + '</div>' +
      '<div class="ag-chart ag-chart--light">' + bars + '</div>' +
      '<div class="ag-sub">Last 7 days: ' + money(d.weekCost) + ' · ' + big(d.weekTokens) + ' tokens</div>');
  }

  // 3. Fleet
  function fleet(c) {
    if (!c || !c.ok) return broken('fleet', 'Fleet', c);
    var d = c.data, ok = d.online === d.total && d.warn === 0;
    function pct(v, hi) { return v == null ? '<td>–</td>' : '<td class="' + (v >= hi ? 'is-warn' : '') + '">' + Math.round(v) + '%</td>'; }
    var rows = d.hosts.map(function (h) {
      return '<tr class="' + (h.online ? '' : 'is-down') + '"><th><i class="ag-dot ag-dot--' + (h.online ? (h.overall === 'ok' ? 'ok' : 'warn') : 'down') + '"></i>' + esc(h.name) + '</th>' +
        (h.online ? pct(h.cpu, 90) + pct(h.ram, 85) + pct(h.disk, 85) + '<td>' + (h.temp == null ? '–' : Math.round(h.temp * 9 / 5 + 32) + '°') + '</td>' : '<td colspan="4">offline</td>') + '</tr>';
    }).join('');
    return shell('fleet', head('fleet', 'Fleet', d.online + ' of ' + d.total + ' online', status(ok, ok ? 'Healthy' : 'Check')) +
      '<table class="ag-table"><thead><tr><th></th><td>CPU</td><td>RAM</td><td>Disk</td><td>CPU °F</td></tr></thead><tbody>' + rows + '</tbody></table>');
  }

  // 4. Long jobs
  function longJobs(c) {
    if (!c || !c.ok) return broken('long', 'Long jobs', c);
    var d = c.data;
    var bars = d.jobs.map(function (j) {
      var p = j.total ? Math.min(100, Math.round(j.done / j.total * 100)) : 0;
      return '<div class="ag-meter"><div class="ag-meter-top"><span class="ag-label">' + esc(j.name) + '</span><span class="ag-pct num">' + p + '<small>%</small></span></div>' +
        '<div class="ag-bar"><i style="width:' + p + '%"></i></div>' +
        '<div class="ag-meter-foot"><span><b>' + big(j.done) + '</b> of ' + big(j.total) + ' ' + esc(j.unit) + '</span><span>' +
        (j.eta ? 'done ' + esc(until(j.eta)) : 'updated ' + esc(ago(j.updated))) + '</span></div></div>';
    }).join('');
    var procs = d.processes.length
      ? '<div class="ag-sub">Background: ' + d.processes.map(function (p) { return esc(p.label) + ' (since ' + esc(ago(p.since)) + ')'; }).join(', ') + '</div>' : '';
    return shell('long', head('long', 'Long jobs', d.jobs.length ? d.jobs.length + ' running' : '', '') +
      (bars || '<div class="ag-empty">No long jobs are reporting progress.</div>') + procs);
  }

  // 5. Power
  function power(c) {
    if (!c || !c.ok) return broken('power', 'Power', c);
    var d = c.data, max = Math.max.apply(null, d.hosts.map(function (h) { return h.d30; }).concat([0.01]));
    var rows = d.hosts.filter(function (h) { return h.d30 > 0 || h.watts; }).map(function (h) {
      return '<div class="ag-prow"><span>' + esc(h.name) + '</span><div class="ag-bar"><i style="width:' + Math.round(h.d30 / max * 100) + '%"></i></div><b class="num">' + money(h.d30) + '</b></div>';
    }).join('');
    return shell('power', head('power', 'Power', 'GPU only', '') +
      '<div class="ag-stats">' + stat(money(d.total.today), 'today') + stat(money(d.total.d7), '7 days') + stat(money(d.total.d30), '30 days') + '</div>' +
      (rows || '<div class="ag-empty">No GPU power measured yet.</div>') +
      '<div class="ag-sub">Measures GPU power only' + (d.pricePerKwh ? ', at $' + d.pricePerKwh.toFixed(3) + ' per kWh' : '') + '.</div>');
  }

  function render() {
    if (!V.el) return;
    var r = V.rep || {};
    var stale = !r.at || (Date.now() - new Date(r.at).getTime()) > 20 * 60000;
    V.el.innerHTML = '<div class="agents">' +
      '<header class="ag-top"><div><div class="label">Hermes · AI agents and fleet</div><h1 class="serif">Agents</h1></div>' +
      '<div class="ag-sync"><span class="label' + (stale ? ' is-stale' : '') + '">' + (r.at ? 'Report ' + esc(ago(r.at)) : 'No report yet') + '</span>' +
      '<button class="icon-btn" data-refresh aria-label="Refresh">' + App.icon('undo', 26) + '</button></div></header>' +
      '<div class="ag-grid">' + jobs(r.jobs) + usage(r.usage) + fleet(r.fleet) + longJobs(r.long) + power(r.power) + '</div>' +
      '</div>';
  }

  function load() {
    return App.api('GET', '/api/agents').then(function (rep) { V.rep = rep; V.fetched = Date.now(); render(); })
      .catch(function () { render(); });
  }

  App.register('agents', {
    show: function (el) {
      if (!V.el) {
        V.el = el;
        el.addEventListener('click', function (e) { if (e.target.closest('[data-refresh]')) load(); });
      }
      render();
      load();
    }
  });
  App.on('minute', function () {
    if (!V.el || !V.el.offsetParent) return;
    if (Date.now() - V.fetched > 60000) load(); else render();
  });
})();
