# fitrepo Developer Documentation

This document provides a comprehensive explanation of the `fitrepo` tool's implementation, including the design decisions, workflow, and technical details for developers who want to understand or extend the codebase.

## Overview

`fitrepo` (Fossil Import Tool) is a Python utility that facilitates importing multiple Git repositories into a single Fossil repository while maintaining proper isolation between them. It solves several challenges:

1. **Subdirectory organization**: Places each Git repository's files in a unique subdirectory
2. **Branch naming**: Prefixes all branches with the subdirectory name (e.g., `hotbox/master`)  
3. **Incremental updates**: Enables pulling new changes from Git repositories and updating Fossil
4. **Workflow management**: Handles all the complex Git and Fossil operations through a simple command-line interface

## Core Components

### 1. Configuration Management

The tool uses a JSON file (`fitrepo.json` by default) to track imported repositories with the following information:
- Git repository URL
- Local Git clone path
- Git marks file location
- Fossil marks file location

These configuration entries allow the tool to handle incremental updates.

### 2. Repository Operations

#### Initial Setup (`init`)
- Creates a new Fossil repository if it doesn't exist
- Opens the repository in the current directory
- Initializes an empty configuration file

#### Repository Import (`import`)
The import process follows these steps:

1. **Validation**
   - Checks that the Git URL is valid
   - Ensures the subdirectory name is valid
   - Verifies the subdirectory hasn't already been imported

2. **Git Repository Processing**
   - Clones the Git repository to a temporary location (`.git_clones/<subdir_name>`)
   - Uses `git-filter-repo --to-subdirectory-filter` to move all files into the specified subdirectory
   - Renames all branches to have the subdirectory name as a prefix using Git commands

3. **Fossil Import**
   - Uses `git fast-export` to export the modified Git history
   - Pipes this to `fossil import --git` to import into the Fossil repository
   - Uses marks files to enable incremental updates later

4. **Configuration Update**
   - Stores information about the imported repository in the configuration file

5. **Checkout Update**
   - Identifies a branch with the correct prefix in Fossil
   - Updates the current checkout to show the newly imported files

#### Repository Update (`update`)
The update process follows similar steps:

1. **Configuration Lookup**
   - Retrieves repository details from the configuration file

2. **Git Update**
   - Pulls the latest changes from the Git repository
   - Re-applies the subdirectory filter and branch renaming

3. **Incremental Import**
   - Uses the marks files to identify new commits
   - Exports and imports only these new commits to Fossil

#### Repository Listing (`list`)
- Displays information about all imported repositories
- Shows more details in verbose mode

### 3. Utility Functions

Several utility functions handle common operations:
- `ensure_directories`: Creates necessary directories
- `check_dependencies`: Verifies Git, git-filter-repo, and Fossil are installed
- `cd`: Context manager for changing directories
- `is_fossil_repo_open`: Checks if a Fossil repository is currently open
- `validate_git_url` and `validate_subdir_name`: Input validation

## Technical Implementation

### Git Filter Operations

The tool relies heavily on `git-filter-repo` for two critical operations:

1. **Moving files to subdirectories**:
   ```python
   subprocess.run(['git-filter-repo', '--to-subdirectory-filter', subdir_name], check=True)
   ```
   This rewrites the Git history so that all files appear within a subdirectory.

2. **Branch Renaming**:
   After exploring more complex approaches (like custom Python callbacks), we opted for a straightforward Git branch renaming approach:
   ```python
   for branch in branches:
       if branch and not branch.startswith(f"{subdir_name}/"):
           subprocess.run(['git', 'branch', '-m', branch, f"{subdir_name}/{branch}"], check=True)
   ```

### Fossil Integration

The tool integrates with Fossil through direct command-line calls:

1. **Repository Creation and Opening**:
   ```python
   subprocess.run(['fossil', 'init', fossil_repo], check=True)
   subprocess.run(['fossil', 'open', fossil_repo], check=True)
   ```

2. **History Import**:
   ```python
   fossil_import = subprocess.Popen(
       ['fossil', 'import', '--git', '--incremental', '--export-marks', str(fossil_marks_file), 
        str(original_cwd / fossil_repo)],
       stdin=git_export.stdout
   )
   ```

3. **Branch Management**:
   ```python
   result = subprocess.run(['fossil', 'branch', 'list'], ...)
   subprocess.run(['fossil', 'update', main_branch], check=True)
   ```

### Pipeline Architecture

The import and update operations use a pipeline architecture with `subprocess.Popen` to directly connect Git export with Fossil import:

