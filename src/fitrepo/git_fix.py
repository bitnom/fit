#!/usr/bin/env python3
"""
A specialized tool for fixing Git index issues in monorepo subdirectories
"""

import os
import sys
import subprocess
import argparse
import logging
from pathlib import Path

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

def find_git_dir(start_dir):
    """Find the actual Git directory from a working directory or .git file"""
    git_path = Path(start_dir) / '.git'
    
    if not git_path.exists():
        return None
    
    # If .git is a file (gitdir pointer), read the actual git directory
    if git_path.is_file():
        with open(git_path, 'r') as f:
            gitdir_line = f.read().strip()
            if gitdir_line.startswith('gitdir: '):
                return gitdir_line[8:]
    
    # Otherwise, it's already the git directory
    return str(git_path)

def fix_git_tracking_issues(target_dir):
    """
    Advanced fix for Git index issues, specifically targeting untracked files
    in monorepo subdirectories. This function will:
    
    1. Disable sparse checkout temporarily
    2. Force-add all files to the index
    3. Reset to unstage but keep them in the index
    4. Re-enable proper sparse checkout settings
    
    Args:
        target_dir: Directory to fix
    """
    target_path = Path(target_dir).resolve()
    git_dir = find_git_dir(target_path)
    
    if not git_dir:
        raise ValueError(f"No Git repository found in {target_path}")
    
    git_dir_path = Path(git_dir).resolve()
    
    # Step 1: Disable sparse checkout temporarily
    sparse_checkout_file = git_dir_path / 'info' / 'sparse-checkout'
    sparse_checkout_backup = None
    
    if sparse_checkout_file.exists():
        sparse_checkout_backup = sparse_checkout_file.read_text()
        logger.info("Temporarily disabling sparse checkout...")
        with open(sparse_checkout_file, 'w') as f:
            f.write("/*\n")  # Match everything
    
    # Step 2: Configure Git settings
    run_command(['git', 'config', 'core.sparseCheckout', 'false'], cwd=target_path)
    run_command(['git', 'config', 'advice.updateSparsePath', 'false'], cwd=target_path)
    
    # Step 3: Reset the index completely
    logger.info("Resetting Git index completely...")
    run_command(['git', 'reset', '--hard'], cwd=target_path)
    
    # Step 4: Force-recognize all files using update-index with specific handling for .gitignore
    logger.info("Registering all files individually with Git index...")
    
    # First handle .gitignore separately with multiple approaches to ensure it works
    gitignore_path = target_path / '.gitignore'
    if gitignore_path.exists():
        logger.info("Special handling for .gitignore file...")
        # Try multiple methods to force Git to track .gitignore
        run_command(['git', 'update-index', '--add', '.gitignore'], cwd=target_path, check=False)
        run_command(['git', 'add', '--force', '.gitignore'], cwd=target_path, check=False)
        
        # If .gitignore is still untracked, try a more aggressive approach
        status = run_command(['git', 'status', '-s', '.gitignore'], cwd=target_path, 
                          capture_output=True, text=True, check=False)
        if '?? .gitignore' in status.stdout:
            logger.info("Trying advanced .gitignore fix...")
            # Temporarily disable sparse checkout completely
            run_command(['git', 'config', 'core.sparseCheckout', 'false'], cwd=target_path)
            run_command(['git', 'add', '--force', '.gitignore'], cwd=target_path, check=False)
            run_command(['git', 'reset'], cwd=target_path)
            # Re-enable sparse checkout
            run_command(['git', 'config', 'core.sparseCheckout', 'true'], cwd=target_path)
    
    # Find all files and update the index in batches
    find_cmd = ['find', '.', '-type', 'f', 
                '-not', '-path', './.git*', 
                '-not', '-path', './*~',
                '-not', '-path', './*.swp']
    all_files = subprocess.check_output(find_cmd, text=True, cwd=target_path).splitlines()
    
    # Process in batches
    batch_size = 50
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i+batch_size]
        logger.debug(f"Processing batch {i//batch_size + 1}/{(len(all_files) + batch_size - 1)//batch_size}...")
        
        try:
            # Use git add with force to bypass any ignored files
            add_cmd = ['git', 'add', '--force', '--'] + batch
            run_command(add_cmd, cwd=target_path, check=False)
        except Exception as e:
            logger.warning(f"Error processing batch: {e}")
    
    # Step 5: Reset to keep files in index but unstaged
    logger.info("Finalizing index...")
    run_command(['git', 'reset'], cwd=target_path)
    
    # Step 6: Re-enable proper sparse checkout settings
    logger.info("Restoring sparse checkout configuration...")
    
    if sparse_checkout_backup:
        with open(sparse_checkout_file, 'w') as f:
            f.write(sparse_checkout_backup)
        
    run_command(['git', 'config', 'core.sparseCheckout', 'true'], cwd=target_path)
    
    # Step 7: Configure Git to hide untracked files
    logger.info("Configuring Git to hide untracked files...")
    run_command(['git', 'config', 'status.showUntrackedFiles', 'no'], cwd=target_path)
    
    # Step 8: Verify
    status_output = run_command(['git', 'status', '-s'], cwd=target_path, capture_output=True, text=True).stdout
    
    if not status_output.strip():
        logger.info("✓ Success! Git index is now properly tracking all files.")
    else:
        logger.info("Git status shows some files still have changes:")
        for line in status_output.splitlines():
            logger.info(f"  {line}")
    
    logger.info(f"Git index fixed for '{target_path}'")

def main():
    parser = argparse.ArgumentParser(description='Fix Git tracking issues in monorepo subdirectories')
    parser.add_argument('directory', nargs='?', default='.', help='Target directory (default: current directory)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        fix_git_tracking_issues(args.directory)
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
