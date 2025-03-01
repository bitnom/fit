#!/usr/bin/env python3

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import unittest

class GitIsolationTest(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for our test
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        
        # Setup simple Git repositories for testing
        self.repo1_dir = os.path.join(self.test_dir, "repo1")
        self.repo2_dir = os.path.join(self.test_dir, "repo2")
        
        # Create test repositories
        self._setup_test_repo(self.repo1_dir, "repo1")
        self._setup_test_repo(self.repo2_dir, "repo2")
        
    def tearDown(self):
        # Return to original directory and clean up
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)
    
    def _setup_test_repo(self, repo_dir, name):
        """Set up a test Git repository with some files"""
        os.makedirs(repo_dir)
        os.chdir(repo_dir)
        
        # Initialize Git repo
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        
        # Create a test file
        with open(f"{name}.txt", "w") as f:
            f.write(f"This is a test file for {name}\n")
        
        # Commit the file
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"Initial commit for {name}"], check=True)
        
    def test_git_worktree_isolation(self):
        """Test that our worktree isolation approach works correctly"""
        # Create a directory structure to test isolation
        monorepo_dir = os.path.join(self.test_dir, "monorepo")
        os.makedirs(monorepo_dir)
        os.chdir(monorepo_dir)
        
        # Setup the worktree for repo1
        subdir1 = os.path.join(monorepo_dir, "subdir1")
        os.makedirs(subdir1)
        
        # Create .git file that points to the actual repo
        with open(os.path.join(subdir1, ".git"), "w") as f:
            f.write(f"gitdir: {os.path.relpath(self.repo1_dir, subdir1)}/.git")
        
        # Configure the git repo to use this worktree
        os.chdir(self.repo1_dir)
        subprocess.run(["git", "config", "core.worktree", 
                        os.path.relpath(subdir1, os.path.join(self.repo1_dir, ".git"))], check=True)
        
        # Set up sparse checkout
        subprocess.run(["git", "config", "core.sparseCheckout", "true"], check=True)
        sparse_checkout_dir = os.path.join(self.repo1_dir, ".git", "info")
        os.makedirs(sparse_checkout_dir, exist_ok=True)
        with open(os.path.join(sparse_checkout_dir, "sparse-checkout"), "w") as f:
            f.write("/*\n")
        
        # Create an untracked file in the parent directory
        with open(os.path.join(monorepo_dir, "outside.txt"), "w") as f:
            f.write("This file is outside the subdirectory\n")
        
        # Now check git status from the subdirectory
        os.chdir(subdir1)
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        
        # The status should not show the outside.txt file
        self.assertNotIn("outside.txt", result.stdout)
        
        # Create a new file in the subdir and check status again
        with open(os.path.join(subdir1, "new_file.txt"), "w") as f:
            f.write("New file in subdir\n")
            
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        self.assertIn("new_file.txt", result.stdout)
        
if __name__ == "__main__":
    unittest.main()
