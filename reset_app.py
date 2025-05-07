#!/usr/bin/env python3
"""
Reset functionality for Nora.
This script provides a simple way to reset the application state.
"""

import os
import logging
import shutil
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the SQLite database by removing all screenshots"""
    db_path = os.path.join("instance", "screenshots.db")
    
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the screenshot table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='screenshot'")
        if cursor.fetchone():
            # Get count of screenshots
            cursor.execute("SELECT COUNT(*) FROM screenshot")
            count = cursor.fetchone()[0]
            
            # Delete all screenshots
            cursor.execute("DELETE FROM screenshot")
            conn.commit()
            
            logger.info(f"Removed {count} screenshots from the database")
        else:
            logger.info("No screenshot table found in database")
        
        # Close connection
        conn.close()
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")

def clear_temp_files():
    """Clear temporary files in the temp_uploads folder"""
    temp_folder = "temp_uploads"
    
    if os.path.exists(temp_folder):
        try:
            file_count = 0
            for filename in os.listdir(temp_folder):
                file_path = os.path.join(temp_folder, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    file_count += 1
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            
            logger.info(f"Cleared {file_count} files from temp folder")
        except Exception as e:
            logger.error(f"Error clearing temp folder: {str(e)}")
    else:
        logger.warning(f"Temp folder {temp_folder} not found")

def reset_app():
    """Reset the entire application state"""
    # Reset database
    reset_database()
    
    # Clear temp files
    clear_temp_files()
    
    logger.info("App reset complete")

if __name__ == "__main__":
    print("Nora App Reset Tool")
    print("==================")
    print("This will clear all screenshots from the database and temporary folders.")
    print()
    
    confirm = input("Type 'YES' to confirm and proceed with reset: ")
    
    if confirm.strip().upper() == "YES":
        print("Proceeding with reset...")
        reset_app()
        print("Reset complete.")
    else:
        print("Operation canceled.")