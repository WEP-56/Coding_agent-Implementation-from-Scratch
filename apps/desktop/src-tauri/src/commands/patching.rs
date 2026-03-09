use crate::commands::common::{
    mode_allows_write, now_millis_str, path_is_sensitive, safe_join_repo_path, utc_now_iso,
};
use crate::commands::repo::write_repo_file_atomic_inner;
use crate::patch_apply;
use crate::state::{ArtifactItem, DiffFile, MutationProvenance, MutationSourceKind};
use serde_json::json;
use std::fs;

const DIFF_CONTEXT_LINES: usize = 3;

pub(crate) struct PersistedMutationArtifacts {
    pub diffs: Vec<DiffFile>,
    pub artifacts: Vec<ArtifactItem>,
}

pub(crate) fn mutation_source_for_tool(
    tool_name: &str,
    approval_id: Option<&str>,
) -> MutationSourceKind {
    if approval_id.is_some() {
        return MutationSourceKind::ApprovalReplay;
    }
    match tool_name {
        "apply_patch" => MutationSourceKind::ApplyPatch,
        "repo_apply_unified_diff" => MutationSourceKind::UnifiedDiff,
        "repo_write_file_atomic" => MutationSourceKind::DirectWrite,
        _ => MutationSourceKind::DirectWrite,
    }
}

pub(crate) fn build_mutation_provenance(
    session_id: &str,
    tool_name: &str,
    run_id: Option<&str>,
    correlation_id: Option<String>,
    artifact_group_id: Option<String>,
    rollback_meta_path: Option<String>,
    approval_id: Option<String>,
) -> MutationProvenance {
    MutationProvenance {
        source_kind: mutation_source_for_tool(tool_name, approval_id.as_deref()),
        tool_name: tool_name.to_string(),
        session_id: session_id.to_string(),
        run_id: run_id.map(str::to_string),
        correlation_id,
        artifact_group_id,
        rollback_meta_path,
        approval_id,
        created_at: utc_now_iso(),
    }
}

fn sha256_hex_bytes(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    h.update(bytes);
    hex::encode(h.finalize())
}

#[derive(Debug, Clone)]
struct UnifiedDiffHunk {
    old_start: usize,
    old_len: usize,
    lines: Vec<String>,
}

#[derive(Debug, Clone)]
struct UnifiedFilePatch {
    old_path: String,
    new_path: String,
    hunks: Vec<UnifiedDiffHunk>,
}

fn normalize_patch_path(path: &str) -> String {
    if let Some(stripped) = path.strip_prefix("a/") {
        return stripped.to_string();
    }
    if let Some(stripped) = path.strip_prefix("b/") {
        return stripped.to_string();
    }
    path.to_string()
}

fn clip_chars(input: &str, max_chars: usize) -> String {
    input.chars().take(max_chars).collect::<String>()
}

fn unified_range(start: usize, len: usize) -> String {
    if len == 1 {
        format!("{}", start.max(1))
    } else {
        format!("{},{}", start.max(1), len)
    }
}

fn contiguous_line_change_window(
    before_lines: &[&str],
    after_lines: &[&str],
) -> (usize, usize, usize, usize) {
    let mut prefix = 0usize;
    let max_prefix = before_lines.len().min(after_lines.len());
    while prefix < max_prefix && before_lines[prefix] == after_lines[prefix] {
        prefix += 1;
    }

    let mut suffix = 0usize;
    while suffix < before_lines.len().saturating_sub(prefix)
        && suffix < after_lines.len().saturating_sub(prefix)
        && before_lines[before_lines.len() - 1 - suffix]
            == after_lines[after_lines.len() - 1 - suffix]
    {
        suffix += 1;
    }

    let before_changed_end = before_lines.len().saturating_sub(suffix);
    let after_changed_end = after_lines.len().saturating_sub(suffix);
    (prefix, before_changed_end, prefix, after_changed_end)
}

fn build_simple_unified_diff(path: &str, before: &str, after: &str) -> String {
    let before_lines = before.lines().collect::<Vec<_>>();
    let after_lines = after.lines().collect::<Vec<_>>();
    let (before_change_start, before_change_end, after_change_start, after_change_end) =
        contiguous_line_change_window(&before_lines, &after_lines);

    let context_start = before_change_start.saturating_sub(DIFF_CONTEXT_LINES);
    let context_suffix = DIFF_CONTEXT_LINES;
    let before_context_end = (before_change_end + context_suffix).min(before_lines.len());
    let after_context_end = (after_change_end + context_suffix).min(after_lines.len());

    let old_len = before_context_end.saturating_sub(context_start);
    let new_len = after_context_end.saturating_sub(context_start);
    let old_start = if old_len == 0 {
        context_start
    } else {
        context_start + 1
    };
    let new_start = if new_len == 0 {
        context_start
    } else {
        context_start + 1
    };

    let mut out = String::new();
    out.push_str(&format!("--- {}\n", path));
    out.push_str(&format!("+++ {}\n", path));
    out.push_str(&format!(
        "@@ -{} +{} @@\n",
        unified_range(old_start, old_len),
        unified_range(new_start, new_len)
    ));

    for line in before_lines
        .iter()
        .take(before_change_start)
        .skip(context_start)
    {
        out.push_str(&format!(" {}\n", line));
    }
    for line in before_lines
        .iter()
        .take(before_change_end)
        .skip(before_change_start)
    {
        out.push_str(&format!("-{}\n", line));
    }
    for line in after_lines
        .iter()
        .take(after_change_end)
        .skip(after_change_start)
    {
        out.push_str(&format!("+{}\n", line));
    }
    for line in after_lines
        .iter()
        .take(after_context_end)
        .skip(after_change_end)
    {
        out.push_str(&format!(" {}\n", line));
    }

    out
}

fn count_diff_lines(unified: &str) -> (i32, i32) {
    let mut additions = 0i32;
    let mut deletions = 0i32;
    for line in unified.lines() {
        if line.starts_with("+++") || line.starts_with("---") {
            continue;
        }
        if line.starts_with('+') {
            additions += 1;
        } else if line.starts_with('-') {
            deletions += 1;
        }
    }
    (additions, deletions)
}

pub(crate) fn build_direct_write_diff(path: &str, before: &str, after: &str) -> DiffFile {
    let unified = build_simple_unified_diff(path, before, after);
    let (added_lines, removed_lines) = count_diff_lines(&unified);

    DiffFile {
        id: format!("d-{}", now_millis_str()),
        path: path.to_string(),
        run_id: None,
        additions: added_lines,
        deletions: removed_lines,
        old_snippet: clip_chars(before, 600),
        new_snippet: clip_chars(after, 600),
        unified_snippet: clip_chars(&unified, 1600),
        diff: unified,
        mutation_provenance: None,
    }
}

fn parse_hunk_header(line: &str) -> Result<(usize, usize, usize, usize), String> {
    if !line.starts_with("@@ ") {
        return Err("invalid hunk header".into());
    }
    let end = line
        .find(" @@")
        .ok_or_else(|| "invalid hunk header (missing end marker)".to_string())?;
    let body = &line[3..end];
    let parts: Vec<&str> = body.split_whitespace().collect();
    if parts.len() < 2 {
        return Err("invalid hunk header body".into());
    }
    let old_part = parts[0];
    let new_part = parts[1];
    if !old_part.starts_with('-') || !new_part.starts_with('+') {
        return Err("invalid hunk header ranges".into());
    }
    let parse_range = |raw: &str| -> Result<(usize, usize), String> {
        let r = &raw[1..];
        if let Some((a, b)) = r.split_once(',') {
            let start = a
                .parse::<usize>()
                .map_err(|_| "invalid range start".to_string())?;
            let len = b
                .parse::<usize>()
                .map_err(|_| "invalid range len".to_string())?;
            Ok((start, len))
        } else {
            let start = r
                .parse::<usize>()
                .map_err(|_| "invalid range start".to_string())?;
            Ok((start, 1))
        }
    };
    let (old_start, old_len) = parse_range(old_part)?;
    let (new_start, new_len) = parse_range(new_part)?;
    Ok((old_start, old_len, new_start, new_len))
}

fn parse_unified_diff_strict(diff_text: &str) -> Result<Vec<UnifiedFilePatch>, String> {
    let lines: Vec<&str> = diff_text.lines().collect();
    let mut i = 0usize;
    let mut out: Vec<UnifiedFilePatch> = Vec::new();
    while i < lines.len() {
        if !lines[i].starts_with("--- ") {
            i += 1;
            continue;
        }
        let old_path = lines[i][4..].trim().to_string();
        i += 1;
        if i >= lines.len() || !lines[i].starts_with("+++ ") {
            return Err("invalid patch: missing +++ line".into());
        }
        let new_path = lines[i][4..].trim().to_string();
        i += 1;

        let mut hunks: Vec<UnifiedDiffHunk> = Vec::new();
        while i < lines.len() && !lines[i].starts_with("--- ") {
            if !lines[i].starts_with("@@ ") {
                i += 1;
                continue;
            }
            let (old_start, old_len, _new_start, _new_len) = parse_hunk_header(lines[i])?;
            i += 1;
            let mut hunk_lines: Vec<String> = Vec::new();
            while i < lines.len() && !lines[i].starts_with("@@ ") && !lines[i].starts_with("--- ") {
                hunk_lines.push(lines[i].to_string());
                i += 1;
            }
            hunks.push(UnifiedDiffHunk {
                old_start,
                old_len,
                lines: hunk_lines,
            });
        }

        out.push(UnifiedFilePatch {
            old_path,
            new_path,
            hunks,
        });
    }
    if out.is_empty() {
        return Err("empty patch".into());
    }
    Ok(out)
}

fn apply_unified_file_patch(
    original: Vec<String>,
    patch: &UnifiedFilePatch,
) -> Result<Vec<String>, String> {
    let mut lines = original;
    let mut delta: isize = 0;
    for h in &patch.hunks {
        let base = (h.old_start as isize - 1) + delta;
        if base < 0 {
            return Err("hunk out of range".into());
        }
        let mut idx = base as usize;
        let mut old_count = 0usize;

        for hl in &h.lines {
            if hl.starts_with('\\') {
                continue;
            }
            let mut chars = hl.chars();
            let prefix = chars.next().unwrap_or(' ');
            let content: String = chars.collect();
            match prefix {
                ' ' => {
                    old_count += 1;
                    if idx >= lines.len() || lines[idx] != content {
                        return Err("context mismatch".into());
                    }
                    idx += 1;
                }
                '-' => {
                    old_count += 1;
                    if idx >= lines.len() || lines[idx] != content {
                        return Err("delete mismatch".into());
                    }
                    lines.remove(idx);
                    delta -= 1;
                }
                '+' => {
                    lines.insert(idx, content);
                    idx += 1;
                    delta += 1;
                }
                _ => return Err("invalid hunk line prefix".into()),
            }
        }

        if old_count != h.old_len {
            return Err("hunk old_len mismatch".into());
        }
    }
    Ok(lines)
}

pub(crate) fn apply_unified_diff_inner(
    repo_root: &str,
    diff_text: &str,
    mode: &str,
) -> Result<Vec<DiffFile>, String> {
    if !mode_allows_write(mode) {
        return Err("patch apply is not allowed in current mode".into());
    }
    if diff_text.chars().count() > 300_000 {
        return Err("diff too large".into());
    }
    let parsed = parse_unified_diff_strict(diff_text)?;
    let mut out: Vec<DiffFile> = Vec::new();
    struct Staged {
        path: String,
        before: String,
        after: String,
        delete_file: bool,
    }
    let mut staged: Vec<Staged> = Vec::new();

    for fp in parsed {
        let old_path = fp.old_path.trim().to_string();
        let new_path = fp.new_path.trim().to_string();

        if old_path == "/dev/null" {
            let target = normalize_patch_path(&new_path);
            if path_is_sensitive(&target) {
                return Err("patch touches sensitive path".into());
            }
            let mut after_lines: Vec<String> = Vec::new();
            for h in &fp.hunks {
                for hl in &h.lines {
                    if let Some(rest) = hl.strip_prefix('+') {
                        after_lines.push(rest.to_string());
                    }
                }
            }
            let after = if after_lines.is_empty() {
                String::new()
            } else {
                format!("{}\n", after_lines.join("\n"))
            };
            staged.push(Staged {
                path: target,
                before: String::new(),
                after,
                delete_file: false,
            });
            continue;
        }

        if new_path == "/dev/null" {
            let target = normalize_patch_path(&old_path);
            if path_is_sensitive(&target) {
                return Err("patch touches sensitive path".into());
            }
            let before = fs::read_to_string(safe_join_repo_path(repo_root, &target)?)
                .map_err(|e| format!("read file failed: {}", e))?;
            staged.push(Staged {
                path: target,
                before,
                after: String::new(),
                delete_file: true,
            });
            continue;
        }

        let target_old = normalize_patch_path(&old_path);
        let target_new = normalize_patch_path(&new_path);
        if target_old != target_new {
            return Err("rename in unified diff is not supported".into());
        }
        if path_is_sensitive(&target_new) {
            return Err("patch touches sensitive path".into());
        }
        let before = fs::read_to_string(safe_join_repo_path(repo_root, &target_new)?)
            .map_err(|e| format!("read file failed: {}", e))?;
        let before_lines: Vec<String> = before.lines().map(|s| s.to_string()).collect();
        let after_lines = apply_unified_file_patch(before_lines, &fp)?;
        let after = if after_lines.is_empty() {
            String::new()
        } else {
            format!("{}\n", after_lines.join("\n"))
        };
        staged.push(Staged {
            path: target_new,
            before,
            after,
            delete_file: false,
        });
    }

    for s in &staged {
        if s.delete_file {
            let p = safe_join_repo_path(repo_root, &s.path)?;
            if p.exists() {
                fs::remove_file(&p).map_err(|e| format!("delete file failed: {}", e))?;
            }
            continue;
        }
        let _ = write_repo_file_atomic_inner(repo_root, &s.path, &s.after, None)?;
    }

    for s in staged {
        let unified = build_simple_unified_diff(&s.path, &s.before, &s.after);
        let (additions, deletions) = count_diff_lines(&unified);
        out.push(DiffFile {
            id: format!("d-{}", now_millis_str()),
            path: s.path,
            run_id: None,
            additions,
            deletions,
            old_snippet: s.before.chars().take(600).collect::<String>(),
            new_snippet: s.after.chars().take(600).collect::<String>(),
            unified_snippet: unified.chars().take(1200).collect::<String>(),
            diff: unified,
            mutation_provenance: None,
        });
    }
    Ok(out)
}

pub(crate) fn apply_codex_style_patch_inner(
    repo_root: &str,
    patch_text: &str,
    mode: &str,
) -> Result<Vec<DiffFile>, String> {
    if !mode_allows_write(mode) {
        return Err("patch apply is not allowed in current mode".into());
    }
    if patch_text.chars().count() > 600_000 {
        return Err("patch too large".into());
    }
    let parsed = patch_apply::parse_apply_patch(patch_text)?;

    struct Stage {
        path: String,
        before: String,
        after: String,
        op: String,
        move_to: Option<String>,
    }

    let mut staged: Vec<Stage> = Vec::new();
    for h in parsed.hunks {
        match h {
            patch_apply::PatchHunk::AddFile { path, contents } => {
                let rel = path.to_string_lossy().replace('\\', "/");
                if path_is_sensitive(&rel) {
                    return Err("patch touches sensitive path".into());
                }
                let abs = safe_join_repo_path(repo_root, &rel)?;
                if abs.exists() {
                    return Err("add file failed: already exists".into());
                }
                staged.push(Stage {
                    path: rel,
                    before: String::new(),
                    after: contents,
                    op: "add".into(),
                    move_to: None,
                });
            }
            patch_apply::PatchHunk::DeleteFile { path } => {
                let rel = path.to_string_lossy().replace('\\', "/");
                if path_is_sensitive(&rel) {
                    return Err("patch touches sensitive path".into());
                }
                let abs = safe_join_repo_path(repo_root, &rel)?;
                let before =
                    fs::read_to_string(&abs).map_err(|e| format!("read file failed: {}", e))?;
                staged.push(Stage {
                    path: rel,
                    before,
                    after: String::new(),
                    op: "delete".into(),
                    move_to: None,
                });
            }
            patch_apply::PatchHunk::UpdateFile {
                path,
                move_path,
                chunks,
            } => {
                let rel = path.to_string_lossy().replace('\\', "/");
                if path_is_sensitive(&rel) {
                    return Err("patch touches sensitive path".into());
                }
                let abs = safe_join_repo_path(repo_root, &rel)?;
                let before =
                    fs::read_to_string(&abs).map_err(|e| format!("read file failed: {}", e))?;
                let after = patch_apply::apply_update_chunks(&before, &chunks)?;
                let move_to = move_path.map(|p| p.to_string_lossy().replace('\\', "/"));
                if let Some(dest) = &move_to {
                    if path_is_sensitive(dest) {
                        return Err("patch touches sensitive path".into());
                    }
                }
                staged.push(Stage {
                    path: rel,
                    before,
                    after,
                    op: "update".into(),
                    move_to,
                });
            }
        }
    }

    for s in &staged {
        if s.op == "add" {
            let abs = safe_join_repo_path(repo_root, &s.path)?;
            if let Some(parent) = abs.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            fs::write(&abs, &s.after).map_err(|e| format!("write file failed: {}", e))?;
            continue;
        }
        if s.op == "delete" {
            let abs = safe_join_repo_path(repo_root, &s.path)?;
            if abs.exists() {
                fs::remove_file(&abs).map_err(|e| format!("delete file failed: {}", e))?;
            }
            continue;
        }
        if let Some(dest) = &s.move_to {
            let from_abs = safe_join_repo_path(repo_root, &s.path)?;
            let to_abs = safe_join_repo_path(repo_root, dest)?;
            if to_abs.exists() {
                return Err("move failed: destination exists".into());
            }
            if let Some(parent) = to_abs.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            fs::write(&to_abs, &s.after).map_err(|e| format!("write file failed: {}", e))?;
            fs::remove_file(&from_abs).map_err(|e| format!("remove original failed: {}", e))?;
        } else {
            let _ = write_repo_file_atomic_inner(repo_root, &s.path, &s.after, None)?;
        }
    }

    let mut out: Vec<DiffFile> = Vec::new();
    for s in staged {
        let path = s.move_to.clone().unwrap_or_else(|| s.path.clone());
        let unified = build_simple_unified_diff(&path, &s.before, &s.after);
        let (additions, deletions) = count_diff_lines(&unified);
        out.push(DiffFile {
            id: format!("d-{}", now_millis_str()),
            path,
            run_id: None,
            additions,
            deletions,
            old_snippet: s.before.chars().take(600).collect::<String>(),
            new_snippet: s.after.chars().take(600).collect::<String>(),
            unified_snippet: unified.chars().take(1200).collect::<String>(),
            diff: unified,
            mutation_provenance: None,
        });
    }
    Ok(out)
}

pub(crate) fn persist_patch_artifacts(
    repo_root: &str,
    session_id: &str,
    tool_name: &str,
    patch_text: &str,
    diffs: &[DiffFile],
    run_id: Option<&str>,
    correlation_id: Option<String>,
    approval_id: Option<&str>,
) -> Result<PersistedMutationArtifacts, String> {
    let ts = now_millis_str();
    let artifact_group_id = Some(ts.clone());
    let base = std::path::PathBuf::from(repo_root)
        .join(".codinggirl")
        .join("artifacts")
        .join(session_id)
        .join(&ts);
    fs::create_dir_all(&base).map_err(|e| format!("create artifacts dir failed: {}", e))?;

    let patch_file = base.join(format!("{}_patch.txt", tool_name));
    fs::write(&patch_file, patch_text)
        .map_err(|e| format!("write patch artifact failed: {}", e))?;
    let rollback_file = base.join("rollback_meta.json");
    let rollback_meta_path = Some(rollback_file.to_string_lossy().replace('\\', "/"));
    let base_provenance = build_mutation_provenance(
        session_id,
        tool_name,
        run_id,
        correlation_id.clone(),
        artifact_group_id.clone(),
        rollback_meta_path.clone(),
        approval_id.map(str::to_string),
    );
    let base_provenance_json = serde_json::to_value(&base_provenance).unwrap_or(json!(null));

    let rollback_meta = json!({
        "session_id": session_id,
        "tool_name": tool_name,
        "created_at": utc_now_iso(),
        "artifact_group_id": ts,
        "run_id": run_id,
        "correlation_id": correlation_id.clone(),
        "approval_id": approval_id,
        "provenance": base_provenance_json.clone(),
        "files": diffs.iter().map(|d| json!({
            "path": d.path,
            "additions": d.additions,
            "deletions": d.deletions,
            "old_content": d.old_snippet,
            "new_content": d.new_snippet,
            "old_snippet": d.old_snippet.chars().take(600).collect::<String>(),
            "new_snippet": d.new_snippet.chars().take(600).collect::<String>(),
            "diff": d.diff,
            "mutation_provenance": d.mutation_provenance.clone().map(serde_json::to_value).transpose().unwrap_or(None).unwrap_or_else(|| base_provenance_json.clone()),
        })).collect::<Vec<_>>()
    });
    fs::write(&rollback_file, rollback_meta.to_string())
        .map_err(|e| format!("write rollback metadata failed: {}", e))?;
    let diff_provenance = build_mutation_provenance(
        session_id,
        tool_name,
        run_id,
        correlation_id.clone(),
        artifact_group_id.clone(),
        rollback_meta_path.clone(),
        approval_id.map(str::to_string),
    );
    let diffs = diffs
        .iter()
        .cloned()
        .map(|mut diff| {
            diff.mutation_provenance = Some(diff_provenance.clone());
            diff
        })
        .collect::<Vec<_>>();

    let to_item = |id_suffix: &str,
                   name: String,
                   kind: crate::state::ArtifactKind,
                   file: &std::path::Path| {
        let size_kb = file
            .metadata()
            .ok()
            .map(|m| (m.len() as f64 / 1024.0).ceil() as i32)
            .unwrap_or(0);
        let bytes = fs::read(file).unwrap_or_default();
        let sha = if bytes.is_empty() {
            None
        } else {
            Some(sha256_hex_bytes(&bytes))
        };
        let item_provenance = build_mutation_provenance(
            session_id,
            tool_name,
            run_id,
            correlation_id.clone(),
            artifact_group_id.clone(),
            rollback_meta_path.clone(),
            approval_id.map(str::to_string),
        );
        ArtifactItem {
            id: format!("a-{}-{}", ts, id_suffix),
            name,
            kind,
            run_id: run_id.map(|v| v.to_string()),
            file_path: file.to_string_lossy().replace('\\', "/"),
            size_kb,
            created_at: utc_now_iso(),
            correlation_id: correlation_id.clone(),
            sha256: sha,
            provenance: Some(format!(
                "{} · {} · {}",
                match item_provenance.source_kind {
                    MutationSourceKind::ApplyPatch => "apply_patch",
                    MutationSourceKind::UnifiedDiff => "unified_diff",
                    MutationSourceKind::DirectWrite => "direct_write",
                    MutationSourceKind::ApprovalReplay => "approval_replay",
                    MutationSourceKind::Rollback => "rollback",
                },
                tool_name,
                session_id
            )),
            mutation_provenance: Some(item_provenance),
        }
    };

    Ok(PersistedMutationArtifacts {
        diffs,
        artifacts: vec![
            to_item(
                "patch",
                format!("{} patch", tool_name),
                crate::state::ArtifactKind::Patch,
                &patch_file,
            ),
            to_item(
                "rollback",
                "rollback metadata".into(),
                crate::state::ArtifactKind::Trace,
                &rollback_file,
            ),
        ],
    })
}
