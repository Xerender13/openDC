'use strict';
// The game's video settings (DriftCity Dev Ed/Data/Init/goption.ini) and the server address
// (DriftCityLauncher.ini [server], [client] display / main_ui_type).
const fs = require('fs');
const path = require('path');
const C = require('./core');

function goption() { return path.join(C.P().client, 'Data', 'Init', 'goption.ini'); }
function defOption() { return path.join(C.P().client, 'Data', 'Init', 'def_option.ini'); }
const bool = (v) => String(v).trim().toLowerCase() === 'true' || String(v).trim() === '1';

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
    hud: ['0', '1'].includes(String(l['client.main_ui_type'] || '').trim()) ? parseInt(l['client.main_ui_type'], 10) : num('MainUIType', 1),
    msaa: num('MultiSampling', 0),
    preset: num('VideoGradeSet', -1),
    shadow: num('ShadowQuality', 3), car: num('CarDetail', 4), env: num('EnvironmentDetail', 4), fx: num('EffectDetail', 4),
    range: num('VisibleRange', 5),
    // motion blur in the openDC client: none / normal (speed effect on the edges); there is no "high" here
    //   none = MotionBlur=false; normal = MotionBlur=true + MotionBlurType=1
    blur: bool(g['Graphic.MotionBlur'] || 'false') ? 1 : 0, fog: bool(g['Graphic.FogEnable'] || 'true'),
    outline: num('VehicleOutline', 1) === 1,
  };
}

function writeVideo(v) {
  const f = goption();
  if (!fs.existsSync(f)) throw new Error('goption.ini not found (is the client installed?)');
  C.iniSet(f, {
    'Graphic.ScreenWidth': String(v.width), 'Graphic.ScreenHeight': String(v.height),
    'Graphic.Fullscreen': v.fullscreen ? 'true' : 'false',
    'Graphic.MainUIType': String(v.hud), 'Graphic.MultiSampling': String(v.msaa),
    'Graphic.VideoGradeSet': String(v.preset), 'Graphic.CustomVideoGrade': v.preset < 0 ? 'true' : 'false',
    'Graphic.ShadowQuality': String(v.shadow), 'Graphic.CarDetail': String(v.car), 'Graphic.EnvironmentDetail': String(v.env),
    'Graphic.EffectDetail': String(v.fx), 'Graphic.VisibleRange': String(v.range),
    'Graphic.MotionBlur': v.blur > 0 ? 'true' : 'false', 'Graphic.MotionBlurType': '1', 'Graphic.FogEnable': v.fog ? 'true' : 'false',
    'Graphic.VehicleOutline': v.outline ? '1' : '0',
  });
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

module.exports = { readVideo, writeVideo, restoreVideo, goption };
