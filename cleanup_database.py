#!/usr/bin/env python3
"""
Utility script to clean up the database and remove all stored screenshots.
USE WITH CAUTION - this will permanently delete all screenshot data.
"""

import os
import sqlite3
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_database():
    """Clean up the database by removing all screenshot records"""
    db_path = os.path.join("instance", "screenshots.db")
    
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get count of screenshots
        cursor.execute("SELECT COUNT(*) FROM screenshot")
        count = cursor.fetchone()[0]
        
        # Delete all screenshots
        cursor.execute("DELETE FROM screenshot")
        conn.commit()
        
        logger.info(f"Removed {count} screenshots from the database")
        
        # Close connection
        conn.close()
    except Exception as e:
        logger.error(f"Error cleaning up database: {str(e)}")

def cleanup_screenshot_files():
    """Clean up actual screenshot files in the screenshots folder"""
    screenshots_folder = "./screenshots"
    
    if not os.path.exists(screenshots_folder):
        logger.warning(f"Screenshots folder not found at {screenshots_folder}")
        return
    
    try:
        # Count files
        file_count = 0
        for file_path in Path(screenshots_folder).glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                file_count += 1
                os.remove(file_path)
        
        logger.info(f"Removed {file_count} screenshot files from {screenshots_folder}")
    except Exception as e:
        logger.error(f"Error cleaning up screenshot files: {str(e)}")

if __name__ == "__main__":
    print("DATABASE CLEANUP UTILITY")
    print("========================")
    print("WARNING: This will permanently delete all stored screenshots!")
    print()
    
    confirm = input("Type 'YES' to confirm and proceed with deletion: ")
    
    if confirm.strip().upper() == "YES":
        print("Proceeding with cleanup...")
        
        # Clean up database
        cleanup_database()
        
        # Clean up screenshot files
        cleanup_screenshot_files()
        
        print("Cleanup complete.")
    else:
        print("Operation canceled.")