"""
Spike (#1671): start the local server inside the desktop app.

Run by the Tauri shell as `python -I -B desktop_entry.py --data-dir ... --log-dir ...
--ui-dir ... --hf-home ...`, with stdin and stdout piped. It wraps local-server's app.py
without changing it, to prove the start-up the build issues will move into the server:

- TLS roots from certifi (#1509), the embedding model from the bundle with the hub offline
- config.json and the databases in the app-data folder, logs in the log folder
- Alembic upgrade head on local.db and operations.db (each backed up first)
- its own loopback sockets: 127.0.0.1 and ::1 on one port (#1692), 8765 preferred
- the built UI served at / on the same origin as /api and /mcp
- one ready line on stdout, runtime.json for MCP clients, exit when stdin closes

Timings go to stderr as `CS_TIMING <phase> <seconds since start>`.
"""

import argparse
import json
import logging
import logging.handlers
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

T0 = time.monotonic()
SERVER_DIR = Path(__file__).resolve().parent


def timing(phase: str) -> None:
    print(f"CS_TIMING {phase} {time.monotonic() - T0:.3f}", file=sys.stderr, flush=True)


def bind_loopback(preferred: int) -> tuple[list[socket.socket], int]:
    """Bind 127.0.0.1 on the preferred port (else a free one) and ::1 on the same port."""

    def bound(family: int, host: str, port: int) -> socket.socket:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        sock.bind((host, port))
        return sock

    try:
        ipv4 = bound(socket.AF_INET, "127.0.0.1", preferred)
    except OSError:
        ipv4 = bound(socket.AF_INET, "127.0.0.1", 0)
    port = ipv4.getsockname()[1]
    sockets = [ipv4]
    try:
        sockets.append(bound(socket.AF_INET6, "::1", port))
    except OSError as exc:
        print(f"::1 not bound, serving 127.0.0.1 only: {exc}", file=sys.stderr, flush=True)
    return sockets, port


def write_config(config_path: Path, port: int) -> None:
    """First run writes defaults; every run points the UI origin at the bound port."""
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    server = config.setdefault("server", {})
    server.update({"host": "127.0.0.1", "port": port, "ui_base_url": f"http://127.0.0.1:{port}"})
    # Spike only: the server refuses to start with no LLM key, so a first run could
    # never reach Settings. A build issue makes keys optional at start-up.
    llm = config.setdefault("llm", {})
    if not any(llm.get(k) for k in ("openai_api_key", "anthropic_api_key", "openrouter_api_key")):
        llm["openrouter_api_key"] = "spike-placeholder-not-a-key"
    config_path.write_text(json.dumps(config, indent=2))
    os.chmod(config_path, 0o600)


def use_log_dir(log_dir: Path) -> None:
    """Point local-server's shared log handler at the log folder, not the source tree."""
    import utils.logger as server_logger

    handler = logging.handlers.RotatingFileHandler(
        log_dir / "context_studio.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    server_logger._file_handler = handler
    server_logger._handler_init_attempted = True


def migrate(data_dir: Path) -> None:
    """Alembic upgrade head on both databases, backing each existing one up first."""
    from alembic import command
    from alembic.config import Config

    sqlite_dir = SERVER_DIR / "adapters" / "persistence" / "sqlite"
    targets = [
        ("local.db", sqlite_dir / "versions", ["local_db_url=sqlite:///{db}"]),
        (
            "operations.db",
            sqlite_dir / "operations" / "versions",
            ["db=operations", "operations_db_url=sqlite:///{db}"],
        ),
    ]
    for name, versions, x_args in targets:
        db = data_dir / name
        if db.exists():
            shutil.copy2(db, data_dir / f"{name}.bak")
        config = Config(str(sqlite_dir / "alembic.ini"))
        config.set_main_option("version_locations", str(versions))
        config.cmd_opts = argparse.Namespace(x=[x.format(db=db) for x in x_args])
        command.upgrade(config, "head")


def ui_files(ui_dir: Path):
    """Static files for the built UI, answering unknown paths with index.html."""
    from starlette.exceptions import HTTPException
    from starlette.staticfiles import StaticFiles

    class SinglePageFiles(StaticFiles):
        async def get_response(self, path, scope):
            try:
                response = await super().get_response(path, scope)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
                return await super().get_response("index.html", scope)
            if response.status_code == 404:
                return await super().get_response("index.html", scope)
            return response

    return SinglePageFiles(directory=str(ui_dir), html=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--ui-dir", required=True, type=Path)
    parser.add_argument("--hf-home", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ["HF_HOME"] = str(args.hf_home)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    args.data_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(args.data_dir, 0o700)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(args.data_dir)  # relative defaults (the reference cache, source files) land here
    sys.path.insert(0, str(SERVER_DIR))  # -I leaves the script's folder off sys.path

    sockets, port = bind_loopback(args.port)
    config_path = args.data_dir / "config.json"
    write_config(config_path, port)
    os.environ["CONFIG_PATH"] = str(config_path)
    use_log_dir(args.log_dir)
    timing("configured")

    migrate(args.data_dir)
    timing("migrated")

    import uvicorn

    from app import app as server_app

    timing("imported")
    server_app.mount("/", ui_files(args.ui_dir), name="ui")

    server = uvicorn.Server(uvicorn.Config(server_app, log_level="info", lifespan="on"))
    runtime_path = args.data_dir / "runtime.json"

    def announce() -> None:
        while not server.started and not server.should_exit:
            time.sleep(0.02)
        if server.should_exit:
            return
        timing("listening")
        runtime = {
            "url": f"http://127.0.0.1:{port}",
            "mcp_url": f"http://127.0.0.1:{port}/mcp",
            "pid": os.getpid(),
        }
        runtime_path.write_text(json.dumps(runtime, indent=2))
        print("CS_READY " + json.dumps({"port": port}), flush=True)

    def exit_when_stdin_closes() -> None:
        for _ in sys.stdin:
            pass
        server.should_exit = True

    threading.Thread(target=announce, name="announce", daemon=True).start()
    threading.Thread(target=exit_when_stdin_closes, name="stdin-watch", daemon=True).start()
    try:
        server.run(sockets=sockets)
    finally:
        runtime_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
