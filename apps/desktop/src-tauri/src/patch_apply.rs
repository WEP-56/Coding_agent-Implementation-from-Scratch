use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum PatchHunk {
    AddFile {
        path: PathBuf,
        contents: String,
    },
    DeleteFile {
        path: PathBuf,
    },
    UpdateFile {
        path: PathBuf,
        move_path: Option<PathBuf>,
        chunks: Vec<UpdateFileChunk>,
    },
}

#[derive(Debug, Clone)]
pub struct UpdateFileChunk {
    pub change_context: Option<String>,
    pub old_lines: Vec<String>,
    pub new_lines: Vec<String>,
    pub is_end_of_file: bool,
}

#[derive(Debug, Clone)]
pub struct ApplyPatchArgs {
    pub hunks: Vec<PatchHunk>,
}

fn normalize_lines_for_patch(contents: &str) -> Vec<String> {
    let mut lines: Vec<String> = contents.split('\n').map(|s| s.to_string()).collect();
    if lines.last().is_some_and(String::is_empty) {
        // Drop trailing empty from final newline.
        lines.pop();
    }
    lines
}

fn join_lines_with_final_newline(mut lines: Vec<String>) -> String {
    if !lines.last().is_some_and(String::is_empty) {
        lines.push(String::new());
    }
    lines.join("\n")
}

fn trim_line(line: &str) -> &str {
    line.trim_matches(['\r', '\n'])
}

fn expect_patch_boundaries(lines: &[&str]) -> Result<(), String> {
    let first = lines.first().map(|l| trim_line(l).trim()).unwrap_or("");
    let last = lines.last().map(|l| trim_line(l).trim()).unwrap_or("");
    if first != "*** Begin Patch" {
        return Err("invalid patch: first line must be '*** Begin Patch'".into());
    }
    if last != "*** End Patch" {
        return Err("invalid patch: last line must be '*** End Patch'".into());
    }
    Ok(())
}

pub fn parse_apply_patch(patch_text: &str) -> Result<ApplyPatchArgs, String> {
    let raw_lines: Vec<&str> = patch_text.trim().lines().collect();
    if raw_lines.len() < 2 {
        return Err("invalid patch: too short".into());
    }
    expect_patch_boundaries(&raw_lines)?;
    let mut hunks: Vec<PatchHunk> = Vec::new();
    let mut i = 1usize;
    while i + 1 < raw_lines.len() {
        let line = raw_lines[i].trim();
        if line.is_empty() {
            i += 1;
            continue;
        }
        if let Some(path) = line.strip_prefix("*** Add File: ") {
            let path = PathBuf::from(path.trim());
            i += 1;
            let mut contents = String::new();
            while i + 1 < raw_lines.len() {
                let l = raw_lines[i];
                if l.trim_start().starts_with("*** ") {
                    break;
                }
                let Some(rest) = l.strip_prefix('+') else {
                    return Err("invalid add file hunk: all lines must start with '+'".into());
                };
                contents.push_str(rest);
                contents.push('\n');
                i += 1;
            }
            if contents.is_empty() {
                return Err("invalid add file hunk: empty contents".into());
            }
            hunks.push(PatchHunk::AddFile { path, contents });
            continue;
        }
        if let Some(path) = line.strip_prefix("*** Delete File: ") {
            let path = PathBuf::from(path.trim());
            hunks.push(PatchHunk::DeleteFile { path });
            i += 1;
            continue;
        }
        if let Some(path) = line.strip_prefix("*** Update File: ") {
            let path = PathBuf::from(path.trim());
            i += 1;
            let mut move_path: Option<PathBuf> = None;
            if i + 1 < raw_lines.len() {
                if let Some(dest) = raw_lines[i].trim().strip_prefix("*** Move to: ") {
                    move_path = Some(PathBuf::from(dest.trim()));
                    i += 1;
                }
            }

            let mut chunks: Vec<UpdateFileChunk> = Vec::new();
            while i + 1 < raw_lines.len() {
                let l = raw_lines[i];
                if l.trim().is_empty() {
                    i += 1;
                    continue;
                }
                if l.trim_start().starts_with("*** ") {
                    break;
                }
                // Parse a chunk: optional "@@ context" line, then +/-/space lines, optional "*** End of File".
                let mut change_context: Option<String> = None;
                if l.trim() == "@@" {
                    change_context = None;
                    i += 1;
                } else if let Some(ctx) = l.trim().strip_prefix("@@ ") {
                    change_context = Some(ctx.to_string());
                    i += 1;
                }

                let mut old_lines: Vec<String> = Vec::new();
                let mut new_lines: Vec<String> = Vec::new();
                let mut is_end_of_file = false;

                while i + 1 < raw_lines.len() {
                    let line = raw_lines[i];
                    let t = line.trim();
                    if t == "*** End of File" {
                        is_end_of_file = true;
                        i += 1;
                        break;
                    }
                    if t.starts_with("*** ") || t == "@@" || t.starts_with("@@ ") {
                        break;
                    }
                    let mut chars = line.chars();
                    let prefix = chars.next().unwrap_or(' ');
                    let rest: String = chars.collect();
                    match prefix {
                        ' ' => {
                            old_lines.push(rest.clone());
                            new_lines.push(rest);
                        }
                        '-' => {
                            old_lines.push(rest);
                        }
                        '+' => {
                            new_lines.push(rest);
                        }
                        _ => return Err("invalid update file chunk line prefix".into()),
                    }
                    i += 1;
                }
                if old_lines.is_empty() && new_lines.is_empty() {
                    return Err("invalid update file hunk: empty chunk".into());
                }
                chunks.push(UpdateFileChunk {
                    change_context,
                    old_lines,
                    new_lines,
                    is_end_of_file,
                });
            }
            if chunks.is_empty() {
                return Err("invalid update file hunk: no chunks".into());
            }
            hunks.push(PatchHunk::UpdateFile {
                path,
                move_path,
                chunks,
            });
            continue;
        }

        return Err(format!("invalid patch: unexpected line: {}", line));
    }

    if hunks.is_empty() {
        return Err("invalid patch: no hunks".into());
    }
    Ok(ApplyPatchArgs { hunks })
}

fn seek_sequence(
    haystack: &[String],
    needle: &[String],
    start: usize,
    must_be_eof: bool,
) -> Option<usize> {
    if needle.is_empty() {
        return Some(start.min(haystack.len()));
    }
    let max = haystack.len().saturating_sub(needle.len());
    let range = if must_be_eof {
        max..=max
    } else {
        start.min(max)..=max
    };
    for i in range {
        if haystack.get(i..i + needle.len()) == Some(needle) {
            return Some(i);
        }
    }
    None
}

fn compute_replacements(
    original_lines: &[String],
    chunks: &[UpdateFileChunk],
) -> Result<Vec<(usize, usize, Vec<String>)>, String> {
    let mut replacements: Vec<(usize, usize, Vec<String>)> = Vec::new();
    let mut line_index: usize = 0;
    for chunk in chunks {
        if let Some(ctx) = &chunk.change_context {
            if let Some(idx) =
                seek_sequence(original_lines, std::slice::from_ref(ctx), line_index, false)
            {
                line_index = idx + 1;
            } else {
                return Err(format!("failed to find context '{}'", ctx));
            }
        }

        if chunk.old_lines.is_empty() {
            // pure insertion
            let insertion = if original_lines.last().is_some_and(String::is_empty) {
                original_lines.len() - 1
            } else {
                original_lines.len()
            };
            replacements.push((insertion, 0, chunk.new_lines.clone()));
            continue;
        }

        let mut pattern: &[String] = &chunk.old_lines;
        let mut new_slice: &[String] = &chunk.new_lines;
        let mut found = seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file);
        if found.is_none() && pattern.last().is_some_and(String::is_empty) {
            pattern = &pattern[..pattern.len() - 1];
            if new_slice.last().is_some_and(String::is_empty) {
                new_slice = &new_slice[..new_slice.len() - 1];
            }
            found = seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file);
        }

        if let Some(start_idx) = found {
            replacements.push((start_idx, pattern.len(), new_slice.to_vec()));
            line_index = start_idx + pattern.len();
        } else {
            return Err("failed to find expected lines for replacement".into());
        }
    }
    replacements.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(replacements)
}

fn apply_replacements(
    mut lines: Vec<String>,
    replacements: &[(usize, usize, Vec<String>)],
) -> Vec<String> {
    for (start, old_len, new_lines) in replacements.iter().rev() {
        for _ in 0..*old_len {
            if *start < lines.len() {
                lines.remove(*start);
            }
        }
        for (offset, nl) in new_lines.iter().enumerate() {
            lines.insert(*start + offset, nl.clone());
        }
    }
    lines
}

pub fn apply_update_chunks(
    original_contents: &str,
    chunks: &[UpdateFileChunk],
) -> Result<String, String> {
    let original_lines = normalize_lines_for_patch(original_contents);
    let replacements = compute_replacements(&original_lines, chunks)?;
    let new_lines = apply_replacements(original_lines, &replacements);
    Ok(join_lines_with_final_newline(new_lines))
}

// NOTE: filesystem application is performed in the Tauri commands layer
// using repo sandbox rules (safe_join_repo_path / sensitive path checks).
