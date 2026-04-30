---
name: git-workflow
description: Git workflow automation - staging, committing, branching with best practices
tools: Bash, Glob
model: qwen2.5-coder:14b
---
# Git Workflow Skill

## Branches
- `main` / `master` - production
- `develop` - integration
- `feature/description` - new features
- `fix/issue-description` - bug fixes

## Workflow
```
git checkout -b feature/my-feature
# Make changes
git add -A
git commit -m "feat: add feature"
git push origin feature/my-feature
# Create PR
```

## Commits
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` non-functional change
- `test:` adding tests
- `chore:` maintenance

## Best Practices
- Small, focused commits
- Include issue references: "Fixes #123"