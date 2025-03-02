import os
import pytest
import tempfile
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fitrepo import fitrepo

def test_cd_context_manager():
    """Test the cd() context manager changes directory and restores it."""
    # Setup
    original_dir = os.getcwd()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Verify the context manager changes directory
        with fitrepo.cd(temp_dir):
            assert os.getcwd() == temp_dir
        
        # Verify directory is restored after context exit
        assert os.getcwd() == original_dir
        
        # Verify directory is restored even if an exception occurs
        try:
            with fitrepo.cd(temp_dir):
                assert os.getcwd() == temp_dir
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass
        
        assert os.getcwd() == original_dir
