import pytest
import subprocess
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fitrepo import fitrepo

def test_run_command_subprocess_error():
    """Test error handling when a subprocess command fails."""
    # Mock subprocess.run to raise CalledProcessError
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ['test'], stderr="Mock error")
        
        # Verify the exception is re-raised
        with pytest.raises(subprocess.CalledProcessError):
            fitrepo.run_command(['test'])

def test_run_command_file_not_found():
    """Test error handling when a command is not found."""
    # Mock subprocess.run to raise FileNotFoundError
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'nonexistent'")
        
        # Verify the exception is re-raised
        with pytest.raises(FileNotFoundError):
            fitrepo.run_command(['nonexistent'])

@patch('fitrepo.fitrepo.setup_repo_operation')
def test_update_git_repo_missing_subdir(mock_setup):
    """Test error handling when trying to update a non-existent subdirectory."""
    # Setup mock to raise ValueError for non-existent subdir
    mock_setup.side_effect = ValueError("Subdirectory 'nonexistent' not found in configuration.")
    
    # Verify the exception is properly raised
    with pytest.raises(ValueError, match="not found in configuration"):
        fitrepo.update_git_repo('nonexistent')

def test_main_error_handling():
    """Test error handling in the main function for command failures."""
    # Use pytest's built-in functionality for testing sys.exit
    with patch('sys.argv', ['fitrepo.py', 'import', 'invalid', 'subdir']):
        with patch('fitrepo.fitrepo.import_git_repo') as mock_import:
            # Setup mock to raise an error
            mock_import.side_effect = ValueError("Invalid input parameters")
            
            # Use pytest's built-in handling of SystemExit
            with pytest.raises(SystemExit) as exit_info:
                fitrepo.main()
            
            # Verify exit code
            assert exit_info.value.code == 1
