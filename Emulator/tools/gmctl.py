"""GM commands for the running emulator, through its control port (emulator.ini [emulator]
control_port, local only): kick, block and ban as dcemu/native/admin.py describes them.

usage (from Emulator/): python3 -m tools.gmctl [-c emulator.ini] COMMAND ...
    who                          who is in the game
    kick NAME [days]             disconnect a character; with days, also block it from the game
    block NAME days              block a character from the game (and kick it)
    unblock NAME
    chatblock NAME minutes       0 lifts it
    ban ACCOUNT-or-NAME          block the account (login: "blocked") and kick it
    unban ACCOUNT-or-NAME
    realmatch open|close|in MINUTES|auto|status   Real Match opening, over emulator.ini (in: opening notices, then open)
"""
import socket
import sys

from dcemu.__main__ import HERE, load_config
import os


def main():
    args = sys.argv[1:]
    config = os.path.join(HERE, 'emulator.ini')
    if args[:1] == ['-c']:
        config, args = args[1], args[2:]
    if not args:
        sys.exit(__doc__)
    port = int(load_config(config)['emulator']['control_port'])
    with socket.create_connection(('127.0.0.1', port), timeout=10) as s:
        s.sendall((' '.join(args) + '\n').encode('utf-8'))
        out = b''
        while data := s.recv(4096):
            out += data
    print(out.decode('utf-8', 'replace').rstrip())
    sys.exit(0 if out.startswith(b'OK') else 1)


if __name__ == '__main__':
    main()
