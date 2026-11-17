"""python -m tools.webadmin: serve the local workshop for the emulator copy in Emulator/."""
import argparse
import ipaddress
from pathlib import Path
import secrets

from .api import Admin
from .server import WebServer

ROOT = Path(__file__).resolve().parents[2]


def loopback(host):
    if host.lower() in ('localhost', 'localhost.localdomain'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='python -m tools.webadmin',
        description='Local browser workshop for the openDC emulator (tables, items, rewards, '
                    'accounts and the GM console).')
    parser.add_argument('--host', default='127.0.0.1',
                        help='address to bind (default 127.0.0.1; other addresses need '
                             '--allow-remote)')
    parser.add_argument('--port', type=int, default=8088, help='port (default 8088, 0 = any)')
    parser.add_argument('--config', default='emulator.ini',
                        help='emulator.ini to read the version and settings from '
                             '(default emulator.ini in Emulator/)')
    parser.add_argument('--client', default=None,
                        help='game client folder for item pictures (default ../Client US)')
    parser.add_argument('--allow-remote', action='store_true',
                        help='allow a non-loopback bind (prints a warning)')
    args = parser.parse_args(argv)

    if not loopback(args.host) and not args.allow_remote:
        parser.exit(2, f'Refusing to bind to {args.host}: use --allow-remote if you really '
                       f'want other machines to reach this tool.\n')
    if not loopback(args.host):
        print('WARNING: this tool controls the emulator and its GM port; anyone who can reach '
              f'{args.host}:{args.port} and reads the printed token has that control.')

    config = Path(args.config)
    if not config.is_absolute():
        config = ROOT / config
    if not config.is_file():
        parser.exit(1, f'{config} not found: run this from Emulator/ or pass --config.\n')
    try:
        admin = Admin.from_config(config, client=Path(args.client) if args.client else None)
    except Exception as error:
        parser.exit(1, f'Could not read {config}: {error}\n')

    token = secrets.token_urlsafe(24)
    try:
        httpd = WebServer((args.host, args.port), admin, token)
    except OSError as error:
        parser.exit(1, f'Could not listen on {args.host}:{args.port}: {error}\n')
    port = httpd.server_address[1]
    host = args.host
    if ':' in host:
        host = f'[{host}]'
    print(f'openDC web workshop · version {admin.version} · tables '
          f'{admin._relative(admin.table_root)}', flush=True)
    if admin.warning:
        print('WARNING:', admin.warning, flush=True)
    if not admin.entries['Settings']:
        print('WARNING: --config is outside Emulator/; the Settings and event switches are '
              'read-only in this tool.', flush=True)
    print(f'Open: http://{host}:{port}/?token={token}', flush=True)
    print('The token changes every start. Ctrl+C stops the tool; the emulator keeps running.',
          flush=True)
    admin.warm_artwork()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
