"""
Fitrepo - Fossil Import Tool

A tool for managing Git repositories within a Fossil monorepo.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("fitrepo")
except PackageNotFoundError:
    __version__ = "0.1.53"  # fallback version

# Import main function directly, making it accessible as fitrepo.main
from .fitrepo import main, __version__

# Also make any other functions or constants available at the package level
from .fitrepo import (
    init_fossil_repo, import_git_repo, update_git_repo, list_repos,
    FOSSIL_REPO, CONFIG_FILE, GIT_CLONES_DIR, MARKS_DIR
)

# Expose the main entry point
__all__ = ['main', 'init_fossil_repo', 'import_git_repo', 'update_git_repo', 
           'list_repos', 'validate_git_url', 'validate_subdir_name', 
           'load_config', 'save_config', 'CONFIG_FILE', 'FOSSIL_REPO',
           '__version__']
