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
import shlex
import tempfile

# Get version using importlib.metadata
try:
    __version__ = importlib.metadata.version('fitrepo')
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.5"

# Set up logging for user feedback
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Default constants
FOSSIL_REPO = 'fitrepo.fossil'
CONFIG_FILE = 'fitrepo.json'
GIT_CLONES_DIR = '.fitrepo/git_clones'
MARKS_DIR = '.fitrepo/marks'

# Helper functions for common operations
def run_command(cmd, check=True, capture_output=False, text=False, fossil_args=None, apply_args=True):
    """Run a command and return its result, with unified error handling."""
    try:
        # Add fossil args if applicable
        if fossil_args and cmd[0] == 'fossil' and apply_args and len(cmd) > 1:
            # Insert args after fossil command and subcommand
            cmd = [cmd[0], cmd[1]] + fossil_args + cmd[2:]
            
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

def ensure_directories(*dirs):
    """Ensure required directories exist."""
    for directory in dirs:
        Path(directory).mkdir(exist_ok=True, parents=True)

def check_dependencies():
    """Check if all required dependencies are installed."""
    dependencies = [
        (['git', '--version'], "Git"),
        (['fossil', 'version'], "Fossil"),
        (['git-filter-repo', '--version'], "git-filter-repo")
    ]
    
    for cmd, name in dependencies:
        try:
            run_command(cmd, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(f"{name} is not installed or not working properly.")
            if name == "git-filter-repo":
                logger.error("Install it with: pip install git-filter-repo")
            return False
    return True

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

def init_fossil_repo(fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, fossil_open_args=None, fossil_init_args=None):
    """Initialize the Fossil repository and configuration file."""
    try:
        repo_path = Path(fossil_repo)
        
        # Create and/or open repository as needed
        if not repo_path.exists():
            logger.info(f"Creating Fossil repository {fossil_repo}...")
            run_command(['fossil', 'init', fossil_repo], fossil_args=fossil_init_args)
            need_open = True
        else:
            need_open = not is_fossil_repo_open()
            
        if need_open:
            logger.info(f"Opening Fossil repository {fossil_repo}...")
            run_command(['fossil', 'open', fossil_repo], fossil_args=fossil_open_args)
        else:
            logger.info(f"Fossil repository is already open.")
            
        if not Path(config_file).exists():
            logger.info(f"Creating configuration file {config_file}...")
            # Use directory name as project name
            save_config({'name': Path.cwd().name, 'repositories': {}}, config_file)
            
        logger.info("Initialization complete.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during initialization: {e}")
        raise

# Path handling functions
def normalize_path(path_str):
    """Normalize a path for use as a subdirectory."""
    return str(Path(path_str)).replace('\\', '/').strip('/')

def path_to_branch_prefix(path_str):
    """Convert a normalized path to a branch prefix suitable for fossil."""
    return normalize_path(path_str).replace('/', '__')

def branch_prefix_to_path(prefix):
    """Convert a branch prefix back to its path representation."""
    return prefix.replace('__', '/')

# Validation functions
def validate_git_url(url):
    """Validate Git repository URL or path."""
    if not url:
        logger.error("Git URL or path cannot be empty")
        return False
    
    # Accept URLs or existing paths
    if url.startswith(('http', 'git', 'ssh')):
        return True
    
    path = Path(url)
    if path.exists():
        if (path / '.git').exists():
            return True
        logger.warning(f"Path exists but may not be a Git repository: {url}")
        return True
        
    logger.error(f"Path does not exist: {url}")
    return False

def validate_subdir_name(name):
    """Validate subdirectory path."""
    if not name:
        logger.error("Subdirectory name cannot be empty")
        return False
        
    if name.startswith('/') or name.endswith('/'):
        logger.error(f"Invalid subdirectory path: {name}. Must not start or end with '/'")
        return False
        
    if any(part.startswith('.') for part in name.split('/')):
        logger.error(f"Invalid subdirectory path: {name}. Path components must not start with '.'")
        return False
        
    if re.search(r'[<>:"|?*\x00-\x1F]', name):
        logger.error(f"Invalid characters in subdirectory path: {name}")
        return False
        
    return True

# Git operations
def process_git_repo(git_clone_path, subdir_path, force=False):
    """Apply subdirectory filter and rename branches with prefix."""
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
    branches = [b.strip().lstrip('* ') for b in result.stdout.splitlines() if b.strip()]
    
    # Rename each branch that doesn't already have the prefix
    for branch in branches:
        if branch and not branch.startswith(f"{branch_prefix}/"):
            try:
                # Check if target branch already exists
                if run_command(['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{branch_prefix}/{branch}'], check=False).returncode == 0:
                    logger.info(f"Branch '{branch_prefix}/{branch}' already exists, skipping rename")
                    # Since we can't have two branches with the same name, delete the current one
                    # The existing prefixed one already has all our changes
                    run_command(['git', 'branch', '-D', branch])
                else:
                    # Safe to rename
                    run_command(['git', 'branch', '-m', branch, f"{branch_prefix}/{branch}"])
            except subprocess.CalledProcessError:
                logger.warning(f"Failed to rename branch '{branch}'")

def export_import_git_to_fossil(subdir_path, git_marks_file, fossil_marks_file, fossil_repo, import_marks=False):
    """Export from Git and import into Fossil with appropriate marks files."""
    logger.info(f"{'Updating' if import_marks else 'Exporting'} Git history to Fossil...")
    
    # Build git command with marks files
    git_cmd = ['git', 'fast-export', '--all']
    if import_marks and Path(git_marks_file).exists():
        git_cmd.extend(['--import-marks', str(git_marks_file)])
    git_cmd.extend(['--export-marks', str(git_marks_file)])
    
    # Build fossil command with marks files
    fossil_cmd = ['fossil', 'import', '--git', '--incremental']
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
    branch_prefix = path_to_branch_prefix(normalize_path(subdir_path))
    
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
def setup_repo_operation(subdir_path=None, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, fossil_args=None):
    """Common setup for repository operations."""
    config = load_config(config_file)
    
    # Ensure config has repositories section
    config.setdefault('repositories', {})
    
    # Check if subdir exists in config if provided
    if subdir_path:
        norm_path = normalize_path(subdir_path)
        if norm_path not in config.get('repositories', {}):
            msg = f"Subdirectory '{norm_path}' not found in configuration."
            logger.error(msg)
            raise ValueError(msg)
        
    # Ensure fossil repository is open
    if not is_fossil_repo_open():
        logger.info(f"Opening Fossil repository {fossil_repo}...")
        run_command(['fossil', 'open', fossil_repo], fossil_args=fossil_args)
    else:
        logger.info(f"Using already open Fossil repository.")
        
    return config

# Repository operations
def import_git_repo(git_repo_url, subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, 
                    git_clones_dir=GIT_CLONES_DIR, marks_dir=MARKS_DIR, fossil_args=None):
    """Import a Git repository into the Fossil repository under a subdirectory."""
    if not validate_git_url(git_repo_url) or not validate_subdir_name(subdir_path):
        raise ValueError("Invalid input parameters")
    
    # Normalize the subdirectory path
    norm_path = normalize_path(subdir_path)
    
    config = setup_repo_operation(fossil_repo=fossil_repo, config_file=config_file, fossil_args=fossil_args)
    if norm_path in config.get('repositories', {}):
        msg = f"Subdirectory '{norm_path}' is already imported."
        logger.error(msg)
        raise ValueError(msg)
    
    # Use sanitized subdirectory name for file/directory names
    sanitized_name = norm_path.replace('/', '_')
    
    original_cwd = Path.cwd()
    git_clone_path = original_cwd / git_clones_dir / sanitized_name
    git_marks_file = original_cwd / marks_dir / f"{sanitized_name}_git.marks"
    fossil_marks_file = original_cwd / marks_dir / f"{sanitized_name}_fossil.marks"
    
    # Clean existing clone directory if needed
    if git_clone_path.exists():
        logger.warning(f"Clone directory '{git_clone_path}' already exists. Removing it...")
        shutil.rmtree(git_clone_path)
    git_clone_path.mkdir(exist_ok=True, parents=True)
    
    try:
        # Clone the Git repository
        logger.info(f"Cloning Git repository from {git_repo_url}...")
        run_command(['git', 'clone', '--no-local', git_repo_url, str(git_clone_path)])
        
        with cd(git_clone_path):
            # Process Git repo and import into Fossil
            process_git_repo(git_clone_path, norm_path)
            export_import_git_to_fossil(norm_path, git_marks_file, fossil_marks_file, original_cwd / fossil_repo)
        
        # Update configuration
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

def update_git_repo(subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, fossil_args=None):
    """Update the Fossil repository with new changes from a Git repository."""
    norm_path = normalize_path(subdir_path)
    config = setup_repo_operation(norm_path, fossil_repo, config_file, fossil_args=fossil_args)
    
    try:
        repo_details = config['repositories'][norm_path]
        git_clone_path = Path(repo_details['git_clone_path'])
        git_marks_file = Path(repo_details['git_marks_file'])
        fossil_marks_file = Path(repo_details['fossil_marks_file'])
        git_repo_url = repo_details['git_repo_url']
        original_cwd = Path.cwd()
        
        # Clean the existing clone and create a fresh one to avoid git-filter-repo issues
        logger.info(f"Re-cloning Git repository for '{norm_path}'...")
        if git_clone_path.exists():
            shutil.rmtree(git_clone_path)
        git_clone_path.mkdir(exist_ok=True, parents=True)
        
        # Clone the Git repository
        run_command(['git', 'clone', '--no-local', git_repo_url, str(git_clone_path)])
        
        with cd(git_clone_path):
            # Process Git repo and update Fossil
            process_git_repo(git_clone_path, norm_path, force=True)
            export_import_git_to_fossil(norm_path, git_marks_file, fossil_marks_file, 
                                      original_cwd / fossil_repo, import_marks=True)
        
        logger.info(f"Successfully updated '{norm_path}' in the Fossil repository.")
    except Exception as e:
        logger.error(f"Error during update: {str(e)}")
        raise

def push_to_git(subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, fossil_args=None, message=None):
    """Push Fossil changes to the original Git repository using bidirectional synchronization."""
    norm_path = normalize_path(subdir_path)
    config = setup_repo_operation(norm_path, fossil_repo, config_file, fossil_args=fossil_args)
    
    try:
        repo_details = config['repositories'][norm_path]
        git_repo_url = repo_details['git_repo_url']
        git_clone_path = Path(repo_details['git_clone_path'])
        git_marks_file = Path(repo_details['git_marks_file'])
        fossil_marks_file = Path(repo_details['fossil_marks_file'])
        original_cwd = Path.cwd()
        abs_fossil_repo = original_cwd / fossil_repo
        
        # Get the current branch *before* we open in a temp directory
        # This ensures we know which branch we need to use
        branch_prefix = path_to_branch_prefix(norm_path)
        all_branches_output = run_command(['fossil', 'branch', 'list'], capture_output=True, text=True).stdout
        target_branch = None
        
        # Find branch that matches our prefix
        for line in all_branches_output.splitlines():
            # Clean up the branch name by removing asterisk and whitespace
            branch_name = line.strip().lstrip('*').strip()
            if branch_name.startswith(f"{branch_prefix}/"):
                target_branch = branch_name
                logger.info(f"Found target branch: {target_branch}")
                break
        
        if not target_branch:
            # Try a more flexible approach - look for branch names that might match
            logger.warning(f"No branch with exact prefix '{branch_prefix}/' found. Looking for alternatives...")
            
            # Get all branches and look for best match
            for line in all_branches_output.splitlines():
                # Clean up the branch name properly
                branch_name = line.strip().lstrip('*').strip()
                # Check if the branch contains the path components in any form
                path_parts = norm_path.split('/')
                if all(part in branch_name.lower().replace('__', '_') for part in path_parts):
                    target_branch = branch_name
                    logger.info(f"Found alternative branch: {target_branch}")
                    break
        
        if not target_branch:
            raise ValueError(f"Could not find any branch related to '{norm_path}'. Available branches: {all_branches_output}")
        
        # More aggressive clean and re-clone approach
        logger.info(f"Recreating Git clone for '{norm_path}'...")
        if git_clone_path.exists():
            shutil.rmtree(git_clone_path)
        git_clone_path.mkdir(exist_ok=True, parents=True)
        
        # Clone with --local to prevent path issues and configure .git properly
        run_command(['git', 'clone', '--no-local', git_repo_url, str(git_clone_path)])
        
        # Completely isolate the Git repository to prevent path leakage
        with cd(git_clone_path):
            # Configure Git to restrict operations to this directory
            run_command(['git', 'config', 'core.worktree', '.'])
            run_command(['git', 'config', 'core.bare', 'false'])
            run_command(['git', 'config', '--local', 'core.sparseCheckout', 'true'])
            
            os.makedirs(os.path.join(git_clone_path, '.git', 'info'), exist_ok=True)
            with open(os.path.join(git_clone_path, '.git', 'info', 'exclude'), 'w') as f:
                f.write("# Exclude everything outside this directory\n../\n")
            
            # Set up sparse checkout to only track files in this directory
            os.makedirs(os.path.join(git_clone_path, '.git', 'info', 'sparse-checkout'), exist_ok=True)
            with open(os.path.join(git_clone_path, '.git', 'info', 'sparse-checkout', 'index'), 'w') as f:
                f.write("/*\n!../\n")
        
        # Get the current branch *before* we open in a temp directory
        # This ensures we know which branch we need to use
        branch_prefix = path_to_branch_prefix(norm_path)
        all_branches_output = run_command(['fossil', 'branch', 'list'], capture_output=True, text=True).stdout
        target_branch = None
        
        # Find branch that matches our prefix
        for line in all_branches_output.splitlines():
            # Clean up the branch name by removing asterisk and whitespace
            branch_name = line.strip().lstrip('*').strip()
            if branch_name.startswith(f"{branch_prefix}/"):
                target_branch = branch_name
                logger.info(f"Found target branch: {target_branch}")
                break
        
        if not target_branch:
            # Try a more flexible approach - look for branch names that might match
            logger.warning(f"No branch with exact prefix '{branch_prefix}/' found. Looking for alternatives...")
            
            # Get all branches and look for best match
            for line in all_branches_output.splitlines():
                # Clean up the branch name properly
                branch_name = line.strip().lstrip('*').strip()
                # Check if the branch contains the path components in any form
                path_parts = norm_path.split('/')
                if all(part in branch_name.lower().replace('__', '_') for part in path_parts):
                    target_branch = branch_name
                    logger.info(f"Found alternative branch: {target_branch}")
                    break
        
        if not target_branch:
            raise ValueError(f"Could not find any branch related to '{norm_path}'. Available branches: {all_branches_output}")
        
        # More aggressive clean and re-clone approach
        logger.info(f"Recreating Git clone for '{norm_path}'...")
        if git_clone_path.exists():
            shutil.rmtree(git_clone_path)
        git_clone_path.mkdir(exist_ok=True, parents=True)
        run_command(['git', 'clone', git_repo_url, str(git_clone_path)])
        
        # Set Git config to ignore parent directories
        with cd(git_clone_path):
            # Configure Git to only track files in this directory
            run_command(['git', 'config', 'core.worktree', '.'])
            # Add a .git/info/exclude entry to ignore parent directories
            os.makedirs(os.path.join(git_clone_path, '.git', 'info'), exist_ok=True)
            with open(os.path.join(git_clone_path, '.git', 'info', 'exclude'), 'a') as f:
                f.write("\n# Ignore parent directories\n../\n")
        
        # Export from Fossil to Git - CRITICAL: run the export in a controlled environment
        logger.info(f"Exporting Fossil changes to Git...")
        
        # CRITICAL FIX: We need to isolate the export to the specific subdirectory
        # Create a temporary directory to work in
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract just the specific subfolder to this temp directory
            run_command(['fossil', 'open', str(abs_fossil_repo), '--workdir', str(temp_path)])
            
            # Make sure we're on the right branch using the branch name we found earlier
            with cd(temp_path):
                logger.info(f"Updating to branch: {target_branch}")
                run_command(['fossil', 'update', target_branch])
                
                # Now export from this controlled environment
                export_cmd = ['fossil', 'export', '--git']
                if Path(fossil_marks_file).exists():
                    export_cmd.extend([f'--import-marks={fossil_marks_file}'])
                export_cmd.extend([f'--export-marks={fossil_marks_file}'])
                
                # Build Git fast-import command with marks
                import_cmd = ['git', 'fast-import', '--force']
                if Path(git_marks_file).exists():
                    import_cmd.extend([f'--import-marks={git_marks_file}'])
                import_cmd.extend([f'--export-marks={git_marks_file}'])
                
                # Export from the controlled temp directory
                with cd(git_clone_path):
                    try:
                        fossil_export = subprocess.Popen(export_cmd, stdout=subprocess.PIPE)
                        git_import = subprocess.Popen(import_cmd, stdin=fossil_export.stdout)
                        fossil_export.stdout.close()
                        git_import.communicate()
                        
                        # Git fast-import may exit with non-zero for warnings too,
                        # so we'll continue with the push regardless
                        if git_import.returncode != 0:
                            logger.warning(f"Git fast-import returned non-zero exit code {git_import.returncode}. Attempting to push anyway...")
                        
                        # Push the changes
                        logger.info("Pushing changes to Git repository...")
                        run_command(['git', 'checkout', '-f', 'master'], check=False)
                        run_command(['git', 'push', '-f', 'origin', '--all'])
                        run_command(['git', 'push', '-f', 'origin', '--tags'])
                    except Exception as e:
                        logger.error(f"Error during git import/export: {str(e)}")
                        raise
                
                # Close the temporary fossil checkout
                run_command(['fossil', 'close'], check=False)
            
        logger.info(f"Successfully pushed Fossil changes from '{norm_path}' to Git repository.")
    except Exception as e:
        logger.error(f"Error during push to Git: {str(e)}")
        raise

def reset_marks(subdir_path, fossil_repo=FOSSIL_REPO, config_file=CONFIG_FILE, fossil_args=None):
    """Reset marks files for a repository to force a clean export/import."""
    norm_path = normalize_path(subdir_path)
    config = setup_repo_operation(norm_path, fossil_repo, config_file, fossil_args=fossil_args)
    
    try:
        repo_details = config['repositories'][norm_path]
        git_marks_file = Path(repo_details['git_marks_file'])
        fossil_marks_file = Path(repo_details['fossil_marks_file'])
        
        # Delete the marks files if they exist
        for marks_file in [git_marks_file, fossil_marks_file]:
            if marks_file.exists():
                logger.info(f"Removing marks file: {marks_file}")
                marks_file.unlink()
                
        logger.info(f"Marks files for '{norm_path}' have been reset. Next push will do a full export/import.")
        logger.info(f"Note: This may cause history to be rewritten in the Git repository.")
    except Exception as e:
        logger.error(f"Error during marks reset: {str(e)}")
        raise

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

def main():
    """Parse command-line arguments and execute the appropriate command."""
    # Create a parent parser with common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parent_parser.add_argument('-f', '--fossil-repo', default=FOSSIL_REPO, help=f'Fossil repository file')
    parent_parser.add_argument('-c', '--config', default=CONFIG_FILE, help=f'Configuration file')
    parent_parser.add_argument('-g', '--git-clones-dir', default=GIT_CLONES_DIR, help=f'Git clones directory')
    parent_parser.add_argument('-M', '--marks-dir', default=MARKS_DIR, help=f'Marks directory')  # Changed -m to -M
    
    # Fossil arguments handling
    parent_parser.add_argument('--fwd-fossil-open', type=str, metavar='ARGS',
                               help='Forward arguments to fossil open command')
    parent_parser.add_argument('--fwd-fossil-init', type=str, metavar='ARGS',
                               help='Forward arguments to fossil init command')
    parent_parser.add_argument('--fwdfossil', type=str, metavar='FOSSIL_ARGS',
                               help='DEPRECATED - Forward arguments to fossil commands')
    
    # Main parser
    parser = argparse.ArgumentParser(description='Fossil Import Tool (fitrepo)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    # Add common arguments to main parser
    parent_group = parser.add_argument_group('global options')
    for action in parent_parser._actions:
        parent_group._group_actions.append(action)
    
    # Command subparsers
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')
    
    # Command definitions
    subparsers.add_parser('init', help='Initialize repository and config', parents=[parent_parser])
    subparsers.add_parser('list', help='List imported repositories', parents=[parent_parser])
    
    import_parser = subparsers.add_parser('import', help='Import Git repository', parents=[parent_parser])
    import_parser.add_argument('git_repo_url', help='URL of Git repository to import')
    import_parser.add_argument('subdir_name', help='Subdirectory name for import')

    update_parser = subparsers.add_parser('update', help='Update with Git changes', parents=[parent_parser])
    update_parser.add_argument('subdir_name', help='Subdirectory name to update')

    # Add command for git push
    git_push_parser = subparsers.add_parser('push-git', help='Push Fossil changes to Git', parents=[parent_parser])
    git_push_parser.add_argument('subdir_name', help='Subdirectory name to push')
    git_push_parser.add_argument('-m', '--message', help='Custom commit message for Git')

    # Add command for resetting marks
    reset_parser = subparsers.add_parser('reset-marks', help='Reset marks files for clean export', parents=[parent_parser])
    reset_parser.add_argument('subdir_name', help='Subdirectory name to reset marks for')

    # Special handling for fwdfossil argument issue
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if '--fwdfossil' in ' '.join(sys.argv) and '-f' in sys.argv:
            print("ERROR: For the --fwdfossil argument with values starting with '-', use equals sign format:")
            print("Example: --fwdfossil=\"-f\"")
            sys.exit(1)
        raise

    # Set debug level if verbose
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose mode enabled")

    # Parse fossil arguments
    fossil_args = shlex.split(args.fwdfossil) if args.fwdfossil else []
    fossil_open_args = shlex.split(args.fwd_fossil_open) if args.fwd_fossil_open else fossil_args
    fossil_init_args = shlex.split(args.fwd_fossil_init) if args.fwd_fossil_init else []
    
    # Ensure directories exist
    ensure_directories(args.git_clones_dir, args.marks_dir)

    # Command dispatch
    commands = {
        'init': lambda: init_fossil_repo(args.fossil_repo, args.config, fossil_open_args, fossil_init_args),
        'import': lambda: import_git_repo(args.git_repo_url, args.subdir_name, args.fossil_repo, 
                                         args.config, args.git_clones_dir, args.marks_dir, fossil_open_args),
        'update': lambda: update_git_repo(args.subdir_name, args.fossil_repo, args.config, fossil_open_args),
        'list': lambda: list_repos(args.config),
        'push-git': lambda: push_to_git(args.subdir_name, args.fossil_repo, args.config, fossil_open_args, args.message),
        'reset-marks': lambda: reset_marks(args.subdir_name, args.fossil_repo, args.config, fossil_open_args)
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
