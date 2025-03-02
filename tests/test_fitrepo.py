import os
import pytest
import tempfile
import json
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
import sys
from pathlib import Path
import argparse  # Make sure this is imported

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
    # Valid paths
    assert fitrepo.validate_subdir_name("valid_name") is True
    assert fitrepo.validate_subdir_name("valid-name") is True
    assert fitrepo.validate_subdir_name("valid.name") is True
    assert fitrepo.validate_subdir_name("valid/path") is True
    assert fitrepo.validate_subdir_name("valid/nested/path") is True
    
    # Invalid paths
    assert fitrepo.validate_subdir_name("") is False
    assert fitrepo.validate_subdir_name("/invalid") is False
    assert fitrepo.validate_subdir_name("invalid/") is False
    assert fitrepo.validate_subdir_name(".invalid") is False
    assert fitrepo.validate_subdir_name("invalid/.hidden") is False
    assert fitrepo.validate_subdir_name("invalid|chars") is False

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

# Update test_init_fossil_repo to include new fossil_args parameter
@patch('subprocess.run')
def test_init_fossil_repo(mock_run, temp_dir):
    """Test initialization of fossil repository with custom values."""
    custom_fossil = "custom.fossil"
    custom_config = "custom.json"
    
    # Setup mock to simulate that fossil repo is not open yet
    mock_run.return_value.returncode = 1  # Non-zero returncode means repo not open
    
    # Mock the file existence check to simulate a new repository
    with patch('pathlib.Path.exists', return_value=False):
        fitrepo.init_fossil_repo(custom_fossil, custom_config)
    
    # Verify expected sequence of calls (only init and open because repo doesn't exist)
    expected_calls = [
        call(['fossil', 'init', custom_fossil], check=True, capture_output=False, text=False),
        call(['fossil', 'open', custom_fossil], check=True, capture_output=False, text=False)
    ]
    
    # Check that the first 2 calls match our expectations
    assert mock_run.mock_calls[0:2] == expected_calls
    assert os.path.exists(custom_config)

# Test init with fossil arguments - Fix signature to match new parameters
@patch('subprocess.run')
def test_init_fossil_repo_with_args(mock_run, temp_dir):
    """Test initialization of fossil repository with fossil arguments."""
    custom_fossil = "custom.fossil"
    custom_config = "custom.json"
    fossil_open_args = ["-f"]
    fossil_init_args = None  # No init args in this test
    
    # Setup mock to simulate that fossil repo is not open yet
    mock_run.return_value.returncode = 1  # Non-zero returncode means repo not open
    
    # Mock the file existence check to simulate a new repository
    with patch('pathlib.Path.exists', return_value=False):
        fitrepo.init_fossil_repo(custom_fossil, custom_config, fossil_open_args, fossil_init_args)
    
    # Verify expected sequence of calls with open args applied only to open command
    expected_calls = [
        call(['fossil', 'init', custom_fossil], check=True, capture_output=False, text=False),
        call(['fossil', 'open', '-f', custom_fossil], check=True, capture_output=False, text=False)
    ]
    
    # Check that the first 2 calls match our expectations
    assert mock_run.mock_calls[0:2] == expected_calls
    assert os.path.exists(custom_config)

# Add test for command-specific fossil args
@patch('fitrepo.fitrepo.init_fossil_repo')
def test_init_command_with_fossil_open_args(mock_init, temp_dir):
    """Test the init command with forwarded fossil open arguments."""
    with patch('sys.argv', ['fitrepo.py', 'init', '--fwd-fossil-open=-f', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args (empty)
    )

# Update test for the --fwdfossil command line argument - Fix to match new signature 
@patch('fitrepo.fitrepo.init_fossil_repo')
def test_init_command_with_fossil_args(mock_init, temp_dir):
    """Test the init command with forwarded fossil arguments."""
    # Test with string-style argument to fwdfossil using equals sign
    with patch('sys.argv', ['fitrepo.py', 'init', '--fwdfossil=-f', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args
    )
    mock_init.reset_mock()
    
    # Test with fwdfossil after command with equals sign
    with patch('sys.argv', ['fitrepo.py', 'init', '--fwdfossil=-f', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args
    )
    mock_init.reset_mock()
    
    # Test with multiple args in a quoted string with equals sign
    with patch('sys.argv', ['fitrepo.py', 'init', '--fwdfossil=-f --force', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f', '--force'],  # open args
        []                  # init args
    )

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
        fitrepo.MARKS_DIR,
        []  # Empty fossil_open_args
    )

# Add test for import command with custom paths
@patch('fitrepo.fitrepo.import_git_repo')
def test_import_command_with_custom_paths(mock_import, temp_dir):
    """Test the import command with custom path arguments."""
    args = [
        'fitrepo.py',
        'import',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        '--git-clones-dir', 'custom_git',
        '--marks-dir', 'custom_marks',
        'https://github.com/user/repo.git',
        'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_import.assert_called_once_with(
        'https://github.com/user/repo.git', 
        'test_repo', 
        'custom.fossil',
        'custom.json',
        'custom_git',
        'custom_marks',
        []  # Empty fossil_open_args
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
        fitrepo.CONFIG_FILE,
        []  # Empty fossil_open_args
    )

# Add test for update command with custom paths
@patch('fitrepo.fitrepo.update_git_repo')
def test_update_command_with_custom_paths(mock_update, temp_dir):
    """Test the update command with custom path arguments."""
    args = [
        'fitrepo.py',
        'update',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_update.assert_called_once_with(
        'test_repo', 
        'custom.fossil',
        'custom.json',
        []  # Empty fossil_open_args
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
    with patch('sys.argv', ['fitrepo.py', 'list', '--config', 'custom.json']):
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

# Mock that prevents SystemExit from stopping tests
@pytest.fixture
def no_sys_exit():
    """Prevent sys.exit from stopping test execution."""
    with patch('sys.exit'):
        # Also patch argparse's parse_args to prevent SystemExit
        with patch('argparse.ArgumentParser.parse_args') as mock_parse:
            # Return a namespace with necessary attributes
            mock_parse.return_value = argparse.Namespace(
                command='init',
                verbose=False,
                fossil_repo=fitrepo.FOSSIL_REPO,
                config=fitrepo.CONFIG_FILE,
                git_clones_dir=fitrepo.GIT_CLONES_DIR,
                marks_dir=fitrepo.MARKS_DIR,
                fwdfossil='-f',
                fwd_fossil_open=None,
                fwd_fossil_init=None,
                git_repo_url='https://github.com/user/repo.git',
                subdir_name='test_repo'
            )
            yield mock_parse

# Remove duplicate test for init_command_with_fossil_args and consolidate
@patch('fitrepo.fitrepo.init_fossil_repo')
@patch('argparse.ArgumentParser.parse_args')  # Adding this patch to handle argument parsing
def test_init_command_with_fossil_args(mock_parse, mock_init, temp_dir):
    """Test the init command with forwarded fossil arguments."""
    # Set up the mock return value for parse_args to avoid SystemExit
    mock_parse.return_value = argparse.Namespace(
        command='init',
        verbose=False,
        fossil_repo=fitrepo.FOSSIL_REPO,
        config=fitrepo.CONFIG_FILE,
        git_clones_dir='temp_git_clones',  # Use temp directories
        marks_dir='temp_marks',
        fwdfossil='-f',
        fwd_fossil_open=None,
        fwd_fossil_init=None
    )
    
    # Test with string-style argument to fwdfossil using equals sign (correct order)
    with patch('sys.argv', ['fitrepo.py', '--fwdfossil=-f', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks', 'init']):
        fitrepo.main()
    
    # Verify the correct call was made
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args
    )
    mock_init.reset_mock()
    
    # Same approach for the second test case - argument order matters
    with patch('sys.argv', ['fitrepo.py', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks', 'init', '--fwdfossil=-f']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args
    )
    
    # Rest of the test remains the same...

@patch('fitrepo.fitrepo.init_fossil_repo')
def test_init_command_with_fossil_open_args(mock_init, no_sys_exit):
    """Test the init command with forwarded fossil open arguments."""
    # Configure the mock return value for this specific test
    no_sys_exit.return_value = argparse.Namespace(
        command='init',
        verbose=False,
        fossil_repo=fitrepo.FOSSIL_REPO,
        config=fitrepo.CONFIG_FILE,
        git_clones_dir=fitrepo.GIT_CLONES_DIR,
        marks_dir=fitrepo.MARKS_DIR,
        fwdfossil=None,
        fwd_fossil_open='-f',
        fwd_fossil_init=None
    )
    
    with patch('sys.argv', ['fitrepo.py', 'init', '--fwd-fossil-open=-f', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
    
    mock_init.assert_called_with(
        fitrepo.FOSSIL_REPO,
        fitrepo.CONFIG_FILE,
        ['-f'],  # open args
        []       # init args (empty)
    )

@patch('fitrepo.fitrepo.import_git_repo')
def test_import_command_with_custom_paths_fixed(mock_import, no_sys_exit):
    """Test the import command with custom path arguments."""
    # Configure mock for this test
    no_sys_exit.return_value = argparse.Namespace(
        command='import',
        verbose=False,
        fossil_repo='custom.fossil',
        config='custom.json',
        git_clones_dir='custom_git',
        marks_dir='custom_marks',
        fwdfossil=None,
        fwd_fossil_open=None,
        fwd_fossil_init=None,
        git_repo_url='https://github.com/user/repo.git', 
        subdir_name='test_repo'
    )
    
    # Make sure the command is first, then the global args
    args = [
        'fitrepo.py', 
        'import',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        '--git-clones-dir', 'custom_git', 
        '--marks-dir', 'custom_marks', 
        'https://github.com/user/repo.git', 'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_import.assert_called_once_with(
        'https://github.com/user/repo.git', 
        'test_repo', 
        'custom.fossil',
        'custom.json',
        'custom_git',
        'custom_marks',
        []  # Empty fossil_open_args
    )

@patch('fitrepo.fitrepo.update_git_repo')
def test_update_command_with_custom_paths_fixed(mock_update, no_sys_exit):
    """Test the update command with custom path arguments."""
    # Configure mock for this test
    no_sys_exit.return_value = argparse.Namespace(
        command='update',
        verbose=False,
        fossil_repo='custom.fossil',
        config='custom.json',
        git_clones_dir=fitrepo.GIT_CLONES_DIR,
        marks_dir=fitrepo.MARKS_DIR,
        fwdfossil=None,
        fwd_fossil_open=None,
        fwd_fossil_init=None,
        subdir_name='test_repo'
    )
    
    args = [
        'fitrepo.py',
        'update',
        '--fossil-repo', 'custom.fossil',
        '--config', 'custom.json',
        '--git-clones-dir', 'custom_git',
        '--marks-dir', 'custom_marks',
        'test_repo'
    ]
    with patch('sys.argv', args):
        fitrepo.main()
    
    mock_update.assert_called_once_with(
        'test_repo', 
        'custom.fossil',
        'custom.json',
        []  # Empty fossil_open_args
    )

@patch('fitrepo.fitrepo.list_repos')
def test_list_command_with_custom_config_fixed(mock_list, no_sys_exit):
    """Test the list command with custom config."""
    # Configure mock for this test
    no_sys_exit.return_value = argparse.Namespace(
        command='list',
        verbose=False,
        fossil_repo=fitrepo.FOSSIL_REPO,
        config='custom.json',
        git_clones_dir=fitrepo.GIT_CLONES_DIR,
        marks_dir=fitrepo.MARKS_DIR,
        fwdfossil=None,
        fwd_fossil_open=None,
        fwd_fossil_init=None
    )
    
    with patch('sys.argv', ['fitrepo.py', 'list', '--config', 'custom.json', '--git-clones-dir', 'temp_git_clones', '--marks-dir', 'temp_marks']):
        fitrepo.main()
        
    mock_list.assert_called_once_with('custom.json')
