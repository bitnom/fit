# fit

This tool manages the import and incremental update of multiple Git repositories into a single Fossil repository, effectively creating a monorepo. Each Git repository is organized into its own subdirectory within the Fossil repository, and its branches are prefixed with the subdirectory name (e.g., `hotbox/master`). The tool provides three commands: `init` to initialize the Fossil repository, `import` to add a new Git repository, and `update` to incrementally update an existing one.

## How to Use

Run the script from the directory where you want the Fossil repository (`monorepo.fossil`) and configuration file (`fit.json`) to reside.

### Commands

1. **Initialize the Fossil Repository**
   ```bash
   python fit.py init
   ```
   - Creates `monorepo.fossil` if it doesn’t exist.
   - Creates an empty `fit.json` configuration file if it doesn’t exist.

2. **Import a Git Repository**
   ```bash
   python fit.py import <git-repo-url> <subdir-name>
   ```
   - Example: `python fit.py import https://github.com/user/repo.git hotbox`
   - Clones the Git repository, moves its files into the `hotbox` subdirectory, prefixes its branches (e.g., `hotbox/master`), and imports it into the Fossil repository.
   - Stores configuration details in `fit.json`.

3. **Update an Existing Git Repository**
   ```bash
   python fit.py update <subdir-name>
   ```
   - Example: `python fit.py update hotbox`
   - Pulls the latest changes from the Git repository associated with `hotbox`, reapplies the filters, and incrementally updates the Fossil repository.

### Configuration File (`fit.json`)

The tool maintains a `fit.json` file to track imported repositories. Example content after importing a repository:

```json
{
    "hotbox": {
        "git_repo_url": "https://github.com/user/repo.git",
        "git_clone_path": ".git_clones/hotbox",
        "git_marks_file": ".marks/hotbox_git.marks",
        "fossil_marks_file": ".marks/hotbox_fossil.marks"
    }
}
```

## Features

- **Subdirectory Organization**: Each Git repository’s files are placed in a unique subdirectory within the Fossil repository.
- **Branch Prefixing**: Branches are renamed with the subdirectory name as a prefix (e.g., `master` becomes `hotbox/master`).
- **Incremental Updates**: Uses marks files to ensure only new changes are imported during updates.
- **Error Handling**: Provides informative error messages for common issues (e.g., duplicate subdirectory names, command failures).
- **User Feedback**: Logs progress and errors to the console.

## Requirements

- **Python 3.x**
- **Git** (with `git filter-repo` installed; install via `pip install git-filter-repo`)
- **Fossil** (installed and accessible from the command line)

## Notes

- Run the tool in the directory where you want `monorepo.fossil` to reside.
- The tool assumes `.git_clones/` and `.marks/` directories are subdirectories of the current working directory.
- Only branches are prefixed; tags retain their original names. To prefix tags, modify the `refname_rewriter` string in the code.

This implementation fulfills your intention to create a CLI tool that seamlessly manages multiple Git repositories within a single Fossil repository, with isolated subdirectories and prefixed branches.