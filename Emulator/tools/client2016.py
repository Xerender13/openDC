"""Patch/launch the Dev Ed client against the isolated 2016 test server.

python -m tools.client2016 patch
python -m tools.client2016 launch

Writes DriftCity2016Test.exe alongside the original (which is never edited).
The auth socket port changes from 11005 to 11105; all subsequent service ports
come from the test server list. Guided tutorial mode also changes one comparison
byte to enter the native apprentice race without waiting for the Tutorial button. The 2011 launcher must not patch this build.
Linux launch uses Proton and a separate prefix, copied from the working 2011
prefix on first use. The test server must already be running.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
IMAGE_SHA256 = '52acaca96cb9f1e88d1f52bf5f8fa6db80daaa9ecbaae4c7c86eae92cd19657a'
TEST_PORT = 11105
# 0x54f6bf: mov word [0x9bc374], 11005. The data word is initialized too.
# The pushes of 11005 at 0x4b8372 / 0x4b8832 / 0x4b886c are UI IDs, NOT ports.
PORT_STORE = 0x14eabf
PORT_DATA = 0x5bb174


def patch_image(data, guided=False):
    if hashlib.sha256(data).hexdigest() != IMAGE_SHA256:
        raise ValueError('Unsupported Dev Ed executable; original SHA-256 does not match')
    out = bytearray(data)
    expected = bytes.fromhex('66c70574c39b00fd2a')
    if out[PORT_STORE:PORT_STORE+9] != expected or out[PORT_DATA:PORT_DATA+2] != b'\xfd\x2a':
        raise ValueError('Unexpected login port instruction/data; refusing to patch')
    struct.pack_into('<H', out, PORT_STORE+7, TEST_PORT)
    struct.pack_into('<H', out, PORT_DATA, TEST_PORT)
    if guided:
        from .tutorial_flow import patch_start_branch
        return patch_start_branch(out, 2016, 1)
    return bytes(out)


def prepare(client):
    original = client / 'DriftCity.exe'
    data = original.read_bytes()
    from .tutorial_flow import guided_mode
    patched = patch_image(data, guided=guided_mode(client) == 1)
    backup = ROOT / 'Emulator/client_backup/2016/DriftCity.exe.orig'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(original, backup)
    destination = client / 'DriftCity2016Test.exe'
    if destination.exists() and destination.read_bytes() not in (data, patched, patch_image(data), patch_image(data, guided=True)):
        raise ValueError(f'{destination} has other modifications; refusing to overwrite it')
    temporary = destination.with_suffix('.exe.tmp')
    temporary.write_bytes(patched)
    temporary.chmod(0o755)
    temporary.replace(destination)
    print(f'Prepared {destination.name}: auth 127.0.0.1:{TEST_PORT}; original unchanged')
    return destination


def launch(client, proton, prefix):
    with socket.create_connection(('127.0.0.1', TEST_PORT), timeout=2):
        pass
    executable = prepare(client)
    if not prefix.exists():
        source = Path.home() / '.local/share/drift2011-pfx'
        if not source.is_dir():
            raise ValueError('Working drift2011-pfx missing; supply an initialized Proton --prefix')
        shutil.copytree(source, prefix, symlinks=True)
    env = os.environ.copy()
    for key in ('SteamAppId', 'SteamGameId', 'SteamOverlayGameId', 'STEAM_COMPAT_APP_ID'):
        env.pop(key, None)
    env.update(STEAM_COMPAT_CLIENT_INSTALL_PATH=str(Path.home()/'.local/share/Steam'),
               STEAM_COMPAT_DATA_PATH=str(prefix), WINEDEBUG='err+seh,+msgbox')
    logs = ROOT / 'Emulator/logs/2016'
    logs.mkdir(parents=True, exist_ok=True)
    with (logs/'client-console.txt').open('ab') as log:
        subprocess.run([str(proton), 'run', 'reg', 'add', r'HKLM\SOFTWARE\DriftCity',
                        '/v', 'EnableWindowMode', '/t', 'REG_DWORD', '/d', '1', '/f', '/reg:32'],
                       cwd=client, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=45)
        tick = int(time.monotonic()*1000)
        token = hashlib.md5(str(tick-tick % 300000).encode()).hexdigest()
        process = subprocess.Popen([str(proton), 'run', './'+executable.name, '/runsw', token],
                                   cwd=client, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    print(f'2016 client launched (Proton PID {process.pid}); console: {logs / "client-console.txt"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('patch', 'launch'))
    parser.add_argument('--client', type=Path, default=ROOT / 'DriftCity Dev Ed')
    parser.add_argument('--proton', type=Path,
                        default=Path.home()/'.local/share/Steam/steamapps/common/Proton 11.0/proton')
    parser.add_argument('--prefix', type=Path, default=Path.home()/'.local/share/drift2016-pfx')
    args = parser.parse_args()
    if args.action == 'patch':
        prepare(args.client.resolve())
    else:
        launch(args.client.resolve(), args.proton, args.prefix)


if __name__ == '__main__':
    main()
