import type { ApprovalMeta, ArtifactItem, DiffFile, LogItem, RepoItem, SessionItem, TimelineStep, ToolCallItem } from "../types/models";

const repos: RepoItem[] = [
  { id: "r1", name: "codinggirl", path: "E:/coding agent", pinned: true },
  { id: "r2", name: "demo-repo", path: "D:/demo-repo", pinned: false },
];

const sessions: SessionItem[] = [
  {
    id: "s1",
    repoId: "r1",
    title: "修复登录验证错误",
    mode: "build",
    createdAt: "2026-03-07T10:00:00+08:00",
    updatedAt: "2026-03-07T13:40:00+08:00",
  },
  {
    id: "s2",
    repoId: "r1",
    title: "重构索引模块",
    mode: "plan",
    createdAt: "2026-03-07T09:00:00+08:00",
    updatedAt: "2026-03-07T13:20:00+08:00",
  },
  {
    id: "s3",
    repoId: "r2",
    title: "自动应用依赖升级",
    mode: "auto",
    createdAt: "2026-03-06T18:00:00+08:00",
    updatedAt: "2026-03-06T20:10:00+08:00",
  },
];

const timeline: TimelineStep[] = [
  { id: "t1", title: "分析仓库上下文", status: "success", detail: "索引 24 个文件" },
  { id: "t2", title: "生成补丁", status: "running", detail: "正在生成 unified diff" },
  { id: "t3", title: "运行测试", status: "pending" },
];

const diffFiles: DiffFile[] = [
  {
    id: "d1",
    path: "codinggirl/core/orchestrator.py",
    additions: 14,
    deletions: 5,
    oldSnippet: "- state.transition(\"PATCHED\")\n- apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch})",
    newSnippet:
      "+ state.transition(\"PATCHED\")\n+ rv = review_patch(patch)\n+ if not rv.ok:\n+   state.transition(\"PATCH_FAILED\")\n+ apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch, \"backup\": True})",
    unifiedSnippet:
      "@@ -42,2 +42,6 @@\n- state.transition(\"PATCHED\")\n- apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch})\n+ state.transition(\"PATCHED\")\n+ rv = review_patch(patch)\n+ if not rv.ok:\n+   state.transition(\"PATCH_FAILED\")\n+ apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch, \"backup\": True})",
    diff:
      "@@ -42,2 +42,6 @@\n- state.transition(\"PATCHED\")\n- apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch})\n+ state.transition(\"PATCHED\")\n+ rv = review_patch(patch)\n+ if not rv.ok:\n+   state.transition(\"PATCH_FAILED\")\n+ apply_res = runner.call(\"patch_apply_unified_diff\", {\"patch\": patch, \"backup\": True})",
  },
  {
    id: "d2",
    path: "apps/desktop/src/pages/workspace-page.tsx",
    additions: 20,
    deletions: 2,
    oldSnippet: "- <div className=\"rounded-md border...\">Diff 占位</div>",
    newSnippet: "+ <DiffPanel files={diffFiles} mode={diffViewMode} />",
    unifiedSnippet:
      "@@ -201,1 +201,1 @@\n- <div className=\"rounded-md border...\">Diff 占位</div>\n+ <DiffPanel files={diffFiles} mode={diffViewMode} />",
    diff:
      "@@ -201,1 +201,1 @@\n- <div className=\"rounded-md border...\">Diff 占位</div>\n+ <DiffPanel files={diffFiles} mode={diffViewMode} />",
  },
];

const toolCalls: ToolCallItem[] = [
  {
    id: "tc1",
    name: "search_rg",
    status: "success",
    durationMs: 82,
    argsJson: '{"pattern":"login","max_results":20}',
    resultJson: '{"results": 4}',
  },
  {
    id: "tc2",
    name: "patch_apply_unified_diff",
    status: "running",
    durationMs: 1240,
    argsJson: '{"backup":true}',
    resultJson: '{"files":1}',
  },
  {
    id: "tc3",
    name: "run_tests",
    status: "failed",
    durationMs: 4021,
    argsJson: '{"command":"pytest"}',
    resultJson: '{"exit_code":1,"failed":2}',
  },
];

const logs: LogItem[] = [
  {
    id: "l1",
    ts: "2026-03-07 14:10:11",
    level: "info",
    source: "orchestrator",
    message: "Run created and plan generated.",
  },
  {
    id: "l2",
    ts: "2026-03-07 14:10:13",
    level: "warn",
    source: "reviewer",
    message: "Patch touches sensitive-like path pattern; awaiting confirmation.",
  },
  {
    id: "l3",
    ts: "2026-03-07 14:10:20",
    level: "error",
    source: "verifier",
    message: "pytest failed: 2 tests failed in test_orchestrator.py.",
  },
];

const artifacts: ArtifactItem[] = [
  {
    id: "a1",
    name: "patchset-20260307.diff",
    kind: "patch",
    filePath: "E:/coding agent/.codinggirl/artifacts/patchset-20260307.diff",
    sizeKb: 12,
    createdAt: "2026-03-07 14:10:15",
  },
  {
    id: "a2",
    name: "run-report-20260307.json",
    kind: "report",
    filePath: "E:/coding agent/.codinggirl/artifacts/run-report-20260307.json",
    sizeKb: 7,
    createdAt: "2026-03-07 14:10:22",
  },
  {
    id: "a3",
    name: "repo_map.txt",
    kind: "index",
    filePath: "E:/coding agent/.codinggirl/index/repo_map.txt",
    sizeKb: 18,
    createdAt: "2026-03-07 14:09:58",
  },
];

export async function getApprovalMeta(sessionId: string): Promise<ApprovalMeta> {
  await wait(40);
  const fileCount = diffFiles.length;
  const additions = diffFiles.reduce((sum, f) => sum + f.additions, 0);
  const deletions = diffFiles.reduce((sum, f) => sum + f.deletions, 0);
  const risk: ApprovalMeta["risk"] = additions + deletions > 40 ? "high" : additions + deletions > 20 ? "medium" : "low";
  const session = sessions.find((s) => s.id === sessionId);
  const repo = repos.find((r) => r.id === session?.repoId);
  return {
    fileCount,
    additions,
    deletions,
    risk,
    repoName: repo?.name ?? "unknown-repo",
    branch: "main",
  };
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function listRepos(): Promise<RepoItem[]> {
  await wait(80);
  return [...repos];
}

export async function listSessions(repoId: string): Promise<SessionItem[]> {
  await wait(80);
  return sessions.filter((s) => s.repoId === repoId).map((s) => ({ ...s }));
}

export async function getTimeline(sessionId: string): Promise<TimelineStep[]> {
  void sessionId;
  await wait(60);
  return timeline.map((t) => ({ ...t }));
}

export async function getDiffFiles(sessionId: string): Promise<DiffFile[]> {
  void sessionId;
  await wait(70);
  return diffFiles.map((d) => ({ ...d }));
}

export async function getToolCalls(sessionId: string): Promise<ToolCallItem[]> {
  void sessionId;
  await wait(65);
  return toolCalls.map((t) => ({ ...t }));
}

export async function getLogs(sessionId: string): Promise<LogItem[]> {
  void sessionId;
  await wait(75);
  return logs.map((l) => ({ ...l }));
}

export async function getArtifacts(sessionId: string): Promise<ArtifactItem[]> {
  void sessionId;
  await wait(55);
  return artifacts.map((a) => ({ ...a }));
}
