"""
分析 agent loop 运行统计

从 SQLite 数据库中提取性能指标
"""
import json
import sqlite3
import sys
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def analyze_run(db_path: str, run_id: str | None = None):
    """分析指定 run 的性能"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 如果没有指定 run_id，使用最新的
    if not run_id:
        cursor.execute("SELECT run_id FROM run ORDER BY created_at DESC LIMIT 1")
        result = cursor.fetchone()
        if not result:
            print("❌ No runs found in database")
            return
        run_id = result[0]

    print(f"📊 Analyzing run: {run_id}\n")

    # 获取 run 信息
    cursor.execute("SELECT created_at, metadata FROM run WHERE run_id = ?", (run_id,))
    run_info = cursor.fetchone()
    if not run_info:
        print(f"❌ Run {run_id} not found")
        return

    created_at, metadata_json = run_info
    metadata = json.loads(metadata_json) if metadata_json else {}

    print(f"⏰ Created: {created_at}")
    print(f"🎯 Goal: {metadata.get('goal', 'N/A')}")
    print(f"📁 Repo: {metadata.get('repo_root', 'N/A')}")
    print()

    # 获取所有事件
    cursor.execute(
        "SELECT kind, ts, payload FROM event WHERE run_id = ? ORDER BY ts",
        (run_id,)
    )
    events = cursor.fetchall()

    print(f"📝 Total Events: {len(events)}\n")

    # 统计事件类型
    event_counts = {}
    for kind, _, _ in events:
        event_counts[kind] = event_counts.get(kind, 0) + 1

    print("📋 Event Types:")
    for kind, count in sorted(event_counts.items(), key=lambda x: -x[1]):
        print(f"  - {kind}: {count}")
    print()

    # 分析迭代次数
    iterations = [e for e in events if e[0] == "loop_iteration"]
    print(f"🔄 Iterations: {len(iterations)}")

    # 分析 LLM 调用
    llm_responses = [e for e in events if e[0] == "llm_response"]
    print(f"🤖 LLM Calls: {len(llm_responses)}")

    # 分析工具调用
    cursor.execute(
        "SELECT tool_name, COUNT(*) FROM tool_call WHERE run_id = ? GROUP BY tool_name",
        (run_id,)
    )
    tool_stats = cursor.fetchall()

    if tool_stats:
        print(f"\n🔧 Tool Calls:")
        for tool_name, count in sorted(tool_stats, key=lambda x: -x[1]):
            print(f"  - {tool_name}: {count}")

    # 分析上下文压缩
    compression_events = [e for e in events if "compress" in e[0]]
    if compression_events:
        print(f"\n💾 Context Compression:")
        print(f"  - Compression Events: {len(compression_events)}")

        total_tokens_saved = 0
        compression_ratios = []

        for kind, ts, payload_json in compression_events:
            payload = json.loads(payload_json) if payload_json else {}
            if "tokens_saved" in payload:
                total_tokens_saved += payload["tokens_saved"]
            if "compression_ratio" in payload:
                compression_ratios.append(payload["compression_ratio"])

        if total_tokens_saved > 0:
            print(f"  - Total Tokens Saved: {total_tokens_saved:,}")
        if compression_ratios:
            avg_ratio = sum(compression_ratios) / len(compression_ratios)
            print(f"  - Avg Compression Ratio: {avg_ratio:.2f}")

    # 分析 Loop Guard 警告
    guard_warnings = [e for e in events if "guard" in e[0] or "circuit" in e[0]]
    if guard_warnings:
        print(f"\n🛡️ Loop Guard Warnings: {len(guard_warnings)}")
        for kind, ts, payload_json in guard_warnings:
            payload = json.loads(payload_json) if payload_json else {}
            print(f"  - {kind}: {payload.get('warning', payload.get('reason', 'N/A'))}")

    # 分析并行执行
    parallel_events = [e for e in events if "parallel" in e[0]]
    if parallel_events:
        print(f"\n⚡ Parallel Execution:")
        print(f"  - Parallel Batches: {len(parallel_events) // 2}")  # start + end

        for kind, ts, payload_json in parallel_events:
            if "start" in kind:
                payload = json.loads(payload_json) if payload_json else {}
                tool_count = payload.get("tool_count", 0)
                if tool_count > 1:
                    print(f"  - Batch with {tool_count} tools")

    # 分析最终结果
    complete_events = [e for e in events if e[0] in ("loop_complete", "loop_max_iterations", "loop_error")]
    if complete_events:
        kind, ts, payload_json = complete_events[0]
        payload = json.loads(payload_json) if payload_json else {}
        print(f"\n✅ Result: {kind}")
        if "reason" in payload:
            print(f"  - Reason: {payload['reason']}")
        if "error" in payload:
            print(f"  - Error: {payload['error']}")

    conn.close()


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else ".codinggirl/runs.db"
    run_id = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"Usage: python analyze_run.py <db_path> [run_id]")
        return

    analyze_run(db_path, run_id)


if __name__ == "__main__":
    main()
