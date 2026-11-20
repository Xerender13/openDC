#!/bin/bash
# Builds the openDC desktop launcher from app/:
#   out/openDC-Launcher-<version>-x86_64.AppImage   (Linux, any distro)
#   out/openDC-Launcher-<version>-Windows.zip       (Windows 10 / 11: "openDC Launcher.exe")
# Needs: bash, curl, unzip, zip, tar, python3 with pefile + pillow (pip install pefile pillow), node (only for the version).
# The prebuilt pieces are downloaded once into .cache/ (Electron, 7-Zip for Linux, appimagetool).
set -e
cd "$(dirname "$0")"
V=$(node -p "require('./app/package.json').version" 2>/dev/null || sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' app/package.json)
ELECTRON=45.4.1
SEVENZIP=2606
CACHE=.cache
mkdir -p "$CACHE"
get() { [ -s "$CACHE/$1" ] || { echo "downloading $1"; curl -fL --retry 3 -o "$CACHE/$1.part" "$2" && mv "$CACHE/$1.part" "$CACHE/$1"; }; }
get electron-linux-x64.zip "https://github.com/electron/electron/releases/download/v$ELECTRON/electron-v$ELECTRON-linux-x64.zip"
get electron-win32-x64.zip "https://github.com/electron/electron/releases/download/v$ELECTRON/electron-v$ELECTRON-win32-x64.zip"
get 7z-linux.tar.xz "https://github.com/ip7z/7zip/releases/download/${SEVENZIP:0:2}.${SEVENZIP:2}/7z$SEVENZIP-linux-x64.tar.xz"
get appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x "$CACHE/appimagetool"
[ -x "$CACHE/7zz" ] || tar -xJf "$CACHE/7z-linux.tar.xz" -C "$CACHE" 7zz

rm -rf build && mkdir -p build out
stage() { # $1 = the resources folder: the app, plus the Python helper next to it (run by the portable Python)
  rm -f "$1/default_app.asar"
  mkdir -p "$1/helper"
  cp -r app "$1/app"; rm -rf "$1/app/helper"
  cp app/helper/odc_helper.py "$1/helper/"
}

# --- Linux: AppImage (7zz bundled to extract the client's .zip / .7z / .rar) ---
mkdir build/AppDir && (cd build/AppDir && unzip -q "../../$CACHE/electron-linux-x64.zip")
mv build/AppDir/electron build/AppDir/opendc-launcher; rm -f build/AppDir/chrome-sandbox
stage build/AppDir/resources
mkdir -p build/AppDir/resources/bin && cp "$CACHE/7zz" build/AppDir/resources/bin/
cat > build/AppDir/AppRun <<'R'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/opendc-launcher" --no-sandbox "$@"
R
chmod +x build/AppDir/AppRun
cp app/ui/assets/icon.png build/AppDir/opendc-launcher.png
printf '[Desktop Entry]\nType=Application\nName=openDC Launcher\nComment=Drift City (openDC)\nExec=AppRun\nIcon=opendc-launcher\nCategories=Game;\nTerminal=false\n' > build/AppDir/opendc-launcher.desktop
rm -f "out/openDC-Launcher-$V-x86_64.AppImage"
ARCH=x86_64 "$CACHE/appimagetool" --appimage-extract-and-run build/AppDir "out/openDC-Launcher-$V-x86_64.AppImage" >/dev/null 2>&1

# --- Windows: a folder with "openDC Launcher.exe" (Windows' own tar.exe extracts the client) ---
W="build/openDC Launcher"
mkdir -p "$W" && (cd "$W" && unzip -q "../../$CACHE/electron-win32-x64.zip")
mv "$W/electron.exe" "$W/openDC Launcher.exe"
python3 seticon.py app/ui/assets/icon.png "$W/openDC Launcher.exe"   # the same icon as the AppImage
stage "$W/resources"
cp README-windows.txt "$W/README.txt"
find "$W" -exec touch {} +   # today's date instead of Electron's 1980
rm -f "out/openDC-Launcher-$V-Windows.zip"
(cd build && zip -qr9 "../out/openDC-Launcher-$V-Windows.zip" "openDC Launcher")
ls -la out
