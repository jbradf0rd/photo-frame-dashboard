// Work: Zoho task counts for up to two people (FRAME_WORK_PEOPLE), and mail drafts. Reads the same report as the
// Agents tab (GET /api/agents, pushed by frame_agents_push.py). Counts only: no client names,
// project names, task titles or mail subjects reach this page.
(function () {
  'use strict';
  var V = { el: null, rep: null, fetched: 0 };
  var PALETTE = [['#111827', '17 24 39'], ['#2D5BFF', '45 91 255']];

  function esc(s) { return App.esc(String(s == null ? '' : s)); }
  function ago(isoStr) {
    if (!isoStr) return 'never';
    var m = Math.round((Date.now() - new Date(isoStr).getTime()) / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return m + ' min ago';
    if (m < 1440) return Math.floor(m / 60) + ' hr ago';
    return Math.floor(m / 1440) + ' days ago';
  }
  function stat(n, label, warn) {
    return '<div class="wk-stat' + (warn ? ' is-warn' : '') + '"><span class="num">' + (n == null ? '–' : n) + '</span><small>' + esc(label) + '</small></div>';
  }

  function person(name, color, rgb, p) {
    var active = p.open - p.onHold;
    var seg = function (n, cls) { return n > 0 ? '<i class="' + cls + '" style="flex-grow:' + n + '"></i>' : ''; };
    var ok = p.overdue === 0;
    return '<section class="ag-card wk-person" style="--c:' + color + ';--c-rgb:' + rgb + '">' +
      '<header class="ag-head"><div class="ag-id"><i class="ag-swatch"></i><b>' + esc(name) + '</b></div>' +
      '<span class="ag-status' + (ok ? '' : ' is-warn') + '"><i></i>' + (ok ? 'Nothing overdue' : p.overdue + ' overdue') + '</span></header>' +
      '<div class="wk-hero"><span class="num">' + p.open + '</span><small>open tasks</small></div>' +
      '<div class="wk-split">' + seg(p.overdue, 'is-over') + seg(p.dueWeek, 'is-week') + seg(Math.max(0, active - p.overdue - p.dueWeek), 'is-rest') + seg(p.onHold, 'is-hold') + '</div>' +
      '<div class="wk-stats">' + stat(p.overdue, 'overdue', p.overdue > 0) + stat(p.dueWeek, 'due this week') +
      stat(p.inProgress, 'in progress') + stat(p.noDate, 'no due date') + stat(p.onHold, 'on hold') + '</div>' +
      '</section>';
  }

  function render() {
    if (!V.el) return;
    var r = V.rep || {}, c = r.waiting;
    var body;
    if (!c || !c.ok) {
      body = '<div class="ag-empty">' + esc(c && c.error ? 'Could not read Zoho: ' + c.error : 'Waiting for the first report') + '</div>';
    } else {
      var d = c.data;
      body = '<div class="wk-grid">' +
        (d.people || []).slice(0, 2).map(function (p, i) {
          return person(p.label, PALETTE[i][0], PALETTE[i][1], p);
        }).join('') +
        '<section class="ag-card wk-side" style="--c:#7A3FD1;--c-rgb:122 63 209">' +
        '<header class="ag-head"><div class="ag-id"><i class="ag-swatch"></i><b>Overview</b></div></header>' +
        '<div class="wk-stats wk-stats--col">' + stat(d.drafts, d.draftsLabel || 'mail drafts, last 30 days') + stat(d.projects, 'projects with open tasks') +
        stat(d.unassigned, 'tasks with no owner', d.unassigned > 0) + '</div>' +
        '<div class="ag-sub">Zoho tasks checked ' + esc(ago(d.snapshot)) + '.</div>' +
        '</section></div>';
    }
    V.el.innerHTML = '<div class="agents work">' +
      '<header class="ag-top"><div><div class="label">Zoho Projects · mail</div><h1 class="serif">Work</h1></div>' +
      '<div class="ag-sync"><span class="label">' + (r.at ? 'Report ' + esc(ago(r.at)) : 'No report yet') + '</span>' +
      '<button class="icon-btn" data-refresh aria-label="Refresh">' + App.icon('undo', 26) + '</button></div></header>' +
      body + '</div>';
  }

  function load() {
    return App.api('GET', '/api/agents').then(function (rep) { V.rep = rep; V.fetched = Date.now(); render(); })
      .catch(function () { render(); });
  }

  App.register('work', {
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
