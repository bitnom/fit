from .fit import main, init_fossil_repo, import_git_repo, update_git_repo, list_repos, validate_git_url, validate_subdir_name, load_config, save_config, CONFIG_FILE, FOSSIL_REPO

# Expose the main entry point
__all__ = ['main', 'init_fossil_repo', 'import_git_repo', 'update_git_repo', 
           'list_repos', 'validate_git_url', 'validate_subdir_name', 
           'load_config', 'save_config', 'CONFIG_FILE', 'FOSSIL_REPO']
