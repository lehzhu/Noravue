#!/usr/bin/env python3
"""
Launch the new session-based privacy-focused version of Nora.
This version does not store screenshots in a central database - all data
is temporary and session-based, and is automatically cleared when the browser
session ends.
"""

import os
import sys
import shutil
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_temp_folder():
    """Create the temporary folder for session data"""
    temp_folder = "temp_uploads"
    if os.path.exists(temp_folder):
        # Clear any existing files
        try:
            for filename in os.listdir(temp_folder):
                file_path = os.path.join(temp_folder, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            logger.info(f"Cleared existing temp folder: {temp_folder}")
        except Exception as e:
            logger.error(f"Error clearing temp folder: {str(e)}")
    else:
        try:
            os.makedirs(temp_folder)
            logger.info(f"Created temp folder: {temp_folder}")
        except Exception as e:
            logger.error(f"Error creating temp folder: {str(e)}")
            sys.exit(1)

def launch_session_app():
    """Launch the session-based privacy-focused version of Nora"""
    try:
        # Make sure temp folder exists
        create_temp_folder()
        
        # Run the app
        cmd = ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main_session:app"]
        process = subprocess.Popen(cmd)
        
        logger.info("Started the session-based privacy version of Nora")
        logger.info("All user data is now temporary and will be cleared after the browser session ends")
        
        # Wait for the process to end (Ctrl+C will stop it)
        process.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error launching app: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("Launching Privacy-Focused Session Mode")
    print("======================================")
    print("This version of Nora does not store any screenshots or data permanently.")
    print("All data is temporary and will be cleared when your browser session ends.")
    print("Use this mode for maximum privacy and data protection.")
    print()
    
    launch_session_app()