# The emulator in a container (docker-compose.yml service "emulator"), for Windows / macOS or anyone who would
# rather not install Python. The Emulator folder is mounted at /emu, so emulator.ini, server_data/ and logs/ are
# the files on the host: edit them there and restart the container.
FROM python:3.12-slim
RUN pip install --no-cache-dir python-tds
WORKDIR /emu
ENV PYTHONUNBUFFERED=1
# the first start copies the client's tables (not in git) from the client mounted at /client
CMD ["sh", "-c", "python -m tools.client_setup && exec python -m dcemu -q"]
