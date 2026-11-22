'use strict';
// The game's video settings (DriftCity Dev Ed/Data/Init/goption.ini) and the server address
// (DriftCityLauncher.ini [server], [client] display / main_ui_type).
const fs = require('fs');
const path = require('path');
const C = require('./core');

function goption() { return path.join(C.P().client, 'Data', 'Init', 'goption.ini'); }
function defOption() { return path.join(C.P().client, 'Data', 'Init', 'def_option.ini'); }
const bool = (v) => String(v).trim().toLowerCase() === 'true' || String(v).trim() === '1';

const ADV_KEYS = ['VehicleShadow', 'ShowObjectShadow', 'ShadowRange', 'ShadowMapType', 'CarTextureQuality', 'ObjectTextureQuality',
  'TerrainTextureQuality', 'CarShader', 'EnvMapType', 'Hdr', 'DofType', 'AniVisibleRange', 'ObjectAnimation', 'BattleAnimation',
  'ShowEffectMine', 'ShowEffectUsers'];

function readVideo() {
  const g = C.iniRead(goption());
  const l = C.iniRead(path.join(C.P().client, 'DriftCityLauncher.ini'));
  const num = (k, d) => (g[`Graphic.${k}`] !== undefined ? parseInt(g[`Graphic.${k}`], 10) : d);
  return {
    exists: fs.existsSync(goption()),
    width: num('ScreenWidth', 1366), height: num('ScreenHeight', 768),
    fullscreen: (l['client.display'] || '').toLowerCase() === 'fullscreen' || bool(g['Graphic.Fullscreen'] || 'false'),
    // the HUD the game really uses: DriftCityLauncher.ini main_ui_type (0 / 1) is written over goption.ini's
    // MainUIType every time the game starts (Launcher/common.go setOptions); "auto" leaves goption.ini's value
    // in the 2016 client MainUIType 0 shows the "Digital Type" HUD and 1 the classic one (user, 2026-11-20: tested in game)
    hud: ['0', '1'].includes(String(l['client.main_ui_type'] || '').trim()) ? parseInt(l['client.main_ui_type'], 10) : num('MainUIType', 1),
    msaa: num('MultiSampling', 0),
    preset: (() => { const x = num('VideoGradeSet', -1); return PRESETS[x] && !bool(g['Graphic.CustomVideoGrade'] || 'false') ? x : -1; })(),
    shadow: num('ShadowQuality', 3), car: num('CarDetail', 4), env: num('EnvironmentDetail', 4), fx: num('EffectDetail', 4),
    range: num('VisibleRange', 5),
    // motion blur in the openDC client: none / normal (speed effect on the edges); there is no "high" here
    //   none = MotionBlur=false; normal = MotionBlur=true + MotionBlurType=1
    blur: bool(g['Graphic.MotionBlur'] || 'false') ? 1 : 0, fog: bool(g['Graphic.FogEnable'] || 'true'),
    outline: num('VehicleOutline', 1) === 1,
    // the details a Graphic Quality preset sets (shown under "Advanced" in the Video tab)
    adv: Object.fromEntries(ADV_KEYS.map((k) => [k, g['Graphic.' + k] === undefined ? null
      : (/^(true|false)$/i.test(g['Graphic.' + k].trim()) ? bool(g['Graphic.' + k]) : parseInt(g['Graphic.' + k], 10))])),
  };
}

// The game's "Graphic Quality" presets (VideoGradeSet), as the 2016 client applies them (DriftCity.exe 0x4f4b50,
// the options window adds them at 0x57a26a: -1 Custom, 0 "speed", 1 "Normal", 2 "quality"). A preset sets these keys;
// MultiSampling is 2x / 4x when the graphics card has it (the launcher writes it; cards from the last 15 years do).
// Picking a preset leaves CustomVideoGrade=false; changing any detail makes it Custom (-1, CustomVideoGrade=true).
const B = (x) => (x ? 'true' : 'false');
const PRESETS = {
  0: { MultiSampling: 0, ShadowQuality: 3, VisibleRange: 2, VehicleShadow: 1, CarTextureQuality: 3, ObjectTextureQuality: 1,
    TerrainTextureQuality: 1, ObjectAnimation: B(0), BattleAnimation: B(1), ShowEffectMine: B(1), ShowEffectUsers: B(0), Hdr: 0,
    ShadowRange: 0, CarShader: 2, ShadowMapType: 0, EnvMapType: 1, Occ: 0, AniVisibleRange: 0, ShowObjectShadow: 0, DofType: 0, FovType: 0 },
  1: { MultiSampling: 2, ShadowQuality: 3, VisibleRange: 3, VehicleShadow: 1, CarTextureQuality: 4, ObjectTextureQuality: 2,
    TerrainTextureQuality: 2, ObjectAnimation: B(1), BattleAnimation: B(1), ShowEffectMine: B(1), ShowEffectUsers: B(1), Hdr: 0,
    ShadowRange: 0, CarShader: 2, ShadowMapType: 0, EnvMapType: 2, Occ: 0, AniVisibleRange: 1, ShowObjectShadow: 0, DofType: 0, FovType: 0 },
  2: { MultiSampling: 4, ShadowQuality: 3, VisibleRange: 4, VehicleShadow: 3, CarTextureQuality: 4, ObjectTextureQuality: 3,
    TerrainTextureQuality: 3, ObjectAnimation: B(1), BattleAnimation: B(1), ShowEffectMine: B(1), ShowEffectUsers: B(1), Hdr: 0,
    ShadowRange: 1, CarShader: 2, ShadowMapType: 1, EnvMapType: 2, Occ: 0, AniVisibleRange: 2, ShowObjectShadow: 1, DofType: 1, FovType: 0 },
};

function writeVideo(v) {
  const f = goption();
  if (!fs.existsSync(f)) throw new Error('goption.ini not found (is the client installed?)');
  C.iniSet(f, {
    'Graphic.ScreenWidth': String(v.width), 'Graphic.ScreenHeight': String(v.height),
    'Graphic.Fullscreen': v.fullscreen ? 'true' : 'false',
    'Graphic.MainUIType': String(v.hud), 'Graphic.MultiSampling': String(v.msaa),
    'Graphic.VideoGradeSet': String(v.preset), 'Graphic.CustomVideoGrade': v.preset < 0 ? 'true' : 'false',
    'Graphic.VisibleRange': String(v.range),
    'Graphic.MotionBlur': v.blur > 0 ? 'true' : 'false', 'Graphic.MotionBlurType': '1', 'Graphic.FogEnable': v.fog ? 'true' : 'false',
    'Graphic.VehicleOutline': v.outline ? '1' : '0',
  });
  // details no longer shown in the window (ShadowQuality, CarDetail, EnvironmentDetail, EffectDetail): kept as they are
  const old = { shadow: 'ShadowQuality', car: 'CarDetail', env: 'EnvironmentDetail', fx: 'EffectDetail' };
  const keep = {};
  for (const [k, key] of Object.entries(old)) if (v[k] !== undefined && v[k] !== null && !Number.isNaN(v[k])) keep['Graphic.' + key] = String(v[k]);
  if (Object.keys(keep).length) C.iniSet(f, keep);
  // the advanced details (a preset below writes its own values over them)
  if (v.adv) {
    const sets = {};
    for (const k of ADV_KEYS) {
      if (v.adv[k] === undefined || v.adv[k] === null) continue;
      sets['Graphic.' + k] = typeof v.adv[k] === 'boolean' ? B(v.adv[k]) : String(v.adv[k]);
    }
    C.iniSet(f, sets);
  }
  // a preset: everything it sets, as the game does (over what the window sent for those keys)
  if (PRESETS[v.preset]) {
    const sets = {};
    for (const [k, x] of Object.entries(PRESETS[v.preset])) sets['Graphic.' + k] = String(x);
    C.iniSet(f, sets);
  }
  const li = path.join(C.P().client, 'DriftCityLauncher.ini');
  if (fs.existsSync(li)) C.iniSet(li, { 'client.display': v.fullscreen ? 'fullscreen' : 'windowed', 'client.main_ui_type': String(v.hud) });
}

function restoreVideo() {
  if (!fs.existsSync(defOption())) throw new Error('def_option.ini not found');
  const d = C.iniRead(defOption());
  const g = {};
  for (const [k, v] of Object.entries(d)) if (k.startsWith('Graphic.')) g[k] = v.replace(/f$/, '').replace(/;$/, '');
  C.iniSet(goption(), g);
}

// First start of the game from the launcher: fullscreen, at 1920 x 1080 when the screen has it, otherwise the largest
// resolution the screen has, 16:9 first.
const RES_16_9 = [[1920, 1080], [1600, 900], [1366, 768], [1360, 768], [1280, 720], [1024, 576]];
const RES_ANY = [[1920, 1200], [1680, 1050], [1600, 1200], [1440, 900], [1280, 1024], [1280, 960], [1280, 800], [1280, 768],
  [1152, 864], [1024, 768], [1024, 600], [800, 600]];
function bestResolution(sw, sh) {
  const fits = ([w, h]) => w <= sw && h <= sh;
  return RES_16_9.find(fits) || RES_ANY.filter(fits).sort((a, b) => b[0] * b[1] - a[0] * a[1])[0] || [800, 600];
}
function firstDisplay(screen) {
  if (!fs.existsSync(goption()) || !screen) return null;
  const [w, h] = bestResolution(screen.w, screen.h);
  writeVideo(Object.assign(readVideo(), { width: w, height: h, fullscreen: true }));
  return { width: w, height: h };
}

module.exports = { readVideo, writeVideo, restoreVideo, goption, PRESETS, ADV_KEYS, bestResolution, firstDisplay };
