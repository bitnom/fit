import os
import pytest
import sys
from unittest.mock import patch
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fitrepo import fitrepo

@patch('fitrepo.fitrepo.push_to_git')
def test_push_git_command(mock_push):
    """Test the push-git command with basic arguments."""
    with patch('sys.argv', ['fitrepo.py', 'push-git', 'test_repo']):
        fitrepo.main()
    mock_push.assert_called_once_with(
        'test_repo',
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        [],
        None  # message
    )

@patch('fitrepo.fitrepo.push_to_git')
def test_push_git_command_with_message(mock_push):
    """Test the push-git command with message argument."""
    with patch('sys.argv', ['fitrepo.py', 'push-git', 'test_repo', '-m', 'Test commit message']):
        fitrepo.main()
    mock_push.assert_called_once_with(
        'test_repo',
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        [],
        'Test commit message'
    )

@patch('fitrepo.fitrepo.reset_marks')
def test_reset_marks_command(mock_reset):
    """Test the reset-marks command."""
    with patch('sys.argv', ['fitrepo.py', 'reset-marks', 'test_repo']):
        fitrepo.main()
    mock_reset.assert_called_once_with(
        'test_repo',
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        []
    )

@patch('fitrepo.fitrepo.fix_git_status')
def test_fix_git_status_command(mock_fix):
    """Test the fix-git-status command."""
    with patch('sys.argv', ['fitrepo.py', 'fix-git-status', 'test_repo']):
        fitrepo.main()
    mock_fix.assert_called_once_with(
        'test_repo',
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        []
    )
