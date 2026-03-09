import { create } from "zustand";

import { applyTheme, readTheme, type ThemeMode } from "../lib/theme";
import type { RepoItem } from "../types/models";

const REPOS_KEY = "codinggirl.repos";
const CURRENT_REPO_KEY = "codinggirl.currentRepoId";

function safeParseRepos(raw: string | null): RepoItem[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const obj = item as Record<string, unknown>;
        if (typeof obj.id !== "string") return null;
        if (typeof obj.name !== "string") return null;
        if (typeof obj.path !== "string") return null;
        return {
          id: obj.id,
          name: obj.name,
          path: obj.path,
          pinned: Boolean(obj.pinned),
        } satisfies RepoItem;
      })
      .filter((x): x is RepoItem => x !== null);
  } catch {
    return [];
  }
}

function saveRepos(repos: RepoItem[]): void {
  window.localStorage.setItem(REPOS_KEY, JSON.stringify(repos));
}

function readCurrentRepoId(): string | null {
  const id = window.localStorage.getItem(CURRENT_REPO_KEY);
  return id && id.length > 0 ? id : null;
}

function saveCurrentRepoId(repoId: string | null): void {
  if (!repoId) {
    window.localStorage.removeItem(CURRENT_REPO_KEY);
    return;
  }
  window.localStorage.setItem(CURRENT_REPO_KEY, repoId);
}

interface AppState {
  theme: ThemeMode;
  currentRepoId: string | null;
  repos: RepoItem[];
  setRepos: (repos: RepoItem[]) => void;
  addRepo: (repo: RepoItem) => void;
  removeRepo: (repoId: string) => void;
  toggleRepoPin: (repoId: string) => void;
  setCurrentRepo: (repoId: string) => void;
  toggleTheme: () => void;
}

const initialTheme = readTheme();
applyTheme(initialTheme);
const initialRepos = safeParseRepos(window.localStorage.getItem(REPOS_KEY));
const initialCurrentRepoId = readCurrentRepoId() ?? initialRepos[0]?.id ?? null;

export const useAppStore = create<AppState>((set, get) => ({
  theme: initialTheme,
  currentRepoId: initialCurrentRepoId,
  repos: initialRepos,
  setRepos: (repos) => {
    const previousCurrent = get().currentRepoId;
    const hasPrevious = previousCurrent ? repos.some((r) => r.id === previousCurrent) : false;
    const nextCurrent = hasPrevious ? previousCurrent : (repos[0]?.id ?? null);
    // backend is source of truth for repo ids; persist merged snapshot locally.
    saveRepos(repos);
    saveCurrentRepoId(nextCurrent);
    set({ repos, currentRepoId: nextCurrent });
  },
  addRepo: (repo) => {
    const current = get().repos;
    const dedupByPath = current.filter((r) => r.path !== repo.path);
    const next = [repo, ...dedupByPath];
    saveRepos(next);
    saveCurrentRepoId(repo.id);
    set({ repos: next, currentRepoId: repo.id });
  },
  removeRepo: (repoId) => {
    const current = get().repos;
    const next = current.filter((r) => r.id !== repoId);
    const currentRepoId = get().currentRepoId;
    const nextCurrent = currentRepoId === repoId ? (next[0]?.id ?? null) : currentRepoId;
    saveRepos(next);
    saveCurrentRepoId(nextCurrent);
    set({ repos: next, currentRepoId: nextCurrent });
  },
  toggleRepoPin: (repoId) => {
    const next = get().repos.map((r) => (r.id === repoId ? { ...r, pinned: !r.pinned } : r));
    // pinned first, then stable insertion order for same pinned state
    next.sort((a, b) => Number(b.pinned) - Number(a.pinned));
    saveRepos(next);
    set({ repos: next });
  },
  setCurrentRepo: (repoId) => {
    saveCurrentRepoId(repoId);
    set({ currentRepoId: repoId });
  },
  toggleTheme: () => {
    const next = get().theme === "dark" ? "light" : "dark";
    applyTheme(next);
    set({ theme: next });
  },
}));
