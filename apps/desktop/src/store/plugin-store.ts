import { create } from "zustand";
import { importPlugin, listPlugins, removePlugin as removePluginRemote, togglePluginEnabled } from "../api/bridge";
import type { PluginItem } from "../types/models";

interface PluginState {
  plugins: PluginItem[];
  hydrated: boolean;
  hydrate: () => Promise<void>;
  importLocal: (path: string) => void;
  toggleEnabled: (id: string) => void;
  removePlugin: (id: string) => void;
}

const KEY = "codinggirl.plugins";

function readPlugins(): PluginItem[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is PluginItem => !!x && typeof x === "object") as PluginItem[];
  } catch {
    return [];
  }
}

function savePlugins(items: PluginItem[]): void {
  window.localStorage.setItem(KEY, JSON.stringify(items));
}

export const usePluginStore = create<PluginState>((set) => ({
  plugins: readPlugins(),
  hydrated: false,
  hydrate: async () => {
    try {
      const remote = await listPlugins();
      const local = readPlugins();
      const next = remote.length === 0 ? local : remote;
      savePlugins(next);
      set({ plugins: next, hydrated: true });
    } catch {
      set({ hydrated: true });
    }
  },
  importLocal: (path) => {
    importPlugin(path)
      .then(() => listPlugins())
      .then((items) => {
        savePlugins(items);
        set({ plugins: items });
      })
      .catch(() => {
        // keep previous state when remote fails
      });
  },
  toggleEnabled: (id) => {
    togglePluginEnabled(id)
      .then(() => listPlugins())
      .then((items) => {
        savePlugins(items);
        set({ plugins: items });
      })
      .catch(() => undefined);
  },
  removePlugin: (id) => {
    removePluginRemote(id)
      .then(() => listPlugins())
      .then((items) => {
        savePlugins(items);
        set({ plugins: items });
      })
      .catch(() => undefined);
  },
}));
