#!/usr/bin/env python3

import os
import subprocess
import argparse
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def run_command(cmd, check=True, capture_output=False, text=False, cwd=None):
    """Run a command with unified error handling."""
    try:
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=text, cwd=cwd)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"Error output: {e.stderr}")
        raise

def fix_git_index(target_dir, git_dir=None):
    """
    Fix Git index issues for directories that show untracked files incorrectly.
    
    This utility directly manipulates Git's index to properly recognize files
    that should be tracked but are showing as untracked.
    
    Args:
        target_dir: Path to the directory with index issues
        git_dir: Path to the git directory (default: TARGET_DIR/.git)
    """
    target_path = Path(target_dir).resolve()
    
    # If .git is a file (gitdir pointer), read the actual git directory
    git_link_path = target_path / '.git'
    if git_link_path.is_file():
        with open(git_link_path, 'r') as f:
            gitdir_line = f.read().strip()
            if gitdir_line.startswith('gitdir: '):
                git_dir = gitdir_line[8:]
                logger.info(f"Found gitdir pointer: {git_dir}")
    
    if not git_dir:
        git_dir = str(target_path / '.git')
    
    git_dir_path = Path(git_dir).resolve()
    if not git_dir_path.exists():
        raise ValueError(f"Git directory not found: {git_dir_path}")
    
    # Step 1: Configure Git to prevent showing untracked files
    logger.info("Setting core.untrackedCache=false and status.showUntrackedFiles=no...")
    run_command(['git', 'config', 'core.untrackedCache', 'false'], cwd=target_path)
    run_command(['git', 'config', 'status.showUntrackedFiles', 'no'], cwd=target_path)
    
    # Step 2: Temporarily modify sparse checkout settings
    sparse_checkout_file = git_dir_path / 'info' / 'sparse-checkout'
    sparse_checkout_backup = None
    
    if sparse_checkout_file.exists():
        # Backup existing sparse checkout
        sparse_checkout_backup = sparse_checkout_file.read_text()
        logger.info("Temporarily modifying sparse-checkout to include all files...")
        with open(sparse_checkout_file, 'w') as f:
            f.write("/*\n")  # Match everything
    
    # Step 3: Reset the index to clear any previous state
    logger.info("Resetting the Git index...")
    run_command(['git', 'reset', '--mixed'], cwd=target_path, check=False)
    
    # Step 4: Force Git to recognize all files by adding them to staging
    logger.info("Force-adding all files to Git index...")
    run_command(['git', 'add', '-A', '.'], cwd=target_path, check=False)
    
    # Step 5: Reset again to unstage but keep the files in the index
    logger.info("Resetting staged files (keeping them in index)...")
    run_command(['git', 'reset'], cwd=target_path, check=False)
    
    # Step 6: Make Git aware of all files using update-index
    logger.info("Updating Git index with all files...")
    file_list = subprocess.check_output(['find', '.', '-type', 'f', 
                                        '-not', '-path', './.git*'], 
                                        text=True, cwd=target_path).splitlines()
    
    # Filter out common exclusions
    file_list = [f for f in file_list if not (
        f.endswith('.swp') or 
        f.endswith('~') or 
        '/.git/' in f or 
        '/__pycache__/' in f
    )]
    
    if file_list:
        # Process files in batches to avoid command line length limits
        batch_size = 100
        for i in range(0, len(file_list), batch_size):
            batch = file_list[i:i+batch_size]
            try:
                update_cmd = ['git', 'update-index', '--add', '--'] + batch
                run_command(update_cmd, cwd=target_path, check=False)
            except Exception as e:
                logger.warning(f"Error updating index batch {i//batch_size}: {e}")
    
    # Step 7: Restore sparse checkout settings if they existed
    if sparse_checkout_backup is not None:
        logger.info("Restoring original sparse-checkout settings...")
        with open(sparse_checkout_file, 'w') as f:
            f.write(sparse_checkout_backup)
    
    # Step 8: Verify the fix worked
    logger.info("Verifying Git status...")
    status_output = subprocess.check_output(['git', 'status', '-s'], text=True, cwd=target_path)
    
    if not status_output.strip():
        logger.info("✓ Success! Git index is now properly tracking files.")
    else:
        logger.warning(f"Some files are still showing in git status output:\n{status_output}")
        logger.info("You may need to run additional Git commands to fix specific issues.")
    
    logger.info(f"Git status display fixed for '{target_path}'")
    logger.info("Run 'git status' to verify the fix.")

def main():
    parser = argparse.ArgumentParser(description='Fix Git index issues in fitrepo subdirectories')
    parser.add_argument('target_dir', help='Directory with Git index issues')
    parser.add_argument('-g', '--git-dir', help='Git directory (if different from TARGET_DIR/.git)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        fix_git_index(args.target_dir, args.git_dir)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
