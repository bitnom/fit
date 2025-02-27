#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
import logging

# Set up logging for user feedback
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Constants
FOSSIL_REPO = 'monorepo.fossil'
CONFIG_FILE = 'fit.json'
GIT_CLONES_DIR = '.git_clones'
MARKS_DIR = '.marks'

# Ensure directories exist
Path(GIT_CLONES_DIR).mkdir(exist_ok=True)
Path(MARKS_DIR).mkdir(exist_ok=True)

# Configuration handling
def load_config():
    """Load the configuration file, returning an empty dict if it doesn't exist."""
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Save the configuration to the config file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Context manager for changing directories
@contextmanager
def cd(path):
    """Temporarily change the current working directory, restoring it afterward."""
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)

# Initialize Fossil repository
def init_fossil_repo():
    """Initialize the Fossil repository and configuration file if they don't exist."""
    try:
        if not Path(FOSSIL_REPO).exists():
            logger.info(f"Initializing Fossil repository at {FOSSIL_REPO}...")
            subprocess.run(['fossil', 'init', FOSSIL_REPO], check=True)
        if not Path(CONFIG_FILE).exists():
            logger.info(f"Creating configuration file {CONFIG_FILE}...")
            save_config({})
        logger.info("Initialization complete.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during initialization: {e}")
        raise

# Import a Git repository
def import_git_repo(git_repo_url, subdir_name):
    """Import a Git repository into the Fossil repository under a subdirectory."""
    config = load_config()
    if subdir_name in config:
        logger.error(f"Subdirectory '{subdir_name}' is already imported.")
        raise ValueError(f"Subdirectory '{subdir_name}' is already imported.")
    
    original_cwd = Path.cwd()
    git_clone_path = original_cwd / GIT_CLONES_DIR / subdir_name
    git_clone_path.mkdir(exist_ok=True)
    
    try:
        # Clone the Git repository
        logger.info(f"Cloning Git repository from {git_repo_url}...")
        subprocess.run(['git', 'clone', git_repo_url, str(git_clone_path)], check=True)
        
        with cd(git_clone_path):
            # Apply git filter-repo to move files and rename branches
            logger.info(f"Moving files to subdirectory '{subdir_name}' and renaming branches...")
            refname_rewriter = f"return 'refs/heads/{subdir_name}/' + refname[11:] if refname.startswith('refs/heads/') else refname"
            subprocess.run(
                ['git', 'filter-repo', '--to-subdirectory-filter', subdir_name, '--refname-rewriter', refname_rewriter],
                check=True
            )
            
            # Define marks file paths
            git_marks_file = original_cwd / MARKS_DIR / f"{subdir_name}_git.marks"
            fossil_marks_file = original_cwd / MARKS_DIR / f"{subdir_name}_fossil.marks"
            
            # Export from Git and import into Fossil
            logger.info("Exporting Git history and importing into Fossil repository...")
            git_export = subprocess.Popen(
                ['git', 'fast-export', '--all', '--export-marks', str(git_marks_file)],
                stdout=subprocess.PIPE
            )
            fossil_import = subprocess.Popen(
                ['fossil', 'import', '--git', '--incremental', '--export-marks', str(fossil_marks_file), str(original_cwd / FOSSIL_REPO)],
                stdin=git_export.stdout
            )
            git_export.stdout.close()
            fossil_import.communicate()
            if fossil_import.returncode != 0:
                raise subprocess.CalledProcessError(fossil_import.returncode, 'fossil import')
        
        # Update configuration
        config[subdir_name] = {
            'git_repo_url': git_repo_url,
            'git_clone_path': str(git_clone_path),
            'git_marks_file': str(git_marks_file),
            'fossil_marks_file': str(fossil_marks_file)
        }
        save_config(config)
        logger.info(f"Successfully imported '{git_repo_url}' into subdirectory '{subdir_name}'.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during import: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

# Update a Git repository
def update_git_repo(subdir_name):
    """Update the Fossil repository with new changes from a Git repository."""
    config = load_config()
    if subdir_name not in config:
        logger.error(f"Subdirectory '{subdir_name}' not found in configuration.")
        raise ValueError(f"Subdirectory '{subdir_name}' not found in configuration.")
    
    original_cwd = Path.cwd()
    git_clone_path = Path(config[subdir_name]['git_clone_path'])
    git_marks_file = Path(config[subdir_name]['git_marks_file'])
    fossil_marks_file = Path(config[subdir_name]['fossil_marks_file'])
    
    try:
        with cd(git_clone_path):
            # Pull latest changes
            logger.info(f"Pulling latest changes for '{subdir_name}'...")
            subprocess.run(['git', 'pull'], check=True)
            
            # Reapply git filter-repo
            logger.info(f"Reapplying filters for '{subdir_name}'...")
            refname_rewriter = f"return 'refs/heads/{subdir_name}/' + refname[11:] if refname.startswith('refs/heads/') else refname"
            subprocess.run(
                ['git', 'filter-repo', '--to-subdirectory-filter', subdir_name, '--refname-rewriter', refname_rewriter, '--force'],
                check=True
            )
            
            # Export and import new changes
            logger.info("Exporting new changes and updating Fossil repository...")
            git_export = subprocess.Popen(
                ['git', 'fast-export', '--import-marks', str(git_marks_file), '--export-marks', str(git_marks_file), '--all'],
                stdout=subprocess.PIPE
            )
            fossil_import = subprocess.Popen(
                ['fossil', 'import', '--git', '--incremental', '--import-marks', str(fossil_marks_file), '--export-marks', str(fossil_marks_file), str(original_cwd / FOSSIL_REPO)],
                stdin=git_export.stdout
            )
            git_export.stdout.close()
            fossil_import.communicate()
            if fossil_import.returncode != 0:
                raise subprocess.CalledProcessError(fossil_import.returncode, 'fossil import')
        
        logger.info(f"Successfully updated '{subdir_name}' in the Fossil repository.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during update: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

# Main function with command-line interface
def main():
    """Parse command-line arguments and execute the appropriate command."""
    parser = argparse.ArgumentParser(description='Fossil Import Tool (fit.py) - Manage Git repositories in a Fossil repository.')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # Init command
    subparsers.add_parser('init', help='Initialize the Fossil repository and configuration')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import a Git repository into the Fossil repository')
    import_parser.add_argument('git_repo_url', help='URL of the Git repository to import')
    import_parser.add_argument('subdir_name', help='Subdirectory name under which to import this repository')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update the Fossil repository with new changes from a Git repository')
    update_parser.add_argument('subdir_name', help='Subdirectory name of the repository to update')

    args = parser.parse_args()

    try:
        if args.command == 'init':
            init_fossil_repo()
        elif args.command == 'import':
            import_git_repo(args.git_repo_url, args.subdir_name)
        elif args.command == 'update':
            update_git_repo(args.subdir_name)
    except (ValueError, subprocess.CalledProcessError, Exception) as e:
        logger.error(f"Command failed: {e}")
        exit(1)

if __name__ == '__main__':
    main()
