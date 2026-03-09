use crate::commands::common::utc_now_iso;
use crate::state::MemoryBlock;
use std::fs;

pub(crate) fn is_safe_memory_label(label: &str) -> bool {
    if label.is_empty() || label.len() > 64 {
        return false;
    }
    label
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
}

pub(crate) fn normalize_memory_scope(scope: &str) -> Option<String> {
    let s = scope.trim().to_ascii_lowercase();
    if s == "global" || s == "project" {
        Some(s)
    } else {
        None
    }
}

pub(crate) fn memory_block_dir_for_repo(
    repo_root: &str,
    scope: &str,
) -> Result<std::path::PathBuf, String> {
    let root = std::path::PathBuf::from(repo_root);
    let root = root
        .canonicalize()
        .map_err(|e| format!("repo root inaccessible: {}", e))?;
    if scope == "project" {
        Ok(root.join(".codinggirl").join("memory"))
    } else {
        Ok(root.join(".codinggirl").join("memory").join("global"))
    }
}

pub(crate) fn ensure_seed_memory_blocks(repo_root: &str) -> Result<(), String> {
    let seeds: Vec<(String, String, String)> = vec![
        (
            "global".into(),
            "persona".into(),
            "Agent persona / rules".into(),
        ),
        ("global".into(), "human".into(), "User preferences".into()),
        (
            "project".into(),
            "project".into(),
            "Project-specific context".into(),
        ),
    ];

    for (scope, label, desc) in seeds {
        let dir = memory_block_dir_for_repo(repo_root, &scope)?;
        fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let gi = dir.join(".gitignore");
        if !gi.exists() {
            let _ = fs::write(&gi, "*\n");
        }
        let path = dir.join(format!("{}.md", label));
        if !path.exists() {
            let stub = MemoryBlock {
                label: label.clone(),
                scope: scope.clone(),
                description: Some(desc),
                limit: 2000,
                read_only: false,
                content: "".into(),
                updated_at: utc_now_iso(),
            };
            write_memory_block_to_file(repo_root, &stub)?;
        }
    }
    Ok(())
}

pub(crate) fn read_memory_block_from_file(
    repo_root: &str,
    scope: &str,
    label: &str,
) -> Result<MemoryBlock, String> {
    let dir = memory_block_dir_for_repo(repo_root, scope)?;
    let path = dir.join(format!("{}.md", label));
    let raw = fs::read_to_string(&path).unwrap_or_default();

    let mut description: Option<String> = None;
    let mut limit: usize = 2000;
    let mut read_only = false;
    let mut body = raw.clone();

    if raw.starts_with("---\n") {
        if let Some(end) = raw[4..].find("\n---\n") {
            let fm = &raw[4..4 + end];
            body = raw[4 + end + "\n---\n".len()..].to_string();
            for line in fm.lines() {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                let Some((k, v)) = line.split_once(':') else {
                    continue;
                };
                let key = k.trim();
                let val = v.trim().trim_matches('"');
                match key {
                    "description" => {
                        if !val.is_empty() {
                            description = Some(val.to_string());
                        }
                    }
                    "limit" => {
                        if let Ok(n) = val.parse::<usize>() {
                            if n >= 200 && n <= 50_000 {
                                limit = n;
                            }
                        }
                    }
                    "read_only" => {
                        read_only = val == "true" || val == "1";
                    }
                    _ => {}
                }
            }
        }
    }

    Ok(MemoryBlock {
        label: label.to_string(),
        scope: scope.to_string(),
        description,
        limit,
        read_only,
        content: body,
        updated_at: utc_now_iso(),
    })
}

pub(crate) fn write_memory_block_to_file(
    repo_root: &str,
    block: &MemoryBlock,
) -> Result<(), String> {
    let dir = memory_block_dir_for_repo(repo_root, &block.scope)?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(format!("{}.md", block.label));

    let description = block.description.clone().unwrap_or_default();
    let mut fm = String::new();
    fm.push_str("---\n");
    fm.push_str(&format!("label: {}\n", block.label));
    if !description.trim().is_empty() {
        fm.push_str(&format!("description: {}\n", description.trim()));
    }
    fm.push_str(&format!("limit: {}\n", block.limit));
    fm.push_str(&format!(
        "read_only: {}\n",
        if block.read_only { "true" } else { "false" }
    ));
    fm.push_str("---\n");
    let raw = format!("{}{}", fm, block.content);
    fs::write(&path, raw).map_err(|e| format!("write memory failed: {}", e))
}

pub(crate) fn read_all_memory_blocks(repo_root: &str) -> Result<Vec<MemoryBlock>, String> {
    ensure_seed_memory_blocks(repo_root)?;
    let mut out: Vec<MemoryBlock> = Vec::new();
    for scope in ["global", "project"] {
        let dir = memory_block_dir_for_repo(repo_root, scope)?;
        if !dir.exists() {
            continue;
        }
        let read_dir = fs::read_dir(&dir).map_err(|e| format!("read memory dir failed: {}", e))?;
        for entry in read_dir.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let Some(ext) = path.extension().and_then(|x| x.to_str()) else {
                continue;
            };
            if ext != "md" {
                continue;
            }
            let Some(stem) = path.file_stem().and_then(|x| x.to_str()) else {
                continue;
            };
            if !is_safe_memory_label(stem) {
                continue;
            }
            if let Ok(block) = read_memory_block_from_file(repo_root, scope, stem) {
                out.push(block);
            }
        }
    }
    out.sort_by(|a, b| a.scope.cmp(&b.scope).then(a.label.cmp(&b.label)));
    Ok(out)
}

pub(crate) fn memory_blocks_to_prompt(blocks: &[MemoryBlock]) -> String {
    let mut out = String::new();
    out.push_str("[Memory Blocks]\n");
    for b in blocks {
        let title = format!("{}:{}", b.scope, b.label);
        let desc = b.description.clone().unwrap_or_default();
        out.push_str(&format!(
            "- {}{}\n",
            title,
            if desc.is_empty() {
                "".into()
            } else {
                format!(" ({})", desc)
            }
        ));
        if !b.content.trim().is_empty() {
            let clipped = if b.content.chars().count() > 4000 {
                let mut s = b.content.chars().take(4000).collect::<String>();
                s.push_str("\n... [truncated]");
                s
            } else {
                b.content.clone()
            };
            out.push_str(&format!("\n{}\n\n", clipped.trim()));
        }
    }
    out
}

pub(crate) fn memory_set_inner(
    repo_root: &str,
    scope: &str,
    label: &str,
    content: &str,
    description: Option<String>,
) -> Result<MemoryBlock, String> {
    let scope = normalize_memory_scope(scope).ok_or_else(|| "invalid scope".to_string())?;
    let label = label.trim().to_string();
    if !is_safe_memory_label(&label) {
        return Err("invalid label".into());
    }
    if content.chars().count() > 120_000 {
        return Err("memory content too large".into());
    }

    let mut block = read_memory_block_from_file(repo_root, &scope, &label).unwrap_or(MemoryBlock {
        label: label.clone(),
        scope: scope.clone(),
        description: None,
        limit: 2000,
        read_only: false,
        content: "".into(),
        updated_at: utc_now_iso(),
    });

    if block.read_only {
        return Err("memory block is read-only".into());
    }
    block.description = description.or(block.description);
    let trimmed = if content.chars().count() > block.limit {
        content.chars().take(block.limit).collect::<String>()
    } else {
        content.to_string()
    };
    block.content = trimmed;
    block.updated_at = utc_now_iso();
    write_memory_block_to_file(repo_root, &block)?;
    Ok(block)
}
