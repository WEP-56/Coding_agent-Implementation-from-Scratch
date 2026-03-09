import { create } from "zustand";
import { getSecurityPolicies, saveSecurityPolicies } from "../api/bridge";
import type { SensitiveAction, SensitivePolicy, ToolPolicyKey } from "../types/models";

interface SecurityState {
  policiesByRepo: Record<string, Record<string, SensitivePolicy>>;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  getPolicy: (repoId: string, action: SensitiveAction) => SensitivePolicy;
  setPolicy: (repoId: string, action: SensitiveAction, policy: SensitivePolicy) => void;
  getToolPolicy: (repoId: string, tool: ToolPolicyKey) => SensitivePolicy;
  setToolPolicy: (repoId: string, tool: ToolPolicyKey, policy: SensitivePolicy) => void;
}

const KEY = "codinggirl.security.policies";

function readPolicies(): Record<string, Record<string, SensitivePolicy>> {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as Record<string, Record<string, SensitivePolicy>>;
  } catch {
    return {};
  }
}

function savePolicies(policies: Record<string, Record<string, SensitivePolicy>>): void {
  window.localStorage.setItem(KEY, JSON.stringify(policies));
}

export function __unsafeReadPoliciesForFallback(): Record<string, Record<string, SensitivePolicy>> {
  return readPolicies();
}

export function __unsafeSavePoliciesForFallback(policies: Record<string, Record<string, SensitivePolicy>>): void {
  savePolicies(policies);
}

function defaultPolicy(): Record<string, SensitivePolicy> {
  return {
    install_dependency: "ask",
    run_shell: "ask",
  };
}

export const useSecurityStore = create<SecurityState>((set, get) => ({
  policiesByRepo: readPolicies(),
  hydrated: false,
  hydrate: async () => {
    try {
      const remote = await getSecurityPolicies();
      const local = readPolicies();
      const next = Object.keys(remote.policiesByRepo ?? {}).length === 0 ? local : remote.policiesByRepo;
      savePolicies(next);
      set({ policiesByRepo: next, hydrated: true });
    } catch {
      set({ hydrated: true });
    }
  },
  getPolicy: (repoId, action) => {
    const repoPolicies = get().policiesByRepo[repoId] ?? defaultPolicy();
    return repoPolicies[action] ?? "ask";
  },
  setPolicy: (repoId, action, policy) => {
    const current = get().policiesByRepo;
    const repoPolicies = { ...(current[repoId] ?? defaultPolicy()) };
    repoPolicies[action] = policy;
    const next = { ...current, [repoId]: repoPolicies };
    savePolicies(next);
    set({ policiesByRepo: next });
    void saveSecurityPolicies({ policiesByRepo: next });
  },
  getToolPolicy: (repoId, tool) => {
    const repoPolicies = get().policiesByRepo[repoId] ?? defaultPolicy();
    return repoPolicies[tool] ?? "ask";
  },
  setToolPolicy: (repoId, tool, policy) => {
    const current = get().policiesByRepo;
    const repoPolicies = { ...(current[repoId] ?? defaultPolicy()) };
    repoPolicies[tool] = policy;
    const next = { ...current, [repoId]: repoPolicies };
    savePolicies(next);
    set({ policiesByRepo: next });
    void saveSecurityPolicies({ policiesByRepo: next });
  },
}));
