use crate::commands::common::{
    collect_top_level_snapshot, path_is_sensitive, safe_join_repo_path, sanitize_repo_entry_name,
    sha256_hex,
};
use crate::state::RepoFileContent;
use crate::state::RepoTreeEntry;
use std::fs;

pub(crate) fn build_repo_context(data: &crate::state::AppData, session_id: &str) -> String {
    let Some(session) = data.sessions.iter().find(|s| s.id == session_id) else {
        return "未找到当前会话对应的仓库信息。".into();
    };
    let Some(repo) = data.repos.iter().find(|r| r.id == session.repo_id) else {
        return "未找到当前会话绑定的仓库。".into();
    };

    format!(
        "关联仓库：{}\n{}",
        repo.name,
        collect_top_level_snapshot(&repo.path, 80)
    )
}

pub(crate) fn list_repo_tree_inner(repo_root: &str) -> Result<Vec<RepoTreeEntry>, String> {
    let root = std::path::PathBuf::from(repo_root);
    let mut out: Vec<RepoTreeEntry> = vec![];

    let read_dir = fs::read_dir(&root).map_err(|e| format!("read repo failed: {}", e))?;
    for entry in read_dir.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        let Some(safe_name) = sanitize_repo_entry_name(&name) else {
            continue;
        };
        let path = entry.path();
        let meta = path.metadata().ok();
        out.push(RepoTreeEntry {
            path: name,
            display_name: safe_name,
            is_dir: path.is_dir(),
            size: meta.and_then(|m| if m.is_file() { Some(m.len()) } else { None }),
        });
    }
    out.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(out)
}

pub(crate) fn read_repo_file_inner(repo_root: &str, path: &str) -> Result<RepoFileContent, String> {
    if path_is_sensitive(path) {
        return Err("敏感文件已被策略阻止读取。".into());
    }
    let file = safe_join_repo_path(repo_root, path)?;
    let raw = fs::read_to_string(&file).map_err(|e| format!("read file failed: {}", e))?;
    let max_chars = 12000usize;
    let truncated = raw.chars().count() > max_chars;
    let content = if truncated {
        let mut s = raw.chars().take(max_chars).collect::<String>();
        s.push_str("\n\n... [truncated]");
        s
    } else {
        raw
    };
    Ok(RepoFileContent {
        path: path.to_string(),
        content,
        truncated,
    })
}

pub(crate) fn write_repo_file_atomic_inner(
    repo_root: &str,
    path: &str,
    content: &str,
    if_match_sha256: Option<String>,
) -> Result<String, String> {
    if path_is_sensitive(path) {
        return Err("敏感文件已被策略阻止写入。".into());
    }
    if content.chars().count() > 200_000 {
        return Err("写入内容过大，已拒绝。".into());
    }
    let file = safe_join_repo_path(repo_root, path)?;
    let before = fs::read_to_string(&file).unwrap_or_default();
    if let Some(expected) = if_match_sha256 {
        if sha256_hex(&before) != expected {
            return Err("写入失败：文件已变更（sha256 mismatch）".into());
        }
    }
    let tmp = file.with_extension("tmp.codinggirl");
    fs::write(&tmp, content).map_err(|e| format!("write temp failed: {}", e))?;
    fs::rename(&tmp, &file).map_err(|e| format!("rename temp failed: {}", e))?;
    Ok(sha256_hex(content))
}

pub(crate) fn search_repo_inner(
    repo_root: &str,
    pattern: &str,
    max_results: usize,
) -> Result<Vec<String>, String> {
    let max_results = max_results.min(200);
    if pattern.trim().is_empty() {
        return Err("pattern is empty".into());
    }
    let re = regex::Regex::new(pattern).map_err(|e| format!("invalid regex: {}", e))?;
    let root = std::path::PathBuf::from(repo_root)
        .canonicalize()
        .map_err(|e| format!("repo root inaccessible: {}", e))?;

    let mut out: Vec<String> = Vec::new();
    for entry in walkdir::WalkDir::new(&root)
        .follow_links(false)
        .into_iter()
        .flatten()
    {
        if out.len() >= max_results {
            break;
        }
        let p = entry.path();
        if !p.is_file() {
            continue;
        }
        let rel = p
            .strip_prefix(&root)
            .ok()
            .and_then(|x| x.to_str())
            .unwrap_or("")
            .replace('\\', "/");
        if rel.starts_with(".git/")
            || rel.starts_with("node_modules/")
            || rel.starts_with("target/")
        {
            continue;
        }
        if path_is_sensitive(&rel) {
            continue;
        }
        let meta = p.metadata().ok();
        if meta.map(|m| m.len() > 512_000).unwrap_or(true) {
            continue;
        }
        let raw = fs::read_to_string(p).unwrap_or_default();
        if raw.is_empty() {
            continue;
        }
        for (idx, line) in raw.lines().enumerate() {
            if re.is_match(line) {
                out.push(format!(
                    "{}:{}:{}",
                    rel,
                    idx + 1,
                    line.chars().take(240).collect::<String>()
                ));
                if out.len() >= max_results {
                    break;
                }
            }
        }
    }
    Ok(out)
}
