---
name: git-workflow
description: Git commit, branch, and PR best practices
tags: [git, version-control, workflow]
auto_load: false
---

# Git Workflow Best Practices

## Commit Messages

### Format
```
<type>: <subject>

<body>

<footer>
```

### Type
- **feat**: New feature
- **fix**: Bug fix
- **refactor**: Code refactoring (no functional changes)
- **docs**: Documentation changes
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, build config)

### Rules
- Use imperative mood: "Add feature" not "Added feature"
- First line: 50 characters max
- Body: wrap at 72 characters
- Separate subject from body with blank line
- Explain **why**, not what (code shows what)

### Examples
```
feat: Add user authentication with JWT

Implement JWT-based authentication to replace session cookies.
This improves scalability and enables stateless API design.

Closes #123
```

```
fix: Prevent race condition in cache invalidation

Add mutex lock around cache write operations to prevent
concurrent updates from corrupting the cache state.
```

## Branch Naming

### Convention
```
<type>/<short-description>
```

### Types
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/updates

### Examples
- `feature/user-authentication`
- `fix/memory-leak-in-parser`
- `refactor/extract-validation-logic`

## Pull Request Workflow

### Before Creating PR
1. Rebase on latest main: `git rebase origin/main`
2. Run tests locally
3. Review your own changes first
4. Write clear PR description

### PR Description Template
```markdown
## What
Brief description of changes

## Why
Motivation and context

## How
Technical approach (if non-obvious)

## Testing
How to test these changes

## Screenshots (if UI changes)
```

### PR Size
- Keep PRs small (< 400 lines changed)
- One logical change per PR
- Split large features into multiple PRs

## Merge Strategies

### Merge Commit (default)
- Preserves full history
- Use for feature branches

### Squash and Merge
- Combines all commits into one
- Use for small fixes or cleanup branches
- Keeps main branch history clean

### Rebase and Merge
- Linear history
- Use when commits are already clean
- Avoid if branch has been shared

## Common Mistakes to Avoid

1. **Committing secrets** - Use .gitignore, never commit API keys
2. **Large binary files** - Use Git LFS for large assets
3. **Mixing concerns** - One commit = one logical change
4. **Force pushing shared branches** - Only force push your own branches
5. **Skipping tests** - Always run tests before pushing

## Useful Commands

```bash
# Interactive rebase to clean up commits
git rebase -i HEAD~3

# Amend last commit (if not pushed)
git commit --amend

# Stash changes temporarily
git stash
git stash pop

# Cherry-pick specific commit
git cherry-pick <commit-hash>

# View commit history
git log --oneline --graph --all
```
