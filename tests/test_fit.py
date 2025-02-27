import os
import pytest
import tempfile
import json
import shutil
from unittest.mock import patch, MagicMock, mock_open
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fit import fit

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        original_dir = os.getcwd()
        os.chdir(tmpdirname)
        yield tmpdirname
        os.chdir(original_dir)

@pytest.fixture
def mock_config():
    """Mock configuration data for testing."""
    return {
        "test_repo": {
            "git_repo_url": "https://github.com/user/repo.git",
            "git_clone_path": ".git_clones/test_repo",
            "git_marks_file": ".marks/test_repo_git.marks",
            "fossil_marks_file": ".marks/test_repo_fossil.marks"
        }
    }

def test_load_config_nonexistent(temp_dir):
    """Test loading a config that doesn't exist."""
    assert fit.load_config() == {}

def test_load_config_exists(temp_dir, mock_config):
    """Test loading a config that exists."""
    with open(fit.CONFIG_FILE, 'w') as f:
        json.dump(mock_config, f)
    
    assert fit.load_config() == mock_config

def test_save_config(temp_dir):
    """Test saving configuration."""
    test_config = {"test": "data"}
    fit.save_config(test_config)
    
    with open(fit.CONFIG_FILE, 'r') as f:
        saved_config = json.load(f)
    
    assert saved_config == test_config

def test_validate_git_url():
    """Test git URL validation."""
    assert fit.validate_git_url("https://github.com/user/repo.git") is True
    assert fit.validate_git_url("git@github.com:user/repo.git") is True
    assert fit.validate_git_url("ssh://git@github.com/user/repo.git") is True
    assert fit.validate_git_url("") is False
    assert fit.validate_git_url("invalid-url") is False

def test_validate_subdir_name():
    """Test subdirectory name validation."""
    assert fit.validate_subdir_name("valid_name") is True
    assert fit.validate_subdir_name("valid-name") is True
    assert fit.validate_subdir_name("valid.name") is True
    assert fit.validate_subdir_name("") is False
    assert fit.validate_subdir_name("/invalid") is False
    assert fit.validate_subdir_name("invalid/path") is False
    assert fit.validate_subdir_name(".invalid") is False

@patch('subprocess.run')
def test_init_fossil_repo(mock_run, temp_dir):
    """Test initialization of fossil repository."""
    fit.init_fossil_repo()
    mock_run.assert_called_once_with(['fossil', 'init', fit.FOSSIL_REPO], check=True)
    assert os.path.exists(fit.CONFIG_FILE)

@patch('fit.fit.import_git_repo')
def test_import_command(mock_import, temp_dir):
    """Test the import command in main function."""
    with patch('sys.argv', ['fit.py', 'import', 'https://github.com/user/repo.git', 'test_repo']):
        fit.main()
    mock_import.assert_called_once_with('https://github.com/user/repo.git', 'test_repo')

@patch('fit.fit.update_git_repo')
def test_update_command(mock_update, temp_dir):
    """Test the update command in main function."""
    with patch('sys.argv', ['fit.py', 'update', 'test_repo']):
        fit.main()
    mock_update.assert_called_once_with('test_repo')

@patch('fit.fit.list_repos')
def test_list_command(mock_list, temp_dir):
    """Test the list command in main function."""
    with patch('sys.argv', ['fit.py', 'list']):
        fit.main()
    mock_list.assert_called_once()

@patch('subprocess.run')
def test_check_dependencies(mock_run, temp_dir):
    """Test dependency checking."""
    mock_run.return_value = MagicMock(returncode=0)
    assert fit.check_dependencies() is True

    mock_run.side_effect = FileNotFoundError("Command not found")
    assert fit.check_dependencies() is False
