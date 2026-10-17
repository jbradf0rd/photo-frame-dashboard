// Family data template. Edit this file for your household. Loaded after data.js; replaces the demo family, chores and lists.
// Shared state (chores done, stars, shopping, Quran progress) is loaded from and saved to the
// family-frame server by sync.js, so this file is only the first-run default.
(function () {
  'use strict';
  var D = window.DATA;

  D.config = {
    place: 'New York, NY',
    lat: 40.7128, lon: -74.0060,          // your home coordinates
    method: 'ISNA', madhab: 'Shafi',
    hijri: 'islamic-umalqura',
    adhanVolume: { fajr: 1.0, dhuhr: 0.6, asr: 0.6, maghrib: 0.6, isha: 0.6 }
  };

  D.people = [
    { id: 'dad', name: 'Dad', color: '#111827', rgb: '17 24 39', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'r', name: 'Mom', color: '#2D5BFF', rgb: '45 91 255', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'h', name: 'Child 1', color: '#00A36C', rgb: '0 163 108', ink: '#FFFFFF', home: true, status: 'Home' },
    { id: 'a', name: 'Child 2', color: '#E4007C', rgb: '228 0 124', ink: '#FFFFFF', home: true, status: 'Home' }
  ];
  D.ALL = D.people.map(function (p) { return p.id; });
  // Whose Google calendar each pushed feed belongs to. Set this to the person whose calendar you push.
  D.calendarOwner = 'dad';
  D.family = { id: 'family', name: 'Family', color: '#111111', rgb: '17 17 17', ink: '#FFFFFF' };

  // Calendar events come from the family Google calendar through the server (sync.js).
  D.events = [];
  D.busyExtras = [];

  // Starter chores. Edit freely; ticks and stars are saved on the server.
  var cid = 0;
  function chore(r, who, title, emoji, stars) {
    return { id: 'c' + (++cid), r: r, who: who, title: title, emoji: emoji, stars: stars, done: false };
  }
  D.routines = [
    { id: 'morning', name: 'Morning', range: 'Fajr – 11 AM', from: 0, to: 11 },
    { id: 'after', name: 'After school', range: '11 AM – 5 PM', from: 11, to: 17 },
    { id: 'evening', name: 'Evening', range: '5 – 10 PM', from: 17, to: 24 }
  ];
  D.chores = [
    chore('morning', 'h', 'Pray Fajr', '🕌', 2),
    chore('morning', 'a', 'Pray Fajr', '🕌', 2),
    chore('morning', 'h', 'Make bed', '🛏️', 1),
    chore('morning', 'a', 'Make bed', '🛏️', 1),
    chore('after', 'h', 'Homework', '📚', 2),
    chore('after', 'a', 'Homework', '📚', 2),
    chore('after', 'h', 'Quran review', '📖', 2),
    chore('after', 'a', 'Quran review', '📖', 2),
    chore('after', 'any', 'Empty dishwasher', '🍽️', 1),
    chore('evening', 'h', 'Clear the table', '🍽️', 1),
    chore('evening', 'a', 'Set the table', '🍴', 1),
    chore('evening', 'any', 'Take out the trash', '🗑️', 1),
    chore('evening', 'r', 'Lock up', '🔐', 0)
  ];
  D.stars = { h: 0, a: 0 };
  D.week = { h: [null, null, null, null, null, null, null], a: [null, null, null, null, null, null, null] };

  // Quran memorization: one row per child, juz/surah progress. Saved on the server.
  D.quran = {
    h: { surah: '', note: '', done: [] },
    a: { surah: '', note: '', done: [] }
  };

  // Adhan volume, 0 to 1, on top of the frame speaker (set to its maximum). Saved on the server.
  D.volume = { fajr: 1.0, other: 0.6 };

  D.groceries = [];
  D.messages = [];
  D.alert = null;

  // Weather starts empty and is filled from Open-Meteo through the server.
  D.weather = { hi: '–', lo: '–', t: [], c: [], p: [], live: false };
  D.photos = [];
})();
