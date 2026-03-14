export function isTauriRuntime(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as {
    __TAURI_INTERNALS__?: { invoke?: unknown };
    __TAURI__?: { core?: { invoke?: unknown } };
  };

  // Tauri v2 always injects `__TAURI_INTERNALS__` for IPC. `__TAURI__` is optional.
  return (
    typeof w.__TAURI_INTERNALS__?.invoke === "function" ||
    typeof w.__TAURI__?.core?.invoke === "function"
  );
}
