#!/usr/bin/env python3
"""
Command line tools for fitrepo
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from .fix_git_index import fix_git_index

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def main_fix_git():
    """Command line entry point for fix-git-status"""
    parser = argparse.ArgumentParser(description='Fix Git index for monorepo directories')
    parser.add_argument('target_dir', help='Directory containing the Git checkout')
    parser.add_argument('-g', '--git-dir', help='Path to the Git directory if not target_dir/.git')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Create absolute paths for reliability
        target_dir = os.path.abspath(args.target_dir)
        git_dir = args.git_dir if args.git_dir else None
        
        logger.info(f"Fixing Git index in {target_dir}...")
        fix_git_index(target_dir, git_dir)
        logger.info("Git index fix completed successfully.")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main_fix_git())
