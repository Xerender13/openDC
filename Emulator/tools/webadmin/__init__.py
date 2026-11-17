"""openDC web workshop: a local browser UI for the emulator's items, cars, rewards and server.

Start it from Emulator/ (or use ./webadmin.sh) and open the printed URL:

    .venv/bin/python -m tools.webadmin [--host 127.0.0.1] [--port 8088] [--config emulator.ini]
    ./webadmin.sh            # the same, through the local virtual environment

Each start makes a random token and prints it in the URL; the page keeps it in
sessionStorage. Every /api request needs that token (header X-Token), because the GM
control port behind this tool has no password. Without --allow-remote the tool binds to
loopback only. The server implementation uses the Python standard library only; the page
is plain HTML/CSS/JavaScript from static/. Icons use Pillow and the game client.

Tabs:
  Items            Every part, consumable and drift item, searchable and filterable by
                   table, kind and grade, with picture, name, grade, level and price.
                   The detail panel edits all columns (fixed identifiers stay locked) and
                   gives an item to an online character with the GM item / drift command.
  Cars             VehicleList models with their V-grade rows from VehicleUpgrade; the
                   same editing, and "Give car" sends the GM car command.
  Rewards & drops  RewardGroup groups (counts and summed probability), the drop tables,
                   the reward text files of every mode, mode_tuning.txt and, for 2016, the
                   Neo City chapter / quest rewards. Rows can be duplicated where the
                   format allows it, then edited.
  Settings         emulator.ini key / value rows (credentials and deployment sections stay
                   out of the browser) and the [events] season switches as on / off / auto,
                   written to the ini and applied live with the GM event command.
  Server           ./launch.sh status, who is online with kick / block / ban, a GM console
                   with history, accounts (search, detail, create, password, role), the last
                   200 lines of the emulator log, and a confirmed restart.

Table saves go through tools/editor/data.py Document: backups land in editor_backups/,
identifier columns are refused, and a file changed on disk since it was loaded is reported
instead of overwritten. The emulator caches tables, so restart it after a table save; the
page reminds you.
"""
