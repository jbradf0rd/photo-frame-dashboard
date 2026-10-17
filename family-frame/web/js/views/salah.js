// Salah: today's prayer times, the Hijri date, coming Islamic days, and Quran progress.
(function () {
  'use strict';
  var D = window.DATA, V = {};

  function countdown(t) {
    var m = Math.max(0, Math.round((t - App.now()) / 60000));
    return m < 60 ? m + ' min' : Math.floor(m / 60) + ' hr ' + (m % 60) + ' min';
  }

  function times() {
    var now = App.now(), next = App.nextPrayer(), cur = App.currentPrayer();
    return App.prayers(now).map(function (p) {
      var cls = 'sl-row' + (next && next.id === p.id && App.sameDay(next.time, now) ? ' is-next' : '') +
        (cur && cur.id === p.id ? ' is-now' : '') + (p.adhan ? '' : ' is-minor') + (p.time < now ? ' is-past' : '');
      return '<div class="' + cls + '"><span class="sl-name">' + p.name + '</span>' +
        '<span class="sl-time num">' + App.fmt.time(p.time, false) + '<small>' + App.fmt.ampm(p.time) + '</small></span>' +
        (next && next.id === p.id && App.sameDay(next.time, now) ? '<span class="sl-in">in ' + countdown(p.time) + '</span>' : '<span class="sl-in"></span>') +
        '</div>';
    }).join('');
  }

  function head() {
    var now = App.now(), h = App.hijri(now), next = App.nextPrayer(), today = App.islamicDay(now);
    return '<div class="sl-hijri serif">' + (h ? h.day + ' ' + h.monthName + ' <i>' + h.year + '</i>' : 'Hijri date unavailable') + '</div>' +
      '<div class="sl-civil">' + App.fmt.day(now) + ', ' + App.fmt.month(now) + ' ' + now.getDate() + (today ? ' · <b>' + App.esc(today.title) + '</b>' : '') + '</div>' +
      (next ? '<div class="sl-next"><span class="label">Next prayer</span><b class="serif">' + next.name + '</b><span class="num">' + App.fmt.time(next.time) + ' · in ' + countdown(next.time) + '</span></div>' : '');
  }

  function upcoming() {
    return '<div class="label">Coming up</div>' + App.upcomingIslamic(400).map(function (e) {
      var days = Math.round((App.dayStart(e.date) - App.dayStart(App.now())) / 864e5);
      return '<div class="sl-up' + (e.big ? ' is-big' : '') + '"><b>' + App.esc(e.title) + '</b>' +
        '<span>' + (days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : 'in ' + days + ' days') + ' · ' + App.fmt.monthShort(e.date) + ' ' + e.date.getDate() +
        (e.hijri ? ' · ' + e.hijri.day + ' ' + e.hijri.monthName : '') + '</span></div>';
    }).join('');
  }

  function quran() {
    return '<div class="label">Quran memorization</div>' + Object.keys(D.quran || {}).map(function (id) {
      var q = D.quran[id], p = App.person(id);
      return '<button class="sl-q" data-q="' + id + '" style="' + App.pstyle(p) + '">' + App.avatar(p, 40) +
        '<span><b>' + p.name + '</b><small>' + (q.surah ? 'Now on ' + App.esc(q.surah) : 'Tap to set the surah') + '</small></span>' +
        '<span class="sl-q-n num">' + (q.done || []).length + '<small>surahs done</small></span></button>';
    }).join('');
  }

  function quranSheet(id) {
    var q = D.quran[id], p = App.person(id);
    App.sheet('<div class="label">Quran · ' + p.name + '</div><h2 class="serif">Which surah now?</h2>' +
      '<input class="sl-input" value="' + App.esc(q.surah || '') + '" placeholder="Surah name">' +
      '<div class="sl-sheet-actions"><button class="btn" data-save>Save</button>' +
      (q.surah ? '<button class="btn btn--solid" data-finish>Finished ' + App.esc(q.surah) + ' ✓</button>' : '') + '</div>', {
      onMount: function (el, close) {
        var inp = el.querySelector('.sl-input');
        el.querySelector('[data-save]').onclick = function () { q.surah = inp.value.trim(); App.emit('data'); paint(); close(); };
        var f = el.querySelector('[data-finish]');
        if (f) f.onclick = function () {
          q.done = (q.done || []).concat([{ surah: q.surah, at: new Date().toISOString() }]);
          if (D.stars[id] != null) D.stars[id] += 5;
          App.toast('Masha Allah, ' + App.esc(p.name) + '! +5 stars', { icon: 'star' });
          q.surah = ''; App.emit('data'); paint(); close();
        };
      }
    });
  }

  function paint() {
    if (!V.el) return;
    V.el.querySelector('.sl-head').innerHTML = head();
    V.el.querySelector('.sl-times').innerHTML = times();
    V.el.querySelector('.sl-upcoming').innerHTML = upcoming();
    V.el.querySelector('.sl-quran').innerHTML = quran();
  }

  App.register('salah', {
    minutely: true,
    show: function (el) {
      V.el = el;
      if (!el.firstChild) {
        el.innerHTML = '<div class="salah"><div class="sl-left"><div class="sl-head"></div><div class="sl-times card"></div></div>' +
          '<div class="sl-right"><div class="sl-upcoming card"></div><div class="sl-quran card"></div></div></div>';
        el.addEventListener('click', function (e) {
          var q = e.target.closest('[data-q]');
          if (q) quranSheet(q.dataset.q);
        });
      }
      paint();
    }
  });
  App.on('minute', function () { if (App.current === 'salah') paint(); });
  App.on('data', function () { if (App.current === 'salah') paint(); });
})();
