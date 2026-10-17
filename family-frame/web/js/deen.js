// Prayer times, Adhan, Hijri calendar, #alert takeover, message board, and sync with the server.
import { Coordinates, CalculationMethod, PrayerTimes, Madhab } from 'adhan';

(function () {
  'use strict';
  var D = window.DATA, $ = App.$;
  var C = D.config;
  var coords = new Coordinates(C.lat, C.lon);
  var params = CalculationMethod.NorthAmerica();          // ISNA: Fajr 15°, Isha 15°
  params.madhab = C.madhab === 'Hanafi' ? Madhab.Hanafi : Madhab.Shafi;

  // ------------------------------------------------------------ prayer times
  var NAMES = [
    { id: 'fajr', name: 'Fajr' }, { id: 'sunrise', name: 'Sunrise', noAdhan: true },
    { id: 'dhuhr', name: 'Dhuhr' }, { id: 'asr', name: 'Asr' },
    { id: 'maghrib', name: 'Maghrib' }, { id: 'isha', name: 'Isha' }
  ];
  var cache = {};
  App.prayers = function (day) {
    var d = App.dayStart(day || App.now());
    var k = d.toDateString();
    if (!cache[k]) {
      var pt = new PrayerTimes(coords, d, params);
      cache[k] = NAMES.map(function (n) {
        var name = n.id === 'dhuhr' && d.getDay() === 5 ? 'Jumuah' : n.name;
        return { id: n.id, name: name, time: pt[n.id], adhan: !n.noAdhan };
      });
    }
    return cache[k];
  };
  // Next prayer with an Adhan (skips sunrise), looking into tomorrow after Isha.
  App.nextPrayer = function () {
    var now = App.now();
    var list = App.prayers(now).concat(App.prayers(App.addDays(now, 1)));
    for (var i = 0; i < list.length; i++) if (list[i].adhan && list[i].time > now) return list[i];
    return null;
  };
  App.currentPrayer = function () {
    var now = App.now(), cur = null;
    App.prayers(now).forEach(function (p) { if (p.adhan && p.time <= now) cur = p; });
    return cur;
  };

  // ------------------------------------------------------------ Hijri (Umm al-Qura)
  var HMONTHS = ['Muharram', 'Safar', "Rabi' al-Awwal", "Rabi' al-Thani", 'Jumada al-Ula', 'Jumada al-Akhirah',
    'Rajab', "Sha'ban", 'Ramadan', 'Shawwal', "Dhu al-Qa'dah", 'Dhu al-Hijjah'];
  var hfmt = null;
  try { hfmt = new Intl.DateTimeFormat('en-US-u-ca-' + C.hijri, { day: 'numeric', month: 'numeric', year: 'numeric' }); } catch (e) { hfmt = null; }
  App.hijri = function (d) {
    if (!hfmt) return null;
    var parts = {};
    hfmt.formatToParts(new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12)).forEach(function (p) { parts[p.type] = p.value; });
    var m = parseInt(parts.month, 10), day = parseInt(parts.day, 10), y = parseInt(parts.year || parts.relatedYear, 10);
    if (!m || !day) return null;
    return { day: day, month: m, year: y, monthName: HMONTHS[m - 1], text: day + ' ' + HMONTHS[m - 1] + ' ' + y + ' AH' };
  };
  // Islamic days for a civil date: Ramadan, both Eids, Arafah, Ashura, the white days.
  App.islamicDay = function (d) {
    var h = App.hijri(d);
    if (!h) return null;
    if (h.month === 10 && h.day === 1) return { title: 'Eid al-Fitr', big: true };
    if (h.month === 12 && h.day === 10) return { title: 'Eid al-Adha', big: true };
    if (h.month === 12 && h.day === 9) return { title: 'Day of Arafah', big: true };
    if (h.month === 1 && h.day === 10) return { title: 'Ashura', big: false };
    if (h.month === 1 && h.day === 1) return { title: 'Islamic New Year', big: false };
    if (h.month === 9) return { title: 'Ramadan ' + h.day, big: h.day === 1 };
    if (h.day >= 13 && h.day <= 15) return { title: 'White day (' + h.day + ')', big: false };
    return null;
  };
  App.upcomingIslamic = function (days) {
    var out = [], d = App.dayStart(App.now()), seenRamadan = false;
    for (var i = 0; i < (days || 400) && out.length < 6; i++) {
      var x = App.addDays(d, i), ev = App.islamicDay(x);
      if (!ev) continue;
      if (/^White day/.test(ev.title) && out.some(function (o) { return /^White day/.test(o.title); })) continue;
      if (/^Ramadan/.test(ev.title)) { if (seenRamadan) continue; seenRamadan = true; ev = { title: 'Ramadan begins', big: true }; }
      out.push({ date: x, title: ev.title, big: ev.big, hijri: App.hijri(x) });
    }
    return out;
  };

  // ------------------------------------------------------------ Adhan
  var audio = { el: null };
  function played(key) { try { return localStorage.getItem('adhan:' + key) === '1'; } catch (e) { return false; } }
  function markPlayed(key) { try { localStorage.setItem('adhan:' + key, '1'); } catch (e) {} }
  App.playAdhan = function (p, test) {
    if (audio.el) { audio.el.pause(); audio.el = null; }
    var a = new Audio(p.id === 'fajr' ? '/audio/adhan-fajr.mp3' : '/audio/adhan.mp3');
    var v = D.volume || { fajr: 1, other: 0.6 };
    a.volume = Math.max(0, Math.min(1, p.id === 'fajr' ? v.fajr : v.other));
    audio.el = a;
    var el = App.takeover(
      '<div class="tk-alarm tk-adhan">' +
      '  <div class="label label--light">' + (test ? 'Test · ' : '') + App.fmt.time(p.time) + '</div>' +
      '  <h1 class="tk-huge">' + p.name + '</h1>' +
      '  <p class="tk-sub">Adhan</p>' +
      '  <div class="tk-actions"><button class="tk-btn tk-btn--solid tk-btn--light" data-stop>' + App.icon('x', 30) + '<span>Stop</span></button></div>' +
      '</div>', 'takeover--adhan');
    function done() { if (audio.el === a) { a.pause(); audio.el = null; } if (!D.alert) App.closeTakeover(); }
    el.querySelector('[data-stop]').onclick = done;
    a.addEventListener('ended', done);
    var pr = a.play();
    if (pr && pr.catch) pr.catch(function (err) { App.toast('Adhan could not play: ' + App.esc(err.name), { icon: 'bell' }); });
  };
  function adhanTick() {
    var now = App.now();
    App.prayers(now).forEach(function (p) {
      if (!p.adhan) return;
      var key = now.toDateString() + ':' + p.id, late = now - p.time;
      if (late >= 0 && late < 120000 && !played(key)) { markPlayed(key); App.playAdhan(p); }
    });
  }

  // ------------------------------------------------------------ server sync
  var KEYS = ['shopping', 'chores', 'stars', 'week', 'quran', 'volume'];
  function toServer(k) { return k === 'shopping' ? D.groceries : D[k]; }
  function fromServer(k, v) { if (v == null) return; if (k === 'shopping') D.groceries = v; else D[k] = v; }
  App.api = function (method, path, body) {
    return fetch(path, { method: method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  };
  var lastSaved = {}, saveTimer = null, loaded = false;
  function saveAll() {
    if (!loaded) return;
    KEYS.forEach(function (k) {
      var s = JSON.stringify(toServer(k));
      if (s !== lastSaved[k]) { lastSaved[k] = s; App.api('POST', '/api/state/' + k, { value: toServer(k) }).catch(function () { lastSaved[k] = null; }); }
    });
  }
  App.on('data', function () { clearTimeout(saveTimer); saveTimer = setTimeout(saveAll, 800); });

  function applyState(s) {
    var changed = false;
    KEYS.forEach(function (k) {
      if (s[k] == null) return;
      var str = JSON.stringify(s[k]);
      if (str !== lastSaved[k]) { lastSaved[k] = str; fromServer(k, s[k]); changed = true; }
    });
    var msgs = JSON.stringify(s.messages || []);
    if (msgs !== JSON.stringify(D.messages)) { D.messages = s.messages || []; changed = true; App.emit('messages'); }
    showAlert(s.alert || null);
    return changed;
  }
  function resetChoresIfNewDay() {
    var today = App.dayStart(App.now()).toDateString(), key = 'choresDay';
    var last = null; try { last = localStorage.getItem(key); } catch (e) {}
    if (last && last !== today) {
      D.chores.forEach(function (c) { c.done = false; delete c.doneBy; });
      App.emit('data');
    }
    try { localStorage.setItem(key, today); } catch (e) {}
  }
  function pullState(first) {
    return App.api('GET', '/api/state').then(function (s) {
      var changed = applyState(s);
      if (first) { loaded = true; resetChoresIfNewDay(); saveAll(); App.rerender(); App.emit('data'); }
      else if (changed) { App.rerender(); App.emit('data'); }
    }).catch(function () { if (first) { loaded = true; } });
  }

  // ------------------------------------------------------------ #alert takeover
  var shownAlert = null;
  var chime = null;
  function playChime() {
    try {
      if (chime) { chime.pause(); chime = null; }
      chime = new Audio('/audio/chime.mp3');
      chime.volume = 0.8;
      var p = chime.play();
      if (p && p.catch) p.catch(function () {});
      chime.addEventListener('ended', function () { chime = null; });
    } catch (e) {}
  }
  function showAlert(a) {
    if (!a) { if (shownAlert) { shownAlert = null; D.alert = null; App.closeTakeover(); } return; }
    if (shownAlert === a.id) return;
    shownAlert = a.id; D.alert = a;
    playChime();
    var el = App.takeover(
      '<div class="tk-alarm tk-msg">' +
      '  <div class="label label--light">' + App.icon('bell', 20) + ' Message from ' + (a.from || 'home') + ' · ' + App.fmt.time(new Date(a.at)) + '</div>' +
      '  <h1 class="tk-alert-text">' + App.esc(a.text) + '</h1>' +
      '  <div class="tk-actions"><button class="tk-btn tk-btn--solid tk-btn--light" data-ok>' + App.icon('check', 30) + '<span>Got it</span></button></div>' +
      '</div>', 'takeover--alert');
    el.querySelector('[data-ok]').onclick = function () {
      App.api('POST', '/api/alert/dismiss', { id: a.id }).catch(function () {});
      shownAlert = null; D.alert = null; App.closeTakeover();
    };
  }

  // ------------------------------------------------------------ weather (Open-Meteo through the server)
  function wxIcon(code, day) {
    if (code >= 51) return 'rain';
    if (code >= 45) return 'cloud';
    if (code === 3) return 'cloud';
    if (code === 1 || code === 2) return 'partly';
    return day ? 'sun' : 'moon';
  }
  function pullWeather() {
    return App.api('GET', '/api/weather').then(function (w) {
      var today = App.dayStart(App.now()), W = { t: [], c: [], p: [], live: true };
      w.hourly.time.forEach(function (ts, i) {
        var d = new Date(ts);
        if (!App.sameDay(d, today)) return;
        var h = d.getHours();
        W.t[h] = Math.round(w.hourly.temperature_2m[i]);
        W.p[h] = w.hourly.precipitation_probability[i] || 0;
        W.c[h] = wxIcon(w.hourly.weather_code[i], w.hourly.is_day[i]);
      });
      W.hi = Math.round(w.daily.temperature_2m_max[0]);
      W.lo = Math.round(w.daily.temperature_2m_min[0]);
      W.feels = Math.round(w.current.apparent_temperature);
      W.humidity = w.current.relative_humidity_2m;
      W.wind = Math.round(w.current.wind_speed_10m);
      W.days = w.daily.time.map(function (ts, i) {
        return { date: new Date(ts + 'T12:00'), hi: Math.round(w.daily.temperature_2m_max[i]), lo: Math.round(w.daily.temperature_2m_min[i]),
          c: wxIcon(w.daily.weather_code[i], 1), p: w.daily.precipitation_probability_max[i] || 0 };
      });
      if (W.t.length === 24) { D.weather = W; App.emit('weather'); App.emit('data'); }
    }).catch(function () {});
  }

  // ------------------------------------------------------------ family calendar (ICS through the server)
  function pullCalendar() {
    return App.api('GET', '/api/calendar').then(function (r) {
      if (!r.feeds) return;
      var n = 0;
      D.events = r.events.map(function (e) {
        return { id: 'k' + (++n), title: e.title, loc: e.loc, allDay: e.allDay, start: new Date(e.start), end: new Date(e.end), people: [e.owner || D.calendarOwner] };
      });
      App.emit('data');
    }).catch(function () {});
  }

  App.on('ready', function () {
    pullState(true);
    pullWeather();
    pullCalendar();
    setInterval(function () { pullState(false); }, 10000);
    setInterval(pullWeather, 20 * 60000);
    setInterval(pullCalendar, 10 * 60000);
    setInterval(adhanTick, 5000);
    App.on('minute', function (n) { if (n.getHours() === 0 && n.getMinutes() === 1) { cache = {}; resetChoresIfNewDay(); App.rerender(); } });
  });
})();
