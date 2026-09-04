import os
import subprocess
import tempfile
import shutil
import pytest

def run_cmd(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)

def test_git_worktree_isolation():
    # Phase 2 Scientist Evaluation: Verify Git Worktree isolation for multi-agent workflows
    with tempfile.TemporaryDirectory() as base_dir:
        main_dir = os.path.join(base_dir, 'main_repo')
        wt_dir = os.path.join(base_dir, 'agent_worktree')
        os.makedirs(main_dir)
        
        # 1. Initialize main repo
        run_cmd('git init', cwd=main_dir)
        with open(os.path.join(main_dir, 'file.txt'), 'w') as f:
            f.write('initial')
        run_cmd('git add file.txt', cwd=main_dir)
        run_cmd('git commit -m "init"', cwd=main_dir)
        
        # 2. Add a worktree
        res = run_cmd(f'git worktree add {wt_dir} -b agent-feature', cwd=main_dir)
        assert res.returncode == 0, f"Worktree creation failed: {res.stderr}"
        
        # 3. Modify in main tree (Simulate Agent A)
        with open(os.path.join(main_dir, 'file.txt'), 'w') as f:
            f.write('agent A modified')
            
        # 4. Modify in worktree (Simulate Agent B)
        with open(os.path.join(wt_dir, 'file2.txt'), 'w') as f:
            f.write('agent B new file')
            
        # 5. Assert isolation
        # Main tree should see file.txt modified, but NOT file2.txt
        res_main = run_cmd('git status --short', cwd=main_dir)
        assert 'M file.txt' in res_main.stdout
        assert 'file2.txt' not in res_main.stdout
        
        # Worktree should see file2.txt untracked, but NOT file.txt modified
        res_wt = run_cmd('git status --short', cwd=wt_dir)
        assert '?? file2.txt' in res_wt.stdout
        assert 'M file.txt' not in res_wt.stdout

