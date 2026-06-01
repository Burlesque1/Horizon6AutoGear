// ========== Horizon6AutoGear — Shared Pywebview API Layer ==========
// Theme HTML files include this and implement:
//   updateDashboard(data)  — render telemetry to theme-specific DOM
//   resetThemeDashboard()  — reset theme-specific DOM elements
//   initTheme()            — called after pywebview ready (optional)

// ========== GLOBAL STATE ==========
var _telemetryData = null;
var _shiftPoints = {};
var _settings = {};
var _i18n = {};
var _lang = 0;
var _liveTorqueData = {};
var _recordEnabled = false;

// 缓存常用DOM元素，避免重复查询
var _logPanel = document.getElementById('logPanel');
var _recBtn = document.getElementById('btnRecord');
var _clearLogBtn = document.getElementById('clearLogBtn');
var _themeSelect = document.getElementById('themeSelect');
var _settingsDrawer = document.getElementById('settingsDrawer');
var _settingsOverlay = document.getElementById('settingsOverlay');

// ========== UTILITY FUNCTIONS ==========

function tempColor(temp) {
  var stops = [
    {t:50, r:50, g:100, b:220},
    {t:75, r:0, g:200, b:100},
    {t:95, r:220, g:200, b:0},
    {t:120, r:240, g:60, b:40}
  ];
  if (temp <= stops[0].t) return stops[0];
  if (temp >= stops[3].t) return stops[3];
  for (var i = 0; i < 3; i++) {
    if (temp >= stops[i].t && temp <= stops[i+1].t) {
      var f = (temp - stops[i].t) / (stops[i+1].t - stops[i].t);
      return {
        r: Math.round(stops[i].r + (stops[i+1].r - stops[i].r) * f),
        g: Math.round(stops[i].g + (stops[i+1].g - stops[i].g) * f),
        b: Math.round(stops[i].b + (stops[i+1].b - stops[i].b) * f)
      };
    }
  }
  return stops[0];
}

function fmtTime(ms) {
  if (!ms || ms <= 0) return '0:00.000';
  var totalSec = ms / 1000;
  var m = Math.floor(totalSec / 60);
  var s = (totalSec % 60).toFixed(3);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function degToRad(d) { return d * Math.PI / 180; }

function rpmColor(pct) {
  if (pct < 0.4) return '#00ff88';
  if (pct < 0.55) { var f=(pct-0.4)/0.15; return 'rgb('+Math.round(255*f)+',255,'+Math.round(136*(1-f))+')'; }
  if (pct < 0.75) { var f2=(pct-0.55)/0.2; return 'rgb(255,'+Math.round(255-34*f2)+',0)'; }
  if (pct < 0.85) { var f3=(pct-0.75)/0.1; return 'rgb(255,'+Math.round(221-100*f3)+',0)'; }
  var f4=(pct-0.85)/0.15; return 'rgb(255,'+Math.round(121-121*f4)+','+Math.round(51*f4)+')';
}

function slipColor(val, warn, danger) {
  if (val > danger) return '#ff4466';
  if (val > warn) return '#ffdd00';
  return '#00ff88';
}

// ========== COACH HUD UTILITIES ==========
function coachLineNorm(raw) { return raw / 127.0; }
function coachBrakeState(rawDiff) {
  if (rawDiff >= 10) return 'green';
  if (rawDiff >= -5) return 'yellow';
  return 'red';
}
function coachGripState(combinedSlip) {
  if (combinedSlip < 0.5) return 'green';
  if (combinedSlip < 1.0) return 'yellow';
  return 'red';
}

// ========== PYWEBVIEW CALLBACKS ==========

window.onTelemetry = function(data) {
  _telemetryData = data;
  // Coach HUD dispatch (no-op if theme doesn't implement it)
  if (typeof updateCoachHUD === 'function') {
    var coachData = {
      drivingLine: data.norm_driving_line,
      aiBrakeDiff: data.norm_ai_brake_diff,
      tireSlips: {
        FL: data.combined_slip_FL,
        FR: data.combined_slip_FR,
        RL: data.combined_slip_RL,
        RR: data.combined_slip_RR
      }
    };
    updateCoachHUD(coachData);
  }
};

window.updateShiftPoints = function(data) {
  _shiftPoints = data;
  if (typeof updateShiftPointsUI === 'function') updateShiftPointsUI(data);
};

window.updateSettings = function(settings) {
  _settings = settings;
  if (typeof applySettings === 'function') applySettings(settings);
};

window.updateI18n = function(i18n, langIndex) {
  _i18n = i18n;
  _lang = langIndex;
  if (typeof applyI18n === 'function') applyI18n(i18n, langIndex);
};

window.updateCharts = function(base64Png) {
  if (typeof updateChartsUI === 'function') updateChartsUI(base64Png);
};

window.updateLiveTorqueData = function(data) {
  _liveTorqueData = data;
  if (typeof updateLiveTorqueUI === 'function') updateLiveTorqueUI(data);
};

window.resetDashboard = function() {
  _telemetryData = null;
  if (typeof resetThemeDashboard === 'function') resetThemeDashboard();
};

window.appendLog = function(msg) {
  if (_logPanel) {
    var line = document.createElement('div');
    line.textContent = msg;
    _logPanel.appendChild(line);
    _logPanel.scrollTop = _logPanel.scrollHeight;
    if (_logPanel.children.length > 500) {
      _logPanel.removeChild(_logPanel.firstChild);
    }
  }
};

// ========== RENDER LOOP ==========

function renderLoop() {
  if (_telemetryData) {
    if (typeof updateDashboard === 'function') updateDashboard(_telemetryData);
    _telemetryData = null;
  }
  requestAnimationFrame(renderLoop);
}
requestAnimationFrame(renderLoop);

// ========== PYWEBVIEW READY ==========

function _onReady() {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.init_app();
    window.pywebview.api.get_settings().then(function(settings) {
      if (settings) window.updateSettings(settings);
    }).catch(function() {});
    // Populate theme dropdown
    window.pywebview.api.get_themes().then(function(themes) {
      if (!themes) return;
      var sel = document.getElementById('themeSelect');
      if (!sel) return;
      // Disable change listener during population to prevent spurious switch_theme
      sel.disabled = true;
      sel.innerHTML = '';
      themes.forEach(function(t) {
        var opt = document.createElement('option');
        opt.value = t.id; opt.textContent = t.name;
        sel.appendChild(opt);
      });
      sel.disabled = false;
    }).catch(function() {});
  }
}

window.addEventListener('pywebviewready', _onReady);

// Fallback if already ready
if (window.pywebview && pywebview.api) {
  setTimeout(_onReady, 100);
}

// ========== HELPER: wire button safely ==========
function wireBtn(id, fn) {
  var el = document.getElementById(id);
  if (el) el.addEventListener('click', function() {
    if (window.pywebview && window.pywebview.api) fn(window.pywebview.api);
  });
}

// Standard action buttons — themes just need matching IDs
wireBtn('btnRun', function(api) { api.run(); });
wireBtn('btnObserve', function(api) { api.observe(); });
wireBtn('btnCollect', function(api) { api.collect(); });
wireBtn('btnAnalyze', function(api) { api.analyze(); });
wireBtn('btnPause', function(api) { api.pause(); });
wireBtn('btnPlayback', function(api) {
  api.list_recordings().then(function(files) {
    if (!files || !files.length) { appendLog('[Playback] No recordings found'); return; }
    showRecordingPicker(files, api);
  }).catch(function(e) { appendLog('[Playback] Error: ' + e); });
});
wireBtn('btnExit', function(api) { api.exit(); });

// Record toggle
if (_recBtn) {
  _recBtn.addEventListener('click', function() {
    _recordEnabled = !_recordEnabled;
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.toggle_record(_recordEnabled);
    }
    _recBtn.textContent = _recordEnabled ? 'STOP REC' : 'REC';
    _recBtn.style.borderColor = _recordEnabled ? '#ff4466' : '';
    _recBtn.style.color = _recordEnabled ? '#ff4466' : '';
  });
}

// Clear log
if (_clearLogBtn) {
  _clearLogBtn.addEventListener('click', function() {
    if (_logPanel) _logPanel.innerHTML = '';
  });
}

// Settings event helpers — buffered, applied on Confirm
var _pendingSettings = {};
function wireSettings() {
  var ipEl = document.getElementById('settingIp');
  if (ipEl) ipEl.addEventListener('change', function() {
    _pendingSettings['ip'] = this.value;
  });
  var portEl = document.getElementById('settingPort');
  if (portEl) portEl.addEventListener('change', function() {
    _pendingSettings['port'] = this.value;
  });
  var langEl = document.getElementById('settingLang');
  if (langEl) langEl.addEventListener('change', function() {
    _pendingSettings['language'] = parseInt(this.value);
  });
  function toggleSwitch(el, key) {
    if (!el) return;
    el.addEventListener('click', function() {
      this.classList.toggle('active');
      var track = this.querySelector('.toggle-track');
      if (track) track.classList.toggle('active', this.classList.contains('active'));
      _pendingSettings[key] = this.classList.contains('active');
    });
  }
  toggleSwitch(document.getElementById('toggleClutch'), 'clutch');
  toggleSwitch(document.getElementById('toggleFarm'), 'farm');
  toggleSwitch(document.getElementById('toggleOffroad'), 'offroad');
  toggleSwitch(document.getElementById('toggleTcs'), 'tcs');

  // TCS range inputs
  ['tcsSlipThreshold', 'tcsThrottleReduction', 'tcsRecoveryMargin'].forEach(function(id) {
    var el = document.getElementById(id);
    var valEl = document.getElementById(id + 'Val');
    if (el) el.addEventListener('input', function() {
      if (valEl) valEl.textContent = this.value;
      _pendingSettings[id] = parseFloat(this.value);
    });
  });

  // Shortcut dropdowns
  var shortcutKeys = ['clutch', 'upshift', 'downshift'];
  shortcutKeys.forEach(function(key) {
    var sel = document.getElementById('shortcut' + key.charAt(0).toUpperCase() + key.slice(1));
    if (sel) sel.addEventListener('change', function() {
      _pendingSettings['shortcut_' + key] = this.value;
    });
  });

  var themeEl = document.getElementById('themeSelect');
  if (themeEl) themeEl.addEventListener('change', function() {
    _pendingSettings['theme'] = this.value;
  });

  // Confirm button — apply all pending settings
  var confirmBtn = document.getElementById('settingsConfirm');
  if (confirmBtn) confirmBtn.addEventListener('click', function() {
    if (!window.pywebview || !window.pywebview.api) return;
    var api = window.pywebview.api;
    if ('ip' in _pendingSettings) api.set_setting('ip', _pendingSettings.ip);
    if ('port' in _pendingSettings) api.set_setting('port', _pendingSettings.port);
    if ('language' in _pendingSettings) api.set_language(_pendingSettings.language);
    if ('clutch' in _pendingSettings) api.set_clutch(_pendingSettings.clutch);
    if ('farm' in _pendingSettings) api.toggle_farm(_pendingSettings.farm);
    if ('theme' in _pendingSettings) api.switch_theme(_pendingSettings.theme);
    if ('offroad' in _pendingSettings) api.toggle_offroad(_pendingSettings.offroad);
    if ('tcs' in _pendingSettings) api.toggle_tcs();
    if ('tcsSlipThreshold' in _pendingSettings || 'tcsThrottleReduction' in _pendingSettings || 'tcsRecoveryMargin' in _pendingSettings) {
      api.set_tcs_params(
        _pendingSettings.tcsSlipThreshold || null,
        _pendingSettings.tcsThrottleReduction || null,
        _pendingSettings.tcsRecoveryMargin || null
      );
    }
    if ('shortcut_clutch' in _pendingSettings) api.set_shortcut('clutch', _pendingSettings.shortcut_clutch);
    if ('shortcut_upshift' in _pendingSettings) api.set_shortcut('upshift', _pendingSettings.shortcut_upshift);
    if ('shortcut_downshift' in _pendingSettings) api.set_shortcut('downshift', _pendingSettings.shortcut_downshift);
    _pendingSettings = {};
    closeSettings();
  });
}
wireSettings();

// Settings drawer
var sTrigger = document.getElementById('settingsTrigger');
var sClose = document.getElementById('settingsClose');

function openSettings() {
  if (_settingsDrawer) _settingsDrawer.classList.add('active');
  if (_settingsOverlay) _settingsOverlay.classList.add('active');
  // Populate shortcut dropdowns from backend
  if (window.pywebview && window.pywebview.api && _settings.shortcuts) {
    var sc = _settings.shortcuts || {};
    var keys = ['clutch', 'upshift', 'downshift'];
    keys.forEach(function(key) {
      var sel = document.getElementById('shortcut' + key.charAt(0).toUpperCase() + key.slice(1));
      if (!sel) return;
      var current = sc[key] || '';
      window.pywebview.api.get_available_shortcuts(current).then(function(available) {
        sel.innerHTML = '';
        (available || []).forEach(function(k) {
          var opt = document.createElement('option');
          opt.value = k; opt.textContent = k;
          if (k === current) opt.selected = true;
          sel.appendChild(opt);
        });
      }).catch(function() {});
    });
  }
}
function closeSettings() {
  if (_settingsDrawer) _settingsDrawer.classList.remove('active');
  if (_settingsOverlay) _settingsOverlay.classList.remove('active');
}
if (sTrigger) sTrigger.addEventListener('click', openSettings);
if (sClose) sClose.addEventListener('click', closeSettings);
if (_settingsOverlay) _settingsOverlay.addEventListener('click', closeSettings);
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeSettings();
  // Suppress browser default for function keys handled by pynput backend
  if (e.key.startsWith('F') && /^F\d+$/.test(e.key)) e.preventDefault();
});

// Theme switching — event listener only; population happens in _onReady()
if (_themeSelect) {
  _themeSelect.addEventListener('change', function() {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.switch_theme(_themeSelect.value);
    }
  });
}

function showRecordingPicker(files, api) {
  var overlay = document.getElementById('recordingOverlay');
  var list = document.getElementById('recordingList');
  if (!overlay || !list) return;
  list.innerHTML = '';
  files.forEach(function(f) {
    var item = document.createElement('div');
    item.textContent = f.name + '  (' + f.packets + ' pkts, ' + f.duration + 's)';
    item.style.cssText = 'padding:8px;border:1px solid #000;margin:4px 0;cursor:pointer;';
    item.addEventListener('click', function() {
      overlay.style.display = 'none';
      api.start_playback(f.path);
    });
    list.appendChild(item);
  });
  var cancelBtn = document.createElement('button');
  cancelBtn.textContent = 'Cancel';
  cancelBtn.addEventListener('click', function() { overlay.style.display = 'none'; });
  list.appendChild(cancelBtn);
  overlay.style.display = 'block';
}

// Call theme init if defined
if (typeof initTheme === 'function') initTheme();

// ========== SHARED i18n HELPER ==========
// Themes add data-i18n="FIELD_NAME" to elements. applyI18n replaces their text.
// Supports: data-i18n="FIELD" (textContent), data-i18n-placeholder="FIELD" (placeholder)
// Also applies button text via wireBtnI18n mapping.
function applyI18n(i18n, lang) {
  if (!i18n) return;
  var L = lang || 0;
  function txt(key) {
    var v = i18n[key];
    return (v && v[L]) || '';
  }
  // Update all [data-i18n] elements
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    var val = txt(key);
    if (val) el.textContent = val;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-placeholder');
    var val = txt(key);
    if (val) el.placeholder = val;
  });
  // Update button text (preserving icon prefixes)
  var btnMap = {
    'btnRun': ['RUN_BUTTON_TXT', '▶ '],
    'btnObserve': ['OBSERVE_BUTTON_TXT', '◉ '],
    'btnCollect': ['COLLECT_BUTTON_TXT', '● '],
    'btnAnalyze': ['ANALYSIS_BUTTON_TXT', '∫ '],
    'btnPause': ['PAUSE_BUTTON_TXT', '◼ '],
    'btnExit': ['EXIT_BUTTON_TXT', '✖ '],
    'btnPlayback': ['PLAYBACK_TXT', '◪ '],
    'clearLogBtn': ['CLEAR_LOG_TXT', ''],
  };
  Object.keys(btnMap).forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.textContent = (btnMap[id][1] || '') + txt(btnMap[id][0]);
  });
  // Language dropdown label
  var langLabel = document.querySelector('[data-i18n-label="language"]');
  if (langLabel) langLabel.textContent = txt('SELECT_LANGUAGE_TXT');
}
