use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub(crate) fn utc_now_iso() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{}", now)
}

pub(crate) fn now_millis_str() -> String {
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    format!("{}", ms)
}

pub(crate) fn session_repo_path(
    data: &crate::state::AppData,
    session_id: &str,
) -> Result<String, String> {
    let session = data
        .sessions
        .iter()
        .find(|s| s.id == session_id)
        .ok_or_else(|| "session not found".to_string())?;
    if let Some(repo) = data.repos.iter().find(|r| r.id == session.repo_id) {
        return Ok(repo.path.clone());
    }
    // Resilient fallback for stale sessions (front/back state mismatch).
    if let Some(first_repo) = data.repos.first() {
        return Ok(first_repo.path.clone());
    }
    Err("repo not found for session".to_string())
}

pub(crate) fn ensure_session_repo_link(
    data: &mut crate::state::AppData,
    session_id: &str,
) -> Result<(), String> {
    let Some(session_idx) = data.sessions.iter().position(|s| s.id == session_id) else {
        return Err("session not found".to_string());
    };
    let repo_id = data.sessions[session_idx].repo_id.clone();
    if data.repos.iter().any(|r| r.id == repo_id) {
        return Ok(());
    }
    let Some(first_repo) = data.repos.first() else {
        return Err("repo not found for session".to_string());
    };
    data.sessions[session_idx].repo_id = first_repo.id.clone();
    Ok(())
}

pub(crate) fn safe_join_repo_path(repo_root: &str, rel_path: &str) -> Result<PathBuf, String> {
    let root = PathBuf::from(repo_root);
    let canonical_root = root
        .canonicalize()
        .map_err(|e| format!("repo root inaccessible: {}", e))?;
    let candidate = canonical_root.join(rel_path);
    let canonical_candidate = candidate
        .canonicalize()
        .or_else(|_| {
            candidate
                .parent()
                .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "invalid parent"))?
                .canonicalize()
                .map(|p| p.join(candidate.file_name().unwrap_or_default()))
        })
        .map_err(|e| format!("path resolve failed: {}", e))?;
    if !canonical_candidate.starts_with(&canonical_root) {
        return Err("path escapes repository root".into());
    }
    Ok(canonical_candidate)
}

pub(crate) fn resolve_repo_scoped_path(
    repo_root: &str,
    given_path: &str,
) -> Result<PathBuf, String> {
    let root = PathBuf::from(repo_root)
        .canonicalize()
        .map_err(|e| format!("repo root inaccessible: {}", e))?;
    let p = PathBuf::from(given_path);
    if p.is_absolute() {
        let cp = p
            .canonicalize()
            .map_err(|e| format!("path inaccessible: {}", e))?;
        if !cp.starts_with(&root) {
            return Err("path escapes repository root".into());
        }
        return Ok(cp);
    }
    safe_join_repo_path(repo_root, given_path)
}

pub(crate) fn sanitize_repo_entry_name(name: &str) -> Option<String> {
    let lower = name.to_ascii_lowercase();
    let deny = [
        ".env",
        "id_rsa",
        "credentials",
        "secret",
        ".pem",
        ".p12",
        ".key",
        ".sqlite",
    ];
    if deny.iter().any(|k| lower.contains(k)) {
        return None;
    }
    let clipped = if name.chars().count() > 120 {
        let mut s = name.chars().take(117).collect::<String>();
        s.push_str("...");
        s
    } else {
        name.to_string()
    };
    Some(clipped)
}

pub(crate) fn path_is_sensitive(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    let deny = [
        ".env",
        "id_rsa",
        "credentials",
        "secret",
        ".pem",
        ".p12",
        ".key",
        ".sqlite",
    ];
    deny.iter().any(|k| lower.contains(k))
}

pub(crate) fn collect_top_level_snapshot(repo_path: &str, limit: usize) -> String {
    let path = Path::new(repo_path);
    if !path.exists() {
        return "仓库路径不存在。".into();
    }

    let mut entries: Vec<String> = match fs::read_dir(path) {
        Ok(read_dir) => read_dir
            .filter_map(|entry| entry.ok())
            .filter_map(|entry| {
                let name = entry.file_name().to_string_lossy().to_string();
                let safe_name = sanitize_repo_entry_name(&name)?;
                let kind = if entry.path().is_dir() { "dir" } else { "file" };
                Some(format!("{} ({})", safe_name, kind))
            })
            .collect(),
        Err(_) => return "无法读取仓库目录。".into(),
    };

    entries.sort();
    if entries.is_empty() {
        return "仓库目录为空。".into();
    }

    let total = entries.len();
    let shown = entries.into_iter().take(limit).collect::<Vec<_>>();
    format!(
        "顶层目录快照（显示 {}/{} 项）：\n{}",
        shown.len(),
        total,
        shown.join("\n")
    )
}

pub(crate) fn sha256_hex(text: &str) -> String {
    let mut h = Sha256::new();
    h.update(text.as_bytes());
    let out = h.finalize();
    hex::encode(out)
}

pub(crate) fn mode_allows_write(mode: &str) -> bool {
    let m = mode.trim().to_ascii_lowercase();
    m == "auto" || m == "build"
}
