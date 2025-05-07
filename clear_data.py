#!/usr/bin/env python3
"""
Simple utility script to directly clear all data in the database and file system.
This script is used when the web interface cleanup function is not working properly.
"""

import os
import shutil
import logging
import psycopg2
from urllib.parse import urlparse
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get a database connection from environment variables"""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        return None
    
    try:
        # Parse the DATABASE_URL
        parsed = urlparse(db_url)
        username = parsed.username
        password = parsed.password
        database = parsed.path[1:]
        hostname = parsed.hostname
        port = parsed.port
        
        # Create connection
        conn = psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        logger.info("Connected to the PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return None

def clear_database():
    """Truncate all tables in the database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Get all table names
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        if not tables:
            logger.info("No tables found in the database")
            return True
        
        # Truncate each table
        for table in tables:
            logger.info(f"Truncating table {table}")
            cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        
        logger.info(f"Successfully truncated {len(tables)} tables")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error truncating database: {str(e)}")
        if conn:
            conn.close()
        return False

def clear_temp_files():
    """Clear all temporary files"""
    temp_dirs = ['temp_uploads']
    screenshots_dir = './screenshots'
    
    try:
        # Clear temp_uploads folder
        for directory in temp_dirs:
            if os.path.exists(directory):
                for file_name in os.listdir(directory):
                    file_path = os.path.join(directory, file_name)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f"Error removing {file_path}: {str(e)}")
                
                logger.info(f"Cleared directory: {directory}")
        
        # We don't want to delete the screenshots folder, just clear it
        if os.path.exists(screenshots_dir):
            # Keep only a handful of the original screenshots to show functionality
            keep_files = []
            files_to_remove = []
            
            # List all files and sort them (keep 10 smallest files for demo)
            all_files = []
            for file_name in os.listdir(screenshots_dir):
                file_path = os.path.join(screenshots_dir, file_name)
                if os.path.isfile(file_path):
                    all_files.append((file_path, os.path.getsize(file_path)))
            
            # Sort by file size
            all_files.sort(key=lambda x: x[1])
            
            # Keep 10 smallest files, remove the rest
            keep_files = [file_path for file_path, _ in all_files[:10]]
            files_to_remove = [file_path for file_path, _ in all_files[10:]]
            
            # Remove files
            for file_path in files_to_remove:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error removing {file_path}: {str(e)}")
            
            logger.info(f"Cleared screenshots directory, kept {len(keep_files)} files for demo")
        
        return True
    except Exception as e:
        logger.error(f"Error clearing temp files: {str(e)}")
        return False

def reset_everything():
    """Reset the entire application state"""
    db_status = clear_database()
    files_status = clear_temp_files()
    
    return db_status and files_status

if __name__ == "__main__":
    print("Database and File Reset Utility")
    print("==============================")
    print("This will clear all data from the database and temporary files.")
    print("USE WITH CAUTION - this will delete all your data!")
    print()
    
    confirm = input("Type 'DELETE EVERYTHING' to confirm and proceed: ")
    
    if confirm.strip() == "DELETE EVERYTHING":
        print("Proceeding with reset...")
        success = reset_everything()
        if success:
            print("Reset completed successfully.")
        else:
            print("Reset completed with some errors. Check the logs for details.")
    else:
        print("Operation canceled.")