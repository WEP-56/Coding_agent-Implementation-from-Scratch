"""
并行工具执行器

支持并行执行多个独立的工具调用，提升速度
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any

from codinggirl.core.contracts import ToolResult
from codinggirl.runtime.tools.runner import ToolRunner


@dataclass
class ParallelToolRunner:
    """
    并行工具执行器

    自动检测可并行的工具调用并并行执行
    """

    runner: ToolRunner
    max_workers: int = 4  # 最大并行数

    def can_parallelize(self, tool_name: str) -> bool:
        """
        判断工具是否可以并行执行

        只读工具可以并行，写入工具需要串行
        """
        spec = self.runner.registry.get_spec(tool_name)
        if not spec:
            return False

        # 只有 readonly 权限的工具可以并行
        return spec.required_permission == "readonly"

    def execute_batch(
        self,
        tool_calls: list[tuple[str, dict[str, Any], str]],  # (name, args, call_id)
    ) -> list[ToolResult]:
        """
        批量执行工具调用

        自动将可并行的工具并行执行，其他串行执行

        Args:
            tool_calls: [(tool_name, args, call_id), ...]

        Returns:
            按原顺序返回的结果列表
        """
        if not tool_calls:
            return []

        # 分组：可并行 vs 需串行
        parallel_batch: list[tuple[int, str, dict[str, Any], str]] = []  # (index, name, args, id)
        serial_batch: list[tuple[int, str, dict[str, Any], str]] = []

        for i, (name, args, call_id) in enumerate(tool_calls):
            if self.can_parallelize(name):
                parallel_batch.append((i, name, args, call_id))
            else:
                serial_batch.append((i, name, args, call_id))

        # 结果字典（index -> result）
        results: dict[int, ToolResult] = {}

        # 并行执行可并行的工具
        if parallel_batch:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.runner.call, name, args, call_id): idx
                    for idx, name, args, call_id in parallel_batch
                }

                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        # 如果并行执行失败，创建错误结果
                        results[idx] = ToolResult(
                            ok=False,
                            error=f"Parallel execution failed: {e}",
                        )

        # 串行执行需要串行的工具
        for idx, name, args, call_id in serial_batch:
            results[idx] = self.runner.call(name, args, call_id)

        # 按原顺序返回结果
        return [results[i] for i in range(len(tool_calls))]


def analyze_parallelizability(tool_calls: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """
    分析工具调用的并行性

    返回统计信息，用于优化决策
    """
    if not tool_calls:
        return {
            "total": 0,
            "parallelizable": 0,
            "serial": 0,
            "speedup_potential": 1.0,
        }

    # 简单分析：假设读操作可并行
    read_tools = {"fs_read_file", "fs_read_range", "fs_list_dir", "fs_list_files",
                  "fs_glob", "search_rg", "index_query_repo_map", "index_query_imports"}

    parallelizable = sum(1 for name, _ in tool_calls if name in read_tools)
    serial = len(tool_calls) - parallelizable

    # 估算加速比（简化模型）
    if parallelizable <= 1:
        speedup = 1.0
    else:
        # 假设并行效率 80%
        speedup = 1.0 + (parallelizable - 1) * 0.8

    return {
        "total": len(tool_calls),
        "parallelizable": parallelizable,
        "serial": serial,
        "speedup_potential": speedup,
    }
