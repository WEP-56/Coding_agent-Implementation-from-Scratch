from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from codinggirl.core.contracts import utc_now_iso
from codinggirl.core.orchestrator import execute_goal
from codinggirl.adapters.telegram.handler import handle_message
from codinggirl.adapters.telegram.session_store import TelegramSessionStore
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.indexer.manifest import load_manifest, save_manifest, scan_manifest
from codinggirl.runtime.indexer.repo_map import build_repo_map_items, render_repo_map
from codinggirl.runtime.indexer.symbols import index_changed_source_files, open_symbols_db
from codinggirl.runtime.llm_adapter import ChatMessage, LLMConfig, ToolSchema, create_llm_provider
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.runner import ToolRunner
from codinggirl.runtime.workspace import RepoWorkspace
from codinggirl.core.policy import PermissionPolicy


def _default_db_path() -> Path:
    return Path(".codinggirl") / "codinggirl.sqlite3"


def cmd_init(args: argparse.Namespace) -> int:
    store = SQLiteStore(Path(args.db))
    store.init_schema()
    print(f"Initialized DB: {store.db_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    store = SQLiteStore(Path(args.db))
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={"goal": args.goal, "repo": args.repo})
    store.append_event(run_id=run_id, kind="run_created", ts=utc_now_iso(), payload={"goal": args.goal, "repo": args.repo})
    print(f"run_id={run_id}")

    ws = RepoWorkspace.from_path(args.repo)
    registry = create_default_registry(ws)
    runner = ToolRunner(registry=registry, store=store, run_id=run_id, permission=PermissionPolicy(mode="readonly"))

    if args.ls:
        res = runner.call("fs_list_dir", {"path": "."})
        print(res.content)

    print("MVP scaffold: run created and recorded to sqlite")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    ws = RepoWorkspace.from_path(repo)
    focus_terms = {x.strip().lower() for x in str(args.focus_terms).split(",") if x.strip()}
    index_dir = ws.resolve_path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = index_dir / "manifest.json"
    symbols_path = index_dir / "symbols.sqlite"
    repo_map_path = index_dir / "repo_map.txt"

    prev = load_manifest(manifest_path)
    entries, added, changed, removed = scan_manifest(ws, previous=prev)
    save_manifest(manifest_path, entries)

    changed_all = sorted(set(added + changed))
    conn = open_symbols_db(symbols_path)
    try:
        index_changed_source_files(
            ws,
            conn=conn,
            changed_files=changed_all,
            removed_files=removed,
        )
        items = build_repo_map_items(conn, focus_terms=focus_terms)
    finally:
        conn.close()

    repo_map_path.write_text(render_repo_map(items, max_lines=int(args.max_lines)), encoding="utf-8")

    print(f"manifest: {manifest_path}")
    print(f"symbols: {symbols_path}")
    print(f"repo_map: {repo_map_path}")
    print(f"added={len(added)} changed={len(changed)} removed={len(removed)}")
    if focus_terms:
        print(f"focus_terms={sorted(focus_terms)}")
    return 0


def cmd_orchestrate(args: argparse.Namespace) -> int:
    res = execute_goal(repo_root=str(args.repo), goal=str(args.goal), db_path=str(args.db))
    print(f"run_id={res.run_id}")
    print(f"status={res.status}")
    print(f"message={res.message}")
    return 0 if res.status == "DONE" else 2


def cmd_llm_probe(args: argparse.Namespace) -> int:
    cfg = LLMConfig(
        provider=str(args.provider),
        model=str(args.model),
        base_url=str(args.base_url) if args.base_url else None,
        api_key=str(args.api_key) if args.api_key else None,
        timeout_sec=int(args.timeout_sec),
    )
    llm = create_llm_provider(cfg)
    tools: list[ToolSchema] = []
    if args.with_tool:
        tools.append(
            ToolSchema(
                name="echo_tool",
                description="Echo a string back.",
                input_schema={
                    "type": "object",
                    "properties": {"echo": {"type": "string"}},
                    "required": ["echo"],
                    "additionalProperties": False,
                },
            )
        )

    messages = [
        ChatMessage(role="system", content="You are a concise assistant."),
        ChatMessage(role="user", content=str(args.prompt)),
    ]
    resp = llm.chat(messages=messages, tools=tools, temperature=float(args.temperature))
    print(f"provider={cfg.provider}")
    print(f"model={resp.model}")
    print(f"finish_reason={resp.finish_reason}")
    print(f"content={resp.content}")
    if resp.tool_calls:
        print("tool_calls:")
        for tc in resp.tool_calls:
            print(f"- id={tc.id} name={tc.name} args={tc.arguments_json}")
    return 0


def cmd_telegram_simulate(args: argparse.Namespace) -> int:
    store = TelegramSessionStore(Path(args.session_store))
    raw = str(args.text)
    normalized = raw if not raw.startswith("/") else raw[1:]
    reply = handle_message(store=store, chat_id=str(args.chat_id), text=normalized)
    print(reply.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="codinggirl")

    db_parent = argparse.ArgumentParser(add_help=False)
    db_parent.add_argument("--db", default=str(_default_db_path()), help="SQLite DB path")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp_init = sub.add_parser("init", help="initialize local sqlite db", parents=[db_parent])
    sp_init.set_defaults(fn=cmd_init)

    sp_run = sub.add_parser("run", help="start a run (scaffold)", parents=[db_parent])
    sp_run.add_argument("--repo", required=True, help="repo root path")
    sp_run.add_argument("--goal", required=True, help="task goal")
    sp_run.add_argument("--ls", action="store_true", help="list repo root entries (debug)")
    sp_run.set_defaults(fn=cmd_run)

    sp_index = sub.add_parser("index", help="build manifest/symbols/repo_map", parents=[db_parent])
    sp_index.add_argument("--repo", required=True, help="repo root path")
    sp_index.add_argument("--index-dir", default=".codinggirl/index", help="index output dir inside repo")
    sp_index.add_argument("--max-lines", type=int, default=300, help="max repo_map lines")
    sp_index.add_argument(
        "--focus-terms",
        default="",
        help="comma-separated terms to boost in ranking, e.g. auth,login,planner",
    )
    sp_index.set_defaults(fn=cmd_index)

    sp_orch = sub.add_parser("orchestrate", help="run Phase-3 orchestrator", parents=[db_parent])
    sp_orch.add_argument("--repo", required=True, help="repo root path")
    sp_orch.add_argument(
        "--goal",
        required=True,
        help="goal in format: replace [old] with [new] in [path]",
    )
    sp_orch.set_defaults(fn=cmd_orchestrate)

    sp_llm = sub.add_parser("llm-probe", help="exercise llm adapter", parents=[db_parent])
    sp_llm.add_argument("--provider", default="mock", help="mock | openai-compatible")
    sp_llm.add_argument("--model", default="mock-model", help="model name")
    sp_llm.add_argument("--base-url", default="", help="base URL for openai-compatible endpoint")
    sp_llm.add_argument("--api-key", default="", help="API key (optional for mock)")
    sp_llm.add_argument("--timeout-sec", type=int, default=60, help="request timeout in seconds")
    sp_llm.add_argument("--temperature", type=float, default=0.0, help="sampling temperature")
    sp_llm.add_argument("--prompt", required=True, help="prompt text")
    sp_llm.add_argument("--with-tool", action="store_true", help="attach one demo tool schema")
    sp_llm.set_defaults(fn=cmd_llm_probe)

    sp_tg = sub.add_parser("telegram-simulate", help="simulate telegram adapter locally", parents=[db_parent])
    sp_tg.add_argument("--session-store", default=".codinggirl/telegram_sessions.json", help="session store json")
    sp_tg.add_argument("--chat-id", required=True, help="telegram chat id")
    sp_tg.add_argument("--text", required=True, help="incoming text message")
    sp_tg.set_defaults(fn=cmd_telegram_simulate)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.fn(args))
