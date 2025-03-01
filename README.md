# Fitrepo - Fossil Import Tool

This tool manages the import and incremental update of multiple Git repositories into a single Fossil repository, effectively creating a monorepo. Each Git repository is organized into its own subdirectory within the Fossil repository, and its branches are prefixed with the subdirectory name (e.g., `subrepo/master`).

## Usage

### Installation
```bash
pip install fitrepo
```

## How to Use

Run the script from the directory where you want the Fossil repository (`fitrepo.fossil`) and configuration file (`fitrepo.json`) to reside.

### Commands

1. **Initialize the Fossil Repository**
   ```bash
   uv tool run fitrepo init
   ```
   - Creates `fitrepo.fossil` if it doesn't exist.
   - Creates an empty `fitrepo.json` configuration file if it doesn't exist.
   - Supports: `-v/--verbose`, `-f/--fossil-repo`, `-c/--config`, `-g/--git-clones-dir`, `-m/--marks-dir`, 
     `--fwd-fossil-open`, `--fwd-fossil-init`, `--fwdfossil`

2. **Import a Git Repository**
   ```bash
   uv tool run fitrepo import <git-repo-url> <subdir-name>
   ```
   - Example: `uv tool run fitrepo import https://github.com/user/subrepo.git subrepo`
   - Clones the Git repository, moves its files into the `subrepo` subdirectory, prefixes its branches (e.g., `subrepo/master`), and imports it into the Fossil repository.
   - Stores configuration details in `fitrepo.json`.
   - Supports the same options as the `init` command.

3. **Update an Existing Git Repository**
   ```bash
   uv tool run fitrepo update <subdir-name>
   ```
   - Example: `uv tool run fitrepo update subrepo`
   - Pulls the latest changes from the Git repository associated with `subrepo`, reapplies the filters, and incrementally updates the Fossil repository.
   - Supports the same options as the `init` command.

4. **List Imported Repositories**
   ```bash
   uv tool run fitrepo list
   ```
   - Lists all the Git repositories that have been imported into the Fossil repository.
   - Shows the subdirectory name and Git repository URL for each imported repository.
   - In verbose mode, shows additional details like clone path and marks files.

### Command-line Options

The tool supports several global options that can be used with any command:

- `-v/--verbose`: Enable verbose output.
- `-f/--fossil-repo FILE`: Specify a custom Fossil repository file (default: `fitrepo.fossil`).
- `-c/--config FILE`: Specify a custom configuration file (default: `fitrepo.json`).
- `-g/--git-clones-dir DIR`: Specify a custom Git clones directory (default: `.fitrepo/git_clones`).
- `-m/--marks-dir DIR`: Specify a custom marks directory (default: `.fitrepo/marks`).
- `--fwd-fossil-open ARGS`: Forward arguments to the `fossil open` command.
- `--fwd-fossil-init ARGS`: Forward arguments to the `fossil init` command.
- `--fwdfossil ARGS`: Forward arguments to all fossil commands (deprecated).
- `--version`: Show the version of the tool and exit.
- `--help`: Show help message and exit.

### Configuration File (`fitrepo.json`)

The tool maintains a `fitrepo.json` file to track imported repositories. Example content after importing a repository:

```json
{
    "name": "project_name",
    "repositories": {
        "subrepo": {
            "git_repo_url": "https://github.com/user/repo.git",
            "git_clone_path": ".fitrepo/git_clones/subrepo",
            "git_marks_file": ".fitrepo/marks/subrepo_git.marks",
            "fossil_marks_file": ".fitrepo/marks/subrepo_fossil.marks"
        }
    }
}
```

## Features

- **Subdirectory Organization**: Each Git repository's files are placed in a unique subdirectory within the Fossil repository.
- **Branch Prefixing**: Branches are renamed with the subdirectory name as a prefix (e.g., `master` becomes `subrepo/master`).
- **Incremental Updates**: Uses marks files to ensure only new changes are imported during updates.
- **Error Handling**: Provides informative error messages for common issues (e.g., duplicate subdirectory names, command failures).
- **User Feedback**: Logs progress and errors to the console.
- **Flexible Configuration**: Allows customization of file paths and Fossil arguments.

## Requirements

- **Python 3.9+**
- **Git**
- **git-filter-repo** (automatically installed as a dependency)
- **Fossil** (installed and accessible from the command line)

## Notes

- Run the tool in the directory where you want `fitrepo.fossil` to reside.
- The tool creates `.fitrepo/git_clones/` for Git repositories and `.fitrepo/marks/` for marks files.
- Only branches are prefixed; tags retain their original names.
- Use `-v/--verbose` for detailed output during operations.
- When specifying arguments with `--fwdfossil` that begin with a dash, use the equals sign format to avoid shell interpretation issues (e.g., `--fwdfossil="-f"`).

## Advanced Usage

### Forwarding Arguments to Fossil Commands

You can pass specific arguments to fossil commands:

```bash
# Forward '-f' argument to 'fossil open' command
uv tool run fitrepo init --fwd-fossil-open="-f"

# Forward arguments to 'fossil init' command
uv tool run fitrepo init --fwd-fossil-init="--template /path/to/template"
```

### Using Nested Subdirectories

You can import repositories into nested subdirectories:

```bash
uv tool run fitrepo import https://github.com/user/repo.git libs/common
```

This will clone the repository to `libs/common/repo` subdirectory and prefix branches with `libs/common/repo/`.