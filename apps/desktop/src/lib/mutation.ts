import type { ArtifactItem } from "../types/models";

function sortableTime(value?: string | null): number {
  if (!value) return 0;
  if (/^\d+$/.test(value)) {
    const numeric = Number(value);
    return value.length <= 10 ? numeric * 1000 : numeric;
  }
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function rollbackMetaPathForArtifact(
  artifact: ArtifactItem,
): string | null {
  if (artifact.mutationProvenance?.rollbackMetaPath) {
    return artifact.mutationProvenance.rollbackMetaPath;
  }
  if (
    artifact.kind === "trace" &&
    artifact.filePath.endsWith("rollback_meta.json")
  ) {
    return artifact.filePath;
  }
  return null;
}

export function findLatestRollbackArtifact(
  artifacts: ArtifactItem[],
): ArtifactItem | null {
  const candidates = artifacts.filter(
    (artifact) => rollbackMetaPathForArtifact(artifact) !== null,
  );
  if (candidates.length === 0) return null;
  return (
    [...candidates].sort(
      (lhs, rhs) => sortableTime(rhs.createdAt) - sortableTime(lhs.createdAt),
    )[0] ?? null
  );
}
