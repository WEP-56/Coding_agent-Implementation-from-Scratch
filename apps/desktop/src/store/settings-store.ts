import { create } from "zustand";
import { getSettings, saveSettings as persistSettingsRemote } from "../api/bridge";
import type { AppSettings, ModelConfig } from "../types/models";

interface SettingsState {
  settings: AppSettings;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  update: (patch: Partial<AppSettings>) => void;
  updateModel: (patch: Partial<ModelConfig>) => void;
  getRuleForRepo: (repoId: string) => { content: string; updatedAt: string };
  setRuleForRepo: (repoId: string, content: string) => void;
  resetRuleForRepo: (repoId: string) => void;
}

const KEY = "codinggirl.settings";

const defaults: AppSettings = {
  notificationsEnabled: true,
  defaultSessionMode: "build",
  defaultTheme: "dark",
  model: {
    provider: "mock",
    model: "mock-1",
    baseUrl: "",
    apiKey: "",
  },
  rulesByRepo: {},
};

function readSettings(): AppSettings {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<AppSettings>;
    return {
      ...defaults,
      ...parsed,
      model: {
        ...defaults.model,
        ...(parsed.model ?? {}),
      },
      rulesByRepo:
        parsed.rulesByRepo && typeof parsed.rulesByRepo === "object"
          ? parsed.rulesByRepo
          : defaults.rulesByRepo,
    };
  } catch {
    return defaults;
  }
}

function saveSettingsLocal(s: AppSettings): void {
  window.localStorage.setItem(KEY, JSON.stringify(s));
}

export function __unsafeReadSettingsForFallback(): AppSettings {
  return readSettings();
}

export function __unsafeSaveSettingsForFallback(s: AppSettings): void {
  saveSettingsLocal(s);
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: readSettings(),
  hydrated: false,
  hydrate: async () => {
    try {
      const remote = await getSettings();
      const local = readSettings();
      const remoteLooksEmpty =
        Object.keys(remote.rulesByRepo ?? {}).length === 0 &&
        remote.model.provider === "mock" &&
        remote.model.model === "mock-1" &&
        !remote.model.baseUrl &&
        !remote.model.apiKey;
      const next = remoteLooksEmpty ? local : remote;
      saveSettingsLocal(next);
      set({ settings: next, hydrated: true });
    } catch {
      set({ hydrated: true });
    }
  },
  update: (patch) => {
    const next = { ...get().settings, ...patch };
    saveSettingsLocal(next);
    set({ settings: next });
    void persistSettingsRemote(next);
  },
  updateModel: (patch) => {
    const next = {
      ...get().settings,
      model: {
        ...get().settings.model,
        ...patch,
      },
    };
    saveSettingsLocal(next);
    set({ settings: next });
    void persistSettingsRemote(next);
  },
  getRuleForRepo: (repoId) => {
    const item = get().settings.rulesByRepo[repoId];
    if (!item) return { content: "", updatedAt: "" };
    return item;
  },
  setRuleForRepo: (repoId, content) => {
    const next = {
      ...get().settings,
      rulesByRepo: {
        ...get().settings.rulesByRepo,
        [repoId]: {
          content,
          updatedAt: new Date().toISOString(),
        },
      },
    };
    saveSettingsLocal(next);
    set({ settings: next });
    void persistSettingsRemote(next);
  },
  resetRuleForRepo: (repoId) => {
    const nextRules = { ...get().settings.rulesByRepo };
    delete nextRules[repoId];
    const next = {
      ...get().settings,
      rulesByRepo: nextRules,
    };
    saveSettingsLocal(next);
    set({ settings: next });
    void persistSettingsRemote(next);
  },
}));
