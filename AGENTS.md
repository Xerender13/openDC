# Rules for a delegated worker (OpenCode)

You are a worker on openDC, a Python server emulator for the 2011 / 2016 Drift City client. The lead assistant
gave you one bounded task and reviews everything you return. `CLAUDE.md` describes the project.

- Do the assigned task only. Do not delegate further and do not start other agents or models.
- Edit only the files the task names. If the task says "findings only", change nothing and answer in text.
- Never: commit, push, restart or stop the emulator or any process, write to the SQL Server database, change a
  client folder or pack (`Client US/`, `Client EU/`, `DriftCity Dev Ed/`), touch `Emulator 2011/`, or delete files.
- Scratch files go in the directory the task names, not in the repository.
- Evidence first. A message layout, client address or game rule must come from the disassembly, a client table, a
  log line or the 2008 server; say where each one comes from (file and line / address). Mark anything else as a
  guess. Do not invent values.
- US behaviour must not change for an EU fix (`dcemu/native/nation.py`), and 2011 behaviour must not change for a
  2016 feature (`session.is2016` / the version checks already used in the module you edit).
- Check your work: from `Emulator/`, `.venv/bin/python -m pytest tests -q`. Report the exact result, including
  failures. Do not claim anything was tried in game.
- Never put passwords, tickets or personal data in a file or in your answer.
- End with: files changed, what was checked and how, what is unverified.
