#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
import logging
import shutil

# Set up logging for user feedback
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Default constants
FOSSIL_REPO = 'monorepo.fossil'
CONFIG_FILE = 'fitrepo.json'
GIT_CLONES_DIR = '.git_clones'
MARKS_DIR = '.marks'

# Ensure directories exist
def ensure_directories(git_clones_dir=GIT_CLONES_DIR, marks_dir=MARKS_DIR):
    """Ensure required directories exist."""
    Path(git_clones_dir).mkdir(exist_ok=True)
    Path(marks_dir).mkdir(exist_ok=True)

# Check dependencies
def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        # Check git
        subprocess.run(['git', '--version'], check=True, stdout=subprocess.PIPE)
        
        # Check git-filter-repo
        try:
            subprocess.run(['git-filter-repo', '--version'], check=True, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logger.error("git-filter-repo is not installed. Install it with: pip install git-filter-repo")
            return False
        except FileNotFoundError:
            logger.error("git-filter-repo is not found in PATH. Install it with: pip install git-filter-repo")
            return False
        
        # Check fossil
        subprocess.run(['fossil', 'version'], check=True, stdout=subprocess.PIPE)
        
        return True
    except subprocess.CalledProcessError:
        logger.error("Missing required dependencies. Please ensure git and fossil are installed.")
        return False
    except FileNotFoundError as e:
        logger.error(f"Missing required dependency: {e}")
        return False

# Context manager for changing directory
@contextmanager
def cd(path):
    """Context manager to change directory and return to original directory."""
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

# Configuration handling
def load_config(config_file=CONFIG_FILE):
    """Load the configuration file, returning an empty dict if it doesn't exist."""
    if not Path(config_file).exists():
        return {}
    with open(config_file, 'r') as f:
        return json.load(f)

def save_config(config, config_file=CONFIG_FILE):
    """Save the configuration to the config file."""
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)

def init_fossil_repo(fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE):
    """Initialize the Fossil repository and configuration file."""
    try:
        if not Path(fossil_repo).exists():
            logger.info(f"Creating Fossil repository {fossil_repo}...")
            subprocess.run(['fossil', 'init', fossil_repo], check=True)
        if not Path(config_file).exists():
            logger.info(f"Creating configuration file {config_file}...")
            save_config({}, config_file)
        logger.info("Initialization complete.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during initialization: {e}")
        raise

# Validate inputs
def validate_git_url(url):
    """Validate that the input looks like a git repository URL."""
    # Basic validation - could be enhanced for more specific rules
    if not url or not (url.startswith('http') or url.startswith('git') or url.startswith('ssh')):
        logger.error(f"Invalid Git URL format: {url}")
        return False
    return True

def validate_subdir_name(name):
    """Validate that the subdirectory name is valid."""
    if not name or '/' in name or name.startswith('.'):
        logger.error(f"Invalid subdirectory name: {name}. Must not contain '/' or start with '.'")
        return False
    return True

# Import a Git repository
def import_git_repo(git_repo_url, subdir_name, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, 
                    git_clones_dir=GIT_CLONES_DIR, marks_dir=MARKS_DIR):
    """Import a Git repository into the Fossil repository under a subdirectory."""
    if not validate_git_url(git_repo_url) or not validate_subdir_name(subdir_name):
        raise ValueError("Invalid input parameters")
    
    config = load_config(config_file)
    if subdir_name in config:
        logger.error(f"Subdirectory '{subdir_name}' is already imported.")
        raise ValueError(f"Subdirectory '{subdir_name}' is already imported.")
    
    original_cwd = Path.cwd()
    git_clone_path = original_cwd / git_clones_dir / subdir_name
    git_clone_path.mkdir(exist_ok=True)
    
    try:
        # Clone the Git repository
        logger.info(f"Cloning Git repository from {git_repo_url}...")
        subprocess.run(['git', 'clone', '--no-local', git_repo_url, str(git_clone_path)], check=True)
        
        with cd(git_clone_path):
            # Apply git-filter-repo to move files and rename branches
            logger.info(f"Moving files to subdirectory '{subdir_name}' and renaming branches...")
            refname_rewriter = f"return 'refs/heads/{subdir_name}/' + refname[11:] if refname.startswith('refs/heads/') else refname"
            subprocess.run(
                ['git-filter-repo', '--to-subdirectory-filter', subdir_name, '--refname-rewriter', refname_rewriter],
                check=True
            )
            
            # Define marks file paths
            git_marks_file = original_cwd / marks_dir / f"{subdir_name}_git.marks"
            fossil_marks_file = original_cwd / marks_dir / f"{subdir_name}_fossil.marks"
            
            # Export from Git and import into Fossil
            logger.info("Exporting Git history and importing into Fossil repository...")
            git_export = subprocess.Popen(
                ['git', 'fast-export', '--all', '--export-marks', str(git_marks_file)],
                stdout=subprocess.PIPE
            )
            fossil_import = subprocess.Popen(
                ['fossil', 'import', '--git', '--incremental', '--export-marks', str(fossil_marks_file), str(original_cwd / fossil_repo)],
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
        save_config(config, config_file)
        logger.info(f"Successfully imported '{git_repo_url}' into subdirectory '{subdir_name}'.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during import: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

# Update a Git repository
def update_git_repo(subdir_name, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE):
    """Update the Fossil repository with new changes from a Git repository."""
    config = load_config(config_file)
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
            
            # Reapply git-filter-repo
            logger.info(f"Reapplying filters for '{subdir_name}'...")
            refname_rewriter = f"return 'refs/heads/{subdir_name}/' + refname[11:] if refname.startswith('refs/heads/') else refname"
            subprocess.run(
                ['git-filter-repo', '--to-subdirectory-filter', subdir_name, '--refname-rewriter', refname_rewriter, '--force'],
                check=True
            )
            
            # Export and import new changes
            logger.info("Exporting new changes and updating Fossil repository...")
            git_export = subprocess.Popen(
                ['git', 'fast-export', '--import-marks', str(git_marks_file), '--export-marks', str(git_marks_file), '--all'],
                stdout=subprocess.PIPE
            )
            fossil_import = subprocess.Popen(
                ['fossil', 'import', '--git', '--incremental', '--import-marks', str(fossil_marks_file), '--export-marks', str(fossil_marks_file), str(original_cwd / fossil_repo)],
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

# List imported repositories
def list_repos(config_file=CONFIG_FILE):
    """List all imported repositories and their details."""
    config = load_config(config_file)
    if not config:
        logger.info("No repositories have been imported.")
        return
    
    logger.info("Imported repositories:")
    for subdir, details in config.items():
        logger.info(f"- {subdir}: {details['git_repo_url']}")
        if logger.level == logging.DEBUG:  # More details when in debug mode
            logger.debug(f"  Clone path: {details['git_clone_path']}")
            logger.debug(f"  Git marks: {details['git_marks_file']}")
            logger.debug(f"  Fossil marks: {details['fossil_marks_file']}")

# Main function with command-line interface
def main():
    """Parse command-line arguments and execute the appropriate command."""
    parser = argparse.ArgumentParser(description='Fossil Import Tool (fitrepo.py) - Manage Git repositories in a Fossil repository.')
    
    # Global options
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-f', '--fossil-repo', default=FOSSIL_REPO, help=f'Fossil repository file (default: {FOSSIL_REPO})')
    parser.add_argument('-c', '--config', default=CONFIG_FILE, help=f'Configuration file (default: {CONFIG_FILE})')
    parser.add_argument('-g', '--git-clones-dir', default=GIT_CLONES_DIR, help=f'Git clones directory (default: {GIT_CLONES_DIR})')
    parser.add_argument('-m', '--marks-dir', default=MARKS_DIR, help=f'Marks directory (default: {MARKS_DIR})')
    
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

    # List command
    subparsers.add_parser('list', help='List all imported repositories')

    args = parser.parse_args()

    # Set debug level if verbose flag is enabled
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Ensure directories exist based on potentially overridden values
    ensure_directories(args.git_clones_dir, args.marks_dir)

    try:
        if args.command == 'init':
            init_fossil_repo(args.fossil_repo, args.config)
        elif args.command == 'import':
            import_git_repo(args.git_repo_url, args.subdir_name, args.fossil_repo, args.config, args.git_clones_dir, args.marks_dir)
        elif args.command == 'update':
            update_git_repo(args.subdir_name, args.fossil_repo, args.config)
        elif args.command == 'list':
            list_repos(args.config)
    except (ValueError, subprocess.CalledProcessError) as e:
        logger.error(f"Command failed: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if args.verbose:
            logger.exception("Detailed error information:")
        exit(1)

if __name__ == '__main__':
    if not check_dependencies():
        logger.error("Missing required dependencies. Please install them before continuing.")
        logger.error("Make sure git, git-filter-repo, and fossil are installed.")
        logger.error("You can install git-filter-repo with: uv pip install git-filter-repo")
        exit(1)
    main()
