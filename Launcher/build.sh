#!/usr/bin/env bash
# Builds DriftCityLauncher for Linux (x86-64) and Windows (32-bit, like the client) into ../Client.
# Needs Go 1.22+, or podman / docker (then the golang image is used; no compiler on the host).
set -euo pipefail
cd "$(dirname "$0")"
build() {
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags '-s -w' -o ../Client/DriftCityLauncher .
  CGO_ENABLED=0 GOOS=windows GOARCH=386 go build -trimpath -ldflags '-s -w' -o ../Client/DriftCityLauncher.exe .
}
if command -v go >/dev/null 2>&1; then
  build
else
  e=$(command -v podman || command -v docker) || { echo "need Go, podman or docker" >&2; exit 1; }
  root=$(cd .. && pwd)
  "$e" run --rm -v "$root:/src:Z" -w /src/Launcher -e GOCACHE=/tmp/gocache docker.io/library/golang:1.22-bookworm \
    bash -c 'CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o ../Client/DriftCityLauncher . &&
             CGO_ENABLED=0 GOOS=windows GOARCH=386 go build -trimpath -ldflags "-s -w" -o ../Client/DriftCityLauncher.exe .'
fi
ls -l ../Client/DriftCityLauncher ../Client/DriftCityLauncher.exe
