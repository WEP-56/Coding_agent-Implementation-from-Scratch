import { isTauriRuntime } from "./platform";

export async function openPathNative(filePath: string): Promise<boolean> {
  if (!isTauriRuntime()) return false;

  try {
    const { open } = await import("@tauri-apps/plugin-shell");
    await open(filePath);
    return true;
  } catch {
    // Fallback: at least open the OS file picker.
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      multiple: false,
      directory: false,
      defaultPath: filePath,
    });
    return selected !== null;
  }
}
