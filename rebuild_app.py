#!/usr/bin/env python3
"""
Rebuild the Nora application with a clean state.
This script sets up a fresh database schema and clears all temporary files.
"""

import os
import logging
import shutil
import subprocess
from clear_data import clear_database, clear_temp_files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_environment():
    """Check that all required environment variables are set"""
    required_vars = [
        "DATABASE_URL",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "PGHOST",
        "PGPORT"
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return False
    
    return True

def restart_server():
    """Restart the Gunicorn server"""
    logger.info("Attempting to restart the server...")
    
    try:
        # Find and kill existing gunicorn processes
        ps_output = subprocess.check_output(["ps", "aux"], universal_newlines=True)
        for line in ps_output.split('\n'):
            if 'gunicorn' in line and 'main:app' in line:
                pid = line.split()[1]
                logger.info(f"Stopping gunicorn process with PID {pid}")
                try:
                    subprocess.call(["kill", "-9", pid])
                except Exception as e:
                    logger.warning(f"Error stopping gunicorn process: {str(e)}")
        
        # Start the server
        logger.info("Starting gunicorn server...")
        subprocess.Popen(
            ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        return True
    except Exception as e:
        logger.error(f"Error restarting server: {str(e)}")
        return False

def rebuild_app():
    """Rebuild the application with a clean state"""
    
    if not verify_environment():
        logger.error("Environment check failed. Aborting rebuild.")
        return False
    
    # Step 1: Clear the database
    logger.info("Clearing database...")
    if not clear_database():
        logger.error("Failed to clear database. Aborting rebuild.")
        return False
    
    # Step 2: Clear temporary files
    logger.info("Clearing temporary files...")
    if not clear_temp_files():
        logger.warning("Failed to clear some temporary files. Continuing anyway.")
    
    # Step 3: Verify Python modules are installed
    try:
        import flask
        import flask_sqlalchemy
        import sqlalchemy
        import psycopg2
        import pytesseract
        import numpy
        import spacy
        logger.info("All required Python modules are available")
    except ImportError as e:
        logger.error(f"Missing Python module: {str(e)}")
        logger.error("Make sure all required modules are installed before continuing")
        return False
    
    # Step 4: Restart the server
    logger.info("Restarting the server...")
    if not restart_server():
        logger.error("Failed to restart server. Manual restart required.")
        return False
    
    logger.info("Application rebuild completed successfully!")
    return True

if __name__ == "__main__":
    print("Nora Application Rebuild Utility")
    print("================================")
    print("This will reset the database and restart the application with a clean state.")
    print("USE WITH CAUTION - this will delete all your data!")
    print()
    
    confirm = input("Type 'REBUILD APP' to confirm and proceed: ")
    
    if confirm.strip() == "REBUILD APP":
        print("Proceeding with rebuild...")
        success = rebuild_app()
        if success:
            print("Rebuild completed successfully.")
            print("The application should now be running with a clean state.")
        else:
            print("Rebuild completed with some errors. Check the logs for details.")
    else:
        print("Operation canceled.")