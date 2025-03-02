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
   - Automatically creates `.vscode/settings.json` with optimized VSCode settings.
   - Supports: `-v/--verbose`, `-f/--fossil-repo`, `-c/--config`, `-g/--git-clones-dir`, `-m/--marks-dir`, 
     `--fwd-fossil-open`, `--fwd-fossil-init`, `--fwdfossil`, `--novscode`

2. **Import a Git Repository**
   ```bash
   uv tool run fitrepo import <git-repo-url> <subdir-name>
   ```
   - Example: `uv tool run fitrepo import https://github.com/user/subrepo.git subrepo`
   - Clones the Git repository, moves its files into the `subrepo` subdirectory, prefixes its branches (e.g., `subrepo/master`), and imports it into the Fossil repository.
   - Stores configuration details in `fitrepo.json`.
   - Supports: `-v/--verbose`, `-f/--fossil-repo`, `-c/--config`, `-g/--git-clones-dir`, `-m/--marks-dir`, 
     `--fwd-fossil-open`, `--fwd-fossil-init`, `--fwdfossil`

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

5. **Push Changes to Git Repository**
   ```bash
   uv tool run fitrepo push-git <subdir-name>
   ```
   - Example: `uv tool run fitrepo push-git subrepo`
   - Pushes the changes from the Fossil repository back to the associated Git repository.
   - Supports the same options as the `init` command.
   - Optional `-m/--message` parameter to specify a custom commit message.

6. **Reset Marks Files**
   ```bash
   uv tool run fitrepo reset-marks <subdir-name>
   ```
   - Example: `uv tool run fitrepo reset-marks subrepo`
   - Deletes the marks files for the specified repository, forcing a complete re-export on the next operation.
   - Useful when synchronization between Git and Fossil repositories becomes inconsistent.

7. **Fix Git Status Display**
   ```bash
   uv tool run fitrepo fix-git-status <subdir-name>
   ```
   - Example: `uv tool run fitrepo fix-git-status subrepo`
   - Fixes the Git configuration to properly hide untracked files and focus only on the relevant subdirectory.
   - Helpful when Git status shows files outside the subdirectory or internal Git files.

### Command-line Options

The tool supports several global options that can be used with any command:

- `-v/--verbose`: Enable verbose output.
- `-f/--fossil-repo FILE`: Specify a custom Fossil repository file (default: `fitrepo.fossil`).
- `-c/--config FILE`: Specify a custom configuration file (default: `fitrepo.json`).
- `-g/--git-clones-dir DIR`: Specify a custom Git clones directory (default: `.fitrepo/git_clones`).
- `-M/--marks-dir DIR`: Specify a custom marks directory (default: `.fitrepo/marks`).
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
- After installation, you can use either `fit`, `fitrepo`, or `fossil-import-tool` commands directly instead of `uv tool run fitrepo`.

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

### VSCode Integration

When initializing a repository with `fitrepo init`, the tool automatically creates a `.vscode/settings.json` file with optimized settings for working with the monorepo:

- Hides duplicate Git repositories from the Source Control panel
- Excludes `.fitrepo` directory and its contents from the file explorer
- Excludes `.fitrepo` content from search results

These settings help provide a cleaner interface when working with the monorepo in VSCode. If you prefer to manage your own VSCode settings, you can use the `--novscode` flag during initialization:

```bash
# Skip VSCode settings during initialization
uv tool run fitrepo init --novscode
```

If a `.vscode/settings.json` file already exists, fitrepo will merge its settings rather than overwriting the file.

### Example Workflow

1. Initialize the monorepo:
   ```bash
   uv tool run fitrepo init
   ```

2. Import a Git repository:
   ```bash
   uv tool run fitrepo import https://github.com/user/repo.git subrepo
   ```

3. Update the Git repository from remote:
   ```bash
   uv tool run fitrepo update subrepo
   ```

4. Make changes and commit them with Fossil:
   ```bash
   cd subrepo
   echo "# New feature documentation" >> README.md
   fossil add README.md
   fossil commit -m "Update documentation for new feature"
   cd ..
   ```

5. Push changes back to the Git repository:
   ```bash
   uv tool run fitrepo push-git subrepo
   ```

## Troubleshooting

### Git Repository Visibility Issues

If you encounter issues where `git status` in an imported subdirectory shows files outside of that subdirectory or shows Git internal files (like "HEAD", "config", "hooks/"):

1. Use the fix-git-status command to repair the Git worktree configuration:
   ```bash
   uv tool run fitrepo fix-git-status <subdir-name>
   ```

2. If the problem persists, you can manually hide untracked files:
   ```bash
   cd <subdir-name>
   git config --local status.showUntrackedFiles no
   ```

3. For repositories that were imported with older versions of fitrepo, you may need to re-import the repository.

### "Would fork. 'update' first or use --branch or --allow-fork"

If you see this error when committing in Fossil, it means there are new changes in the upstream repository that you haven't pulled down yet. Unlike Git, which would let you create divergent histories, Fossil tries to maintain a linear history by default.

You have three options:

1. **Update first** (recommended): Pull in the latest changes before committing
   ```bash
   fossil update
   fossil commit -m "your message"
   ```

2. **Create a new branch**: Explicitly make a branch for your changes
   ```bash
   fossil commit --branch new-feature-name -m "your message"
   ```

3. **Allow the fork**: Tell Fossil to proceed anyway
   ```bash
   fossil commit --allow-fork -m "your message"
   ```

This is an intentional design difference between Fossil and Git, aimed at encouraging linear history and reducing merge complexity.