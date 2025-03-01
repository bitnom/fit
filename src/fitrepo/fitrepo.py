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
import importlib.metadata
import re

# Get version using importlib.metadata
try:
    __version__ = importlib.metadata.version('fitrepo')
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.3.dev"  # Default version when not installed

# Set up logging for user feedback
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Default constants
FOSSIL_REPO = 'monorepo.fossil'
CONFIG_FILE = 'fitrepo.json'
GIT_CLONES_DIR = '.git_clones'
MARKS_DIR = '.marks'

# Helper functions for common operations
def run_command(cmd, check=True, capture_output=False, text=False):
    """Run a command and return its result, with unified error handling."""
    try:
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=text)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise

def ensure_directories(git_clones_dir=GIT_CLONES_DIR, marks_dir=MARKS_DIR):
    """Ensure required directories exist."""
    Path(git_clones_dir).mkdir(exist_ok=True)
    Path(marks_dir).mkdir(exist_ok=True)

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        # Check git and fossil
        run_command(['git', '--version'], capture_output=True)
        run_command(['fossil', 'version'], capture_output=True)
        
        # Check git-filter-repo
        try:
            run_command(['git-filter-repo', '--version'], capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("git-filter-repo is not installed. Install it with: pip install git-filter-repo")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Missing required dependency: {e}")
        return False

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
    return json.load(open(config_file, 'r')) if Path(config_file).exists() else {}

def save_config(config, config_file=CONFIG_FILE):
    """Save the configuration to the config file."""
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)

def is_fossil_repo_open():
    """Check if we are already in a Fossil checkout."""
    try:
        return run_command(['fossil', 'status'], check=False).returncode == 0
    except:
        return False

def init_fossil_repo(fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE):
    """Initialize the Fossil repository and configuration file."""
    try:
        # Create and/or open repository as needed
        if not Path(fossil_repo).exists():
            logger.info(f"Creating Fossil repository {fossil_repo}...")
            run_command(['fossil', 'init', fossil_repo])
            if not is_fossil_repo_open():
                logger.info(f"Opening Fossil repository {fossil_repo}...")
                run_command(['fossil', 'open', fossil_repo])
        elif not is_fossil_repo_open():
            logger.info(f"Opening existing Fossil repository {fossil_repo}...")
            run_command(['fossil', 'open', fossil_repo])
        else:
            logger.info(f"Fossil repository is already open.")
            
        if not Path(config_file).exists():
            logger.info(f"Creating configuration file {config_file}...")
            # Get the directory name of the current working directory
            dir_name = Path.cwd().name
            # Save the configuration with the name parameter and empty repositories
            save_config({'name': dir_name, 'repositories': {}}, config_file)
        logger.info("Initialization complete.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during initialization: {e}")
        raise

# Validate inputs
def validate_git_url(url):
    """Validate that the input looks like a git repository URL or local path."""
    if not url:
        logger.error("Git URL or path cannot be empty")
        return False
    
    # Accept URLs or existing paths
    if url.startswith(('http', 'git', 'ssh')):
        return True
    
    path = Path(url)
    if path.exists() and (path / '.git').exists():
        return True
    elif path.exists():
        logger.warning(f"Path exists but may not be a Git repository: {url}")
        return True
    
    logger.error(f"Path does not exist: {url}")
    return False

def normalize_path(path_str):
    """
    Normalize a path for use as a subdirectory.
    Removes leading/trailing slashes and normalizes internal separators.
    """
    # Convert to Path object and back to string for normalization
    path = Path(path_str)
    # Convert back to string with forward slashes
    normalized = str(path).replace('\\', '/')
    # Remove leading and trailing slashes
    normalized = normalized.strip('/')
    return normalized

def path_to_branch_prefix(path_str):
    """
    Convert a normalized path to a branch prefix suitable for fossil.
    Replaces path separators with a safe character for branch naming.
    """
    # Replace slashes with double underscores to ensure uniqueness
    return normalize_path(path_str).replace('/', '__')

def branch_prefix_to_path(prefix):
    """Convert a branch prefix back to its path representation."""
    return prefix.replace('__', '/')

def validate_subdir_name(name):
    """
    Validate that the subdirectory path is valid.
    Allows internal slashes for proper subdirectory paths,
    but rejects leading/trailing slashes and other invalid patterns.
    """
    if not name:
        logger.error("Subdirectory name cannot be empty")
        return False
        
    # Check for leading/trailing slashes
    if name.startswith('/') or name.endswith('/'):
        logger.error(f"Invalid subdirectory path: {name}. Must not start or end with '/'")
        return False
        
    # Check for invalid patterns
    if any(part.startswith('.') for part in name.split('/')):
        logger.error(f"Invalid subdirectory path: {name}. Path components must not start with '.'")
        return False
        
    # Check for invalid characters beyond slashes
    if re.search(r'[<>:"|?*\x00-\x1F]', name):
        logger.error(f"Invalid characters in subdirectory path: {name}")
        return False
        
    return True

# Common operations used by both import and update
def process_git_repo(git_clone_path, subdir_path, force=False):
    """Apply subdirectory filter and rename branches with prefix."""
    # Normalize the subdirectory path
    norm_subdir = normalize_path(subdir_path)
    branch_prefix = path_to_branch_prefix(norm_subdir)
    
    # Apply git-filter-repo to move files to a subdirectory
    logger.info(f"Moving files to subdirectory '{norm_subdir}'...")
    filter_cmd = ['git-filter-repo', '--to-subdirectory-filter', norm_subdir]
    if force:
        filter_cmd.append('--force')
    run_command(filter_cmd)
    
    # Rename branches with subdirectory prefix
    logger.info(f"Renaming branches with prefix '{branch_prefix}/'...")
    result = run_command(['git', 'branch'], capture_output=True, text=True)
    branches = [b.strip()[2:] if b.strip().startswith('* ') else b.strip() 
               for b in result.stdout.split('\n') if b.strip()]
    
    # Rename each branch that doesn't already have the prefix
    for branch in branches:
        if branch and not branch.startswith(f"{branch_prefix}/"):
            run_command(['git', 'branch', '-m', branch, f"{branch_prefix}/{branch}"])

def export_import_git_to_fossil(subdir_path, git_marks_file, fossil_marks_file, fossil_repo, import_marks=False):
    """Export from Git and import into Fossil with appropriate marks files."""
    logger.info(f"{'Updating' if import_marks else 'Exporting'} Git history to Fossil...")
    
    # Prepare git and fossil commands
    git_cmd = ['git', 'fast-export', '--all']
    fossil_cmd = ['fossil', 'import', '--git', '--incremental']
    
    # Add marks files if they exist and import_marks is True
    if import_marks and Path(git_marks_file).exists():
        git_cmd.extend(['--import-marks', str(git_marks_file)])
    git_cmd.extend(['--export-marks', str(git_marks_file)])
    
    if import_marks and Path(fossil_marks_file).exists():
        fossil_cmd.extend(['--import-marks', str(fossil_marks_file)])
    fossil_cmd.extend(['--export-marks', str(fossil_marks_file), str(fossil_repo)])
    
    # Execute the pipeline
    git_export = subprocess.Popen(git_cmd, stdout=subprocess.PIPE)
    fossil_import = subprocess.Popen(fossil_cmd, stdin=git_export.stdout)
    git_export.stdout.close()
    fossil_import.communicate()
    
    if fossil_import.returncode != 0:
        raise subprocess.CalledProcessError(fossil_import.returncode, 'fossil import')

def update_fossil_checkout(subdir_path):
    """Update the fossil checkout to a branch with the given subdirectory prefix."""
    # Convert path to branch prefix
    branch_prefix = path_to_branch_prefix(normalize_path(subdir_path))
    
    logger.info("Checking available branches...")
    result = run_command(['fossil', 'branch', 'list'], capture_output=True, text=True)
    
    # Find first branch with the expected prefix and update to it
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(f"{branch_prefix}/"):
            logger.info(f"Updating checkout to branch '{line}'...")
            run_command(['fossil', 'update', line])
            return
            
    logger.warning(f"No branches starting with '{branch_prefix}/' were found. Your checkout was not updated.")

# Common setup for repository operations
def setup_repo_operation(subdir_path=None, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE):
    """Common setup for repository operations."""
    config = load_config(config_file)
    
    # Ensure config has repositories section
    if 'repositories' not in config:
        config['repositories'] = {}
    
    # Check if subdir exists in config if provided
    if subdir_path:
        norm_path = normalize_path(subdir_path)
        if norm_path not in config.get('repositories', {}):
            logger.error(f"Subdirectory '{norm_path}' not found in configuration.")
            raise ValueError(f"Subdirectory '{norm_path}' not found in configuration.")
        
    # Ensure fossil repository is open
    if not is_fossil_repo_open():
        logger.info(f"Opening Fossil repository {fossil_repo}...")
        run_command(['fossil', 'open', fossil_repo])
    else:
        logger.info(f"Using already open Fossil repository.")
        
    return config

# Import a Git repository
def import_git_repo(git_repo_url, subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, 
                    git_clones_dir=GIT_CLONES_DIR, marks_dir=MARKS_DIR):
    """Import a Git repository into the Fossil repository under a subdirectory."""
    if not validate_git_url(git_repo_url) or not validate_subdir_name(subdir_path):
        raise ValueError("Invalid input parameters")
    
    # Normalize the subdirectory path
    norm_path = normalize_path(subdir_path)
    
    config = setup_repo_operation(fossil_repo=fossil_repo, config_file=config_file)
    if norm_path in config.get('repositories', {}):
        logger.error(f"Subdirectory '{norm_path}' is already imported.")
        raise ValueError(f"Subdirectory '{norm_path}' is already imported.")
    
    # Use sanitized subdirectory name for file/directory names
    sanitized_name = norm_path.replace('/', '_')
    
    original_cwd = Path.cwd()
    git_clone_path = original_cwd / git_clones_dir / sanitized_name
    
    # Clean existing clone directory if needed
    if git_clone_path.exists():
        logger.warning(f"Clone directory '{git_clone_path}' already exists. Removing it...")
        shutil.rmtree(git_clone_path)
    git_clone_path.mkdir(exist_ok=True, parents=True)
    
    try:
        # Clone the Git repository
        logger.info(f"Cloning Git repository from {git_repo_url}...")
        run_command(['git', 'clone', '--no-local', git_repo_url, str(git_clone_path)])
        
        # Define marks file paths
        git_marks_file = original_cwd / marks_dir / f"{sanitized_name}_git.marks"
        fossil_marks_file = original_cwd / marks_dir / f"{sanitized_name}_fossil.marks"
        
        with cd(git_clone_path):
            # Process Git repo and import into Fossil
            process_git_repo(git_clone_path, norm_path)
            export_import_git_to_fossil(norm_path, git_marks_file, fossil_marks_file, original_cwd / fossil_repo)
        
        # Update configuration
        if 'repositories' not in config:
            config['repositories'] = {}
            
        config['repositories'][norm_path] = {
            'git_repo_url': git_repo_url,
            'git_clone_path': str(git_clone_path),
            'git_marks_file': str(git_marks_file),
            'fossil_marks_file': str(fossil_marks_file)
        }
        save_config(config, config_file)
        
        # Update checkout and report success
        update_fossil_checkout(norm_path)
        logger.info(f"Successfully imported '{git_repo_url}' into subdirectory '{norm_path}'.")
    except Exception as e:
        logger.error(f"Error during import: {str(e)}")
        raise

# Update a Git repository
def update_git_repo(subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE):
    """Update the Fossil repository with new changes from a Git repository."""
    # Normalize the path for config lookup
    norm_path = normalize_path(subdir_path)
    
    config = setup_repo_operation(norm_path, fossil_repo, config_file)
    
    try:
        git_clone_path = Path(config['repositories'][norm_path]['git_clone_path'])
        git_marks_file = Path(config['repositories'][norm_path]['git_marks_file'])
        fossil_marks_file = Path(config['repositories'][norm_path]['fossil_marks_file'])
        original_cwd = Path.cwd()
        
        with cd(git_clone_path):
            # Pull latest changes and update Fossil
            logger.info(f"Pulling latest changes for '{norm_path}'...")
            run_command(['git', 'pull'])
            
            # Process Git repo and update Fossil
            process_git_repo(git_clone_path, norm_path, force=True)
            export_import_git_to_fossil(norm_path, git_marks_file, fossil_marks_file, 
                                      original_cwd / fossil_repo, import_marks=True)
        
        logger.info(f"Successfully updated '{norm_path}' in the Fossil repository.")
    except Exception as e:
        logger.error(f"Error during update: {str(e)}")
        raise

# List imported repositories
def list_repos(config_file=CONFIG_FILE):
    """List all imported repositories and their details."""
    config = load_config(config_file)
    repositories = config.get('repositories', {})
    
    if not repositories:
        logger.info("No repositories have been imported.")
        return
    
    logger.info("Imported repositories:")
    for subdir, details in repositories.items():
        logger.info(f"- {subdir}: {details['git_repo_url']}")
        if logger.level == logging.DEBUG:  # More details when in debug mode
            logger.debug(f"  Clone path: {details['git_clone_path']}")
            logger.debug(f"  Git marks: {details['git_marks_file']}")
            logger.debug(f"  Fossil marks: {details['fossil_marks_file']}")

# Main function with command-line interface
def main():
    """Parse command-line arguments and execute the appropriate command."""
    parser = argparse.ArgumentParser(description='Fossil Import Tool (fitrepo) - Manage Git repositories in a Fossil repository.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    # Global options
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-f', '--fossil-repo', default=FOSSIL_REPO, help=f'Fossil repository file (default: {FOSSIL_REPO})')
    parser.add_argument('-c', '--config', default=CONFIG_FILE, help=f'Configuration file (default: {CONFIG_FILE})')
    parser.add_argument('-g', '--git-clones-dir', default=GIT_CLONES_DIR, help=f'Git clones directory (default: {GIT_CLONES_DIR})')
    parser.add_argument('-m', '--marks-dir', default=MARKS_DIR, help=f'Marks directory (default: {MARKS_DIR})')
    
    # Command subparsers
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')
    subparsers.add_parser('init', help='Initialize the Fossil repository and configuration')
    subparsers.add_parser('list', help='List all imported repositories')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import a Git repository into the Fossil repository')
    import_parser.add_argument('git_repo_url', help='URL of the Git repository to import')
    import_parser.add_argument('subdir_name', help='Subdirectory name under which to import this repository')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update the Fossil repository with new changes from a Git repository')
    update_parser.add_argument('subdir_name', help='Subdirectory name of the repository to update')

    args = parser.parse_args()

    # Set debug level if verbose flag is enabled
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Ensure directories exist based on potentially overridden values
    ensure_directories(args.git_clones_dir, args.marks_dir)

    # Execute the appropriate command
    commands = {
        'init': lambda: init_fossil_repo(args.fossil_repo, args.config),
        'import': lambda: import_git_repo(args.git_repo_url, args.subdir_name, args.fossil_repo, 
                                          args.config, args.git_clones_dir, args.marks_dir),
        'update': lambda: update_git_repo(args.subdir_name, args.fossil_repo, args.config),
        'list': lambda: list_repos(args.config)
    }
    
    try:
        commands[args.command]()
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
