import { Button } from "../ui/button";
import type { ArtifactItem } from "../../types/models";

interface ArtifactsPanelProps {
  items: ArtifactItem[];
  onCopyPath: (path: string) => void;
  onOpenPath: (path: string) => void;
  supportsNativeOpen: boolean;
}

export function ArtifactsPanel({
  items,
  onCopyPath,
  onOpenPath,
  supportsNativeOpen,
}: ArtifactsPanelProps) {
  if (items.length === 0)
    return <div className="text-xs text-muted-foreground">暂无产物。</div>;

  return (
    <div className="space-y-2">
      {items.map((a) => (
        <div key={a.id} className="rounded border border-border p-2">
          <div className="text-xs font-medium">{a.name}</div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            类型：{a.kind} · 大小：{a.sizeKb}KB · 创建：{a.createdAt}
          </div>
          {a.provenance ? (
            <div className="mt-1 text-[10px] text-muted-foreground">
              来源：{a.provenance}
            </div>
          ) : null}
          {a.mutationProvenance ? (
            <div className="mt-1 text-[10px] text-muted-foreground">
              变更来源：{a.mutationProvenance.sourceKind} · tool=
              {a.mutationProvenance.toolName}
              {a.mutationProvenance.rollbackMetaPath
                ? ` · rollback=${a.mutationProvenance.rollbackMetaPath}`
                : ""}
              {a.mutationProvenance.approvalId
                ? ` · approval=${a.mutationProvenance.approvalId}`
                : ""}
            </div>
          ) : null}
          {a.sha256 ? (
            <div className="mt-1 break-all text-[10px] text-muted-foreground">
              sha256：{a.sha256}
            </div>
          ) : null}
          <div className="mt-2 flex gap-2">
            <Button
              variant="outline"
              className="h-7 px-2 text-xs"
              onClick={() => onOpenPath(a.filePath)}
            >
              {supportsNativeOpen ? "打开" : "选择并打开"}
            </Button>
            <Button
              variant="outline"
              className="h-7 px-2 text-xs"
              onClick={() => onCopyPath(a.filePath)}
            >
              复制路径
            </Button>
          </div>
          <div className="mt-1 truncate text-[10px] text-muted-foreground">
            路径：{a.filePath}
          </div>
        </div>
      ))}
    </div>
  );
}
