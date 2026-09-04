---
name: git-worktree-isolation
description: Enforces Git worktree isolation for concurrent AI agents, preventing index.lock collisions and split-brain states across multiple IDEs.
license: Complete terms in LICENSE.txt
---

# Git Worktree Agent Isolation

## Overview
This skill enforces **Rule R40: Split-Brain Workspace Isolation**. When invoking autonomous agents (like Claude Code or Gemini subagents) that write code to the repository, they MUST NOT operate in the primary D:\GOOGLE ANTIGRAVITY directory simultaneously. Instead, they must be isolated into temporary Git worktrees.

## The Mechanism
A Git worktree allows multiple branches of the same repository to be checked out simultaneously in different directories, sharing the same .git database but maintaining completely independent working trees and indices.

## Execution Pattern (The "Sandboxed Agent")

1. **Create the Worktree**
   From the main repo root, run:
   `ash
   git worktree add ../.worktrees/feat-<name> -b feat/<name>
   `

2. **Dispatch the Agent**
   Change into the isolated worktree before triggering the coding agent:
   `ash
   cd ../.worktrees/feat-<name>
   claude -p "Implement the feature..."
   `

3. **Stage, Commit, and Teardown**
   Once the agent finishes, commit the isolated changes:
   `ash
   git add .
   git commit -m "feat: complete agent sub-task"
   git push origin feat/<name>
   cd ../../GOOGLE\ ANTIGRAVITY
   git worktree remove ../.worktrees/feat-<name>
   `

## Why This Matters (Empirically Verified)
Our deterministic Pytest (	ests/test_git_worktree_isolation.py) successfully proved that modifying files inside a worktree does not dirty the index of the primary worktree. This structurally guarantees that index.lock collisions are impossible, and git reset --hard in one tree will not nuke the other tree's state.

