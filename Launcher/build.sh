#!/usr/bin/env bash
# Builds DriftCityLauncher for Linux (x86-64) and Windows (32-bit, like the client) into each client folder there is:
# ../Client US, ../Client EU (or ../Client), ../DriftCity Dev Ed (the 2016 client).
# Needs Go 1.22+, or podman / docker (then the golang image is used; no compiler on the host).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
build() {
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags '-s -w' -o build/DriftCityLauncher .
  CGO_ENABLED=0 GOOS=windows GOARCH=386 go build -trimpath -ldflags '-s -w' -o build/DriftCityLauncher.exe .
}
if command -v go >/dev/null 2>&1; then
  build
else
  e=$(command -v podman || command -v docker) || { echo "need Go, podman or docker" >&2; exit 1; }
  "$e" run --rm -v "$(pwd):/src:Z" -w /src -e GOCACHE=/tmp/gocache docker.io/library/golang:1.22-bookworm \
    bash -c 'CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o build/DriftCityLauncher . &&
             CGO_ENABLED=0 GOOS=windows GOARCH=386 go build -trimpath -ldflags "-s -w" -o build/DriftCityLauncher.exe .'
fi
for c in "../Client US" "../Client EU" "../Client" "../DriftCity Dev Ed"; do
  [ -d "$c" ] || continue
  linux=DriftCityLauncher
  [ "$c" = "../DriftCity Dev Ed" ] && linux=DriftCityLauncher2016      # the user's name for it there
  # a new file swapped in: a running launcher keeps the old one open
  cp build/DriftCityLauncher "$c/$linux.new" && mv -f "$c/$linux.new" "$c/$linux"
  cp build/DriftCityLauncher.exe "$c/DriftCityLauncher.exe.new" && mv -f "$c/DriftCityLauncher.exe.new" "$c/DriftCityLauncher.exe"
  ls -l "$c/$linux" "$c/DriftCityLauncher.exe"
done
