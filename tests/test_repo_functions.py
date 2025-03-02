import os
import pytest
import tempfile
import sys
from unittest.mock import patch, mock_open, MagicMock, call
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fitrepo import fitrepo

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        original_dir = os.getcwd()
        os.chdir(tmpdirname)
        yield tmpdirname
        os.chdir(original_dir)

@patch('fitrepo.fitrepo.run_command')
def test_process_git_repo(mock_run_command, temp_dir):
    """Test the process_git_repo function."""
    # Setup
    git_clone_path = Path(temp_dir) / "clone"
    git_clone_path.mkdir()
    subdir_path = "test_subdir"
    
    # Configure mock to simulate branch listing
    branch_result = MagicMock()
    branch_result.stdout = "* master\n  feature\n"
    
    # Configure mock to simulate branches not existing yet
    show_ref_result = MagicMock()
    show_ref_result.returncode = 1  # Non-zero means branch doesn't exist
    
    # Define side effect to return different results for different commands
    def side_effect(cmd, **kwargs):
        if cmd[0] == 'git' and cmd[1] == 'branch' and kwargs.get('capture_output'):
            return branch_result
        if cmd[0] == 'git' and cmd[1] == 'show-ref':
            return show_ref_result
        return MagicMock(returncode=0)
        
    mock_run_command.side_effect = side_effect
    
    # Call the function
    fitrepo.process_git_repo(git_clone_path, subdir_path)
    
    # Create list of essential calls we want to verify
    expected_calls = [
        # First call is git-filter-repo
        call(['git-filter-repo', '--to-subdirectory-filter', 'test_subdir']),
        # Second call is git branch to list branches
        call(['git', 'branch'], capture_output=True, text=True),
        # These calls should be for checking if branches exist and renaming them
        call(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/test_subdir/master'], check=False),
        call(['git', 'branch', '-m', 'master', 'test_subdir/master']),
        call(['git', 'show-ref', '--verify', '--quiet', 'refs/heads/test_subdir/feature'], check=False),
        call(['git', 'branch', '-m', 'feature', 'test_subdir/feature'])
    ]
    
    # Verify the important calls were made in the correct order
    for i, expected in enumerate(expected_calls):
        assert mock_run_command.call_args_list[i] == expected

@patch('subprocess.Popen')
def test_export_import_git_to_fossil(mock_popen, temp_dir):
    """Test the export_import_git_to_fossil function."""
    # Setup
    subdir_path = "test_subdir"
    git_marks_file = Path(temp_dir) / "git.marks"
    fossil_marks_file = Path(temp_dir) / "fossil.marks"
    fossil_repo = Path(temp_dir) / "repo.fossil"
    
    # Mock subprocess.Popen instances
    mock_git_process = MagicMock()
    mock_fossil_process = MagicMock()
    mock_fossil_process.returncode = 0
    
    # Configure mock to return the appropriate process objects
    mock_popen.side_effect = [mock_git_process, mock_fossil_process]
    
    # Call without import marks
    fitrepo.export_import_git_to_fossil(subdir_path, git_marks_file, fossil_marks_file, fossil_repo)
    
    # Verify calls
    expected_git_cmd = ['git', 'fast-export', '--all', '--export-marks', str(git_marks_file)]
    expected_fossil_cmd = [
        'fossil', 'import', '--git', '--incremental', 
        '--export-marks', str(fossil_marks_file), str(fossil_repo)
    ]
    
    assert mock_popen.call_args_list[0][0][0] == expected_git_cmd
    assert mock_popen.call_args_list[1][0][0] == expected_fossil_cmd
    
    # Reset mock and test with import marks
    mock_popen.reset_mock()
    mock_popen.side_effect = [mock_git_process, mock_fossil_process]
    
    # Create marks files to test import behavior
    git_marks_file.touch()
    fossil_marks_file.touch()
    
    # Call with import marks
    fitrepo.export_import_git_to_fossil(subdir_path, git_marks_file, fossil_marks_file, fossil_repo, import_marks=True)
    
    # Verify updated calls with import marks
    expected_git_cmd = [
        'git', 'fast-export', '--all', '--import-marks', str(git_marks_file),
        '--export-marks', str(git_marks_file)
    ]
    expected_fossil_cmd = [
        'fossil', 'import', '--git', '--incremental', '--import-marks', str(fossil_marks_file),
        '--export-marks', str(fossil_marks_file), str(fossil_repo)
    ]
    
    assert mock_popen.call_args_list[0][0][0] == expected_git_cmd
    assert mock_popen.call_args_list[1][0][0] == expected_fossil_cmd

@patch('fitrepo.fitrepo.cd')
@patch('fitrepo.fitrepo.run_command')
def test_setup_git_worktree(mock_run_command, mock_cd, temp_dir):
    """Test the setup_git_worktree function."""
    # Setup
    git_clone_path = Path(temp_dir) / "clone"
    target_dir = Path(temp_dir) / "target"
    norm_path = "test_subdir"
    
    # Call the function
    with patch('builtins.open', mock_open()) as mock_file:
        with patch('os.makedirs') as mock_makedirs:
            fitrepo.setup_git_worktree(git_clone_path, target_dir, norm_path)
    
    # Verify git config operations
    worktree_call = call(['git', 'config', 'core.worktree', os.path.abspath(target_dir)])
    sparse_checkout_call = call(['git', 'config', 'core.sparseCheckout', 'true'])
    untracked_files_call = call(['git', 'config', 'status.showUntrackedFiles', 'no'])
    
    # Check that the essential commands were called
    assert worktree_call in mock_run_command.mock_calls, "core.worktree not configured"
    assert sparse_checkout_call in mock_run_command.mock_calls, "core.sparseCheckout not set to true"
    assert untracked_files_call in mock_run_command.mock_calls, "status.showUntrackedFiles not set to no"
