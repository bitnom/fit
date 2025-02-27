import os
import pytest
import tempfile
import json
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fitrepo import fitrepo

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for testing and ensure cleanup."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        original_dir = os.getcwd()
        os.chdir(tmpdirname)
        
        # Create temporary directories for test artifacts
        Path('temp_git_clones').mkdir(exist_ok=True)
        Path('temp_marks').mkdir(exist_ok=True)
        
        # Patch the constants to use our temporary directories
        with patch.object(fitrepo, 'GIT_CLONES_DIR', 'temp_git_clones'), \
             patch.object(fitrepo, 'MARKS_DIR', 'temp_marks'):
            
            yield tmpdirname
            
        # Cleanup (although tempfile will delete the directory, this ensures
        # files are removed even if we change to a non-tempfile approach)
        if Path('temp_git_clones').exists():
            shutil.rmtree('temp_git_clones', ignore_errors=True)
        if Path('temp_marks').exists():
            shutil.rmtree('temp_marks', ignore_errors=True)
            
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

@pytest.fixture(autouse=True)
def prevent_external_calls():
    """Prevent any test from making external subprocess calls accidentally."""
    with patch('subprocess.Popen'):
        with patch('subprocess.run'):
            yield

def test_load_config_nonexistent(temp_dir):
    """Test loading a config that doesn't exist."""
    assert fitrepo.load_config() == {}

def test_load_config_exists(temp_dir, mock_config):
    """Test loading a config that exists."""
    with open(fitrepo.CONFIG_FILE, 'w') as f:
        json.dump(mock_config, f)
    
    assert fitrepo.load_config() == mock_config

def test_save_config(temp_dir):
    """Test saving configuration."""
    test_config = {"test": "data"}
    fitrepo.save_config(test_config)
    
    with open(fitrepo.CONFIG_FILE, 'r') as f:
        saved_config = json.load(f)
    
    assert saved_config == test_config

def test_validate_git_url():
    """Test git URL validation."""
    assert fitrepo.validate_git_url("https://github.com/user/repo.git") is True
    assert fitrepo.validate_git_url("git@github.com:user/repo.git") is True
    assert fitrepo.validate_git_url("ssh://git@github.com/user/repo.git") is True
    assert fitrepo.validate_git_url("") is False
    assert fitrepo.validate_git_url("invalid-url") is False

def test_validate_subdir_name():
    """Test subdirectory name validation."""
    assert fitrepo.validate_subdir_name("valid_name") is True
    assert fitrepo.validate_subdir_name("valid-name") is True
    assert fitrepo.validate_subdir_name("valid.name") is True
    assert fitrepo.validate_subdir_name("") is False
    assert fitrepo.validate_subdir_name("/invalid") is False
    assert fitrepo.validate_subdir_name("invalid/path") is False
    assert fitrepo.validate_subdir_name(".invalid") is False

# Test the new ensure_directories function
def test_ensure_directories(temp_dir):
    """Test that directories are created as expected."""
    test_git_dir = "test_git_dir"
    test_marks_dir = "test_marks_dir"
    
    # Ensure the directories don't exist first
    assert not os.path.exists(test_git_dir)
    assert not os.path.exists(test_marks_dir)
    
    fitrepo.ensure_directories(test_git_dir, test_marks_dir)
    
    # Check that they were created
    assert os.path.exists(test_git_dir)
    assert os.path.exists(test_marks_dir)

# Update test_init_fossil_repo to include new parameters
@patch('subprocess.run')
def test_init_fossil_repo(mock_run, temp_dir):
    """Test initialization of fossil repository with custom values."""
    custom_fossil = "custom.fossil"
    custom_config = "custom.json"
    
    fitrepo.init_fossil_repo(custom_fossil, custom_config)
    
    mock_run.assert_called_once_with(['fossil', 'init', custom_fossil], check=True)
    assert os.path.exists(custom_config)

# Update test_import_command to match new parameter signature
@patch('fitrepo.fitrepo.import_git_repo')
def test_import_command(mock_import, temp_dir):
    """Test the import command in main function with default values."""
    with patch('sys.argv', ['fitrepo.py', 'import', 'https://github.com/user/repo.git', 'test_repo']):
        fitrepo.main()
    mock_import.assert_called_once_with(
        'https://github.com/user/repo.git', 
        'test_repo',
        fitrepo.FOSSIL_REPO, 
        fitrepo.CONFIG_FILE,
        fitrepo.GIT_CLONES_DIR, 
        fitrepo.MARKS_DIR
    )

# Add test for import command with custom paths
@patch('fitrepo.fitrepo.import_git_repo')
def test_import_command_with_custom_paths(mock_import, temp_dir):
    """Test the import command with custom path arguments."""
    args = [
        'fitrepo.py',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        '--git-clones-dir', 'custom_git',
        '--marks-dir', 'custom_marks',
        'import', 'https://github.com/user/repo.git', 'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_import.assert_called_once_with(
        'https://github.com/user/repo.git', 
        'test_repo', 
        'custom.fossil',
        'custom.json',
        'custom_git',
        'custom_marks'
    )

# Update test_update_command to match new parameter signature
@patch('fitrepo.fitrepo.update_git_repo')
def test_update_command(mock_update, temp_dir):
    """Test the update command in main function."""
    with patch('sys.argv', ['fitrepo.py', 'update', 'test_repo']):
        fitrepo.main()
    mock_update.assert_called_once_with(
        'test_repo',
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE
    )

# Add test for update command with custom paths
@patch('fitrepo.fitrepo.update_git_repo')
def test_update_command_with_custom_paths(mock_update, temp_dir):
    """Test the update command with custom path arguments."""
    args = [
        'fitrepo.py',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        'update', 'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_update.assert_called_once_with(
        'test_repo', 
        'custom.fossil',
        'custom.json'
    )

# Update list command test
@patch('fitrepo.fitrepo.list_repos')
def test_list_command(mock_list, temp_dir):
    """Test the list command in main function."""
    with patch('sys.argv', ['fitrepo.py', 'list']):
        fitrepo.main()
    mock_list.assert_called_once_with(fitrepo.CONFIG_FILE)

# Add test for list command with custom config
@patch('fitrepo.fitrepo.list_repos')
def test_list_command_with_custom_config(mock_list, temp_dir):
    """Test the list command with custom config."""
    with patch('sys.argv', ['fitrepo.py', '--config', 'custom.json', 'list']):
        fitrepo.main()
    mock_list.assert_called_once_with('custom.json')

@patch('subprocess.run')
def test_check_dependencies(mock_run, temp_dir):
    """Test dependency checking."""
    mock_run.return_value = MagicMock(returncode=0)
    assert fitrepo.check_dependencies() is True

    mock_run.side_effect = FileNotFoundError("Command not found")
    assert fitrepo.check_dependencies() is False

# Cleanup fixture that runs after all tests in this module
@pytest.fixture(scope="module", autouse=True)
def cleanup_after_all_tests():
    """Clean up any stray directories after all tests run."""
    yield
    # This runs after all tests in the module
    current_dir = os.getcwd()
    git_clones = Path(current_dir) / '.git_clones'
    marks = Path(current_dir) / '.marks'
    if git_clones.exists():
        shutil.rmtree(git_clones, ignore_errors=True)
    if marks.exists():
        shutil.rmtree(marks, ignore_errors=True)
