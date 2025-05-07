import os
import uuid
import datetime
import logging
import shutil
import tempfile
import pytesseract
from PIL import Image
from flask import session, current_app
from typing import List, Dict, Optional, Tuple
import nlp_analyzer
import random

# Configure logging
logger = logging.getLogger(__name__)

class SessionScreenshot:
    """In-memory screenshot class for session-based storage"""
    def __init__(
        self,
        id: str,
        filename: str,
        path: str,
        text_content: str,
        priority_score: float,
        urgency_score: float,
        action_score: float,
        dismissed: bool = False
    ):
        self.id = id
        self.filename = filename
        self.path = path
        self.text_content = text_content
        self.priority_score = priority_score
        self.urgency_score = urgency_score
        self.action_score = action_score
        self.dismissed = dismissed
        self.deferred_until = None
        self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()
    
    def is_active(self) -> bool:
        """
        Determines if a screenshot should be shown in the current view.
        It's active if it hasn't been dismissed and isn't currently deferred.
        """
        if self.dismissed:
            return False
        
        if self.deferred_until and self.deferred_until > datetime.datetime.utcnow():
            return False
            
        return True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'filename': self.filename,
            'path': self.path,
            'text_content': self.text_content,
            'priority_score': self.priority_score,
            'urgency_score': self.urgency_score,
            'action_score': self.action_score,
            'dismissed': self.dismissed,
            'deferred_until': self.deferred_until.isoformat() if self.deferred_until else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class SessionManager:
    """Manages session-based screenshot storage"""
    
    def __init__(self, app=None):
        self.app = app
        self.temp_folder = "temp_uploads"
        if app:
            self.init_app(app)
            
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        
        # Create temp folder if it doesn't exist
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)
            
        # Register a cleanup function to run when the app terminates
        @app.teardown_appcontext
        def cleanup_temp_files(exception=None):
            self._cleanup_old_files()
    
    def _ensure_session_initialized(self):
        """Ensure session variables are initialized"""
        if 'screenshots' not in session:
            session['screenshots'] = []
        if 'dismissed_screenshots' not in session:
            session['dismissed_screenshots'] = []
            
    def get_active_screenshots(self) -> List[Dict]:
        """Get all active screenshots for the current session"""
        self._ensure_session_initialized()
        
        # Convert stored dict data back to SessionScreenshot objects
        screenshots = []
        for screenshot_data in session.get('screenshots', []):
            screenshot = self._dict_to_screenshot(screenshot_data)
            if screenshot.is_active():
                screenshots.append(screenshot.to_dict())
                
        # Sort by priority score, highest first
        screenshots.sort(key=lambda x: x['priority_score'], reverse=True)
        return screenshots
    
    def get_dismissed_screenshots(self) -> List[Dict]:
        """Get all dismissed screenshots for the current session"""
        self._ensure_session_initialized()
        
        dismissed = []
        for screenshot_data in session.get('dismissed_screenshots', []):
            screenshot = self._dict_to_screenshot(screenshot_data)
            dismissed.append(screenshot.to_dict())
            
        return dismissed
    
    def dismiss_screenshot(self, screenshot_id: str) -> bool:
        """Mark a screenshot as dismissed"""
        self._ensure_session_initialized()
        
        screenshots = session.get('screenshots', [])
        for i, screenshot_data in enumerate(screenshots):
            if screenshot_data.get('id') == screenshot_id:
                # Remove from active list
                screenshot_data = screenshots.pop(i)
                # Add to dismissed list
                session['dismissed_screenshots'] = session.get('dismissed_screenshots', []) + [screenshot_data]
                session.modified = True
                return True
        return False
    
    def restore_screenshot(self, screenshot_id: str) -> bool:
        """Restore a dismissed screenshot"""
        self._ensure_session_initialized()
        
        dismissed = session.get('dismissed_screenshots', [])
        for i, screenshot_data in enumerate(dismissed):
            if screenshot_data.get('id') == screenshot_id:
                # Remove from dismissed list
                screenshot_data = dismissed.pop(i)
                # Set dismissed flag to False
                screenshot_data['dismissed'] = False
                # Add back to active list
                session['screenshots'] = session.get('screenshots', []) + [screenshot_data]
                session.modified = True
                return True
        return False
    
    def defer_screenshot(self, screenshot_id: str, minutes: int = 30) -> bool:
        """Defer a screenshot for later viewing"""
        self._ensure_session_initialized()
        
        screenshots = session.get('screenshots', [])
        for i, screenshot_data in enumerate(screenshots):
            if screenshot_data.get('id') == screenshot_id:
                # Set deferred_until time
                deferred_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
                screenshot_data['deferred_until'] = deferred_time.isoformat()
                screenshot_data['updated_at'] = datetime.datetime.utcnow().isoformat()
                session.modified = True
                return True
        return False
    
    def dismiss_all_screenshots(self) -> int:
        """Dismiss all active screenshots"""
        self._ensure_session_initialized()
        
        screenshots = session.get('screenshots', [])
        active_screenshots = []
        dismissed_count = 0
        
        for screenshot_data in screenshots:
            screenshot = self._dict_to_screenshot(screenshot_data)
            if screenshot.is_active():
                # Mark as dismissed
                screenshot_data['dismissed'] = True
                session['dismissed_screenshots'] = session.get('dismissed_screenshots', []) + [screenshot_data]
                dismissed_count += 1
            else:
                active_screenshots.append(screenshot_data)
        
        session['screenshots'] = active_screenshots
        session.modified = True
        return dismissed_count
    
    def restore_all_screenshots(self) -> int:
        """Restore all dismissed screenshots"""
        self._ensure_session_initialized()
        
        dismissed = session.get('dismissed_screenshots', [])
        count = len(dismissed)
        
        # Set dismissed flag to False and add to active screenshots
        for screenshot_data in dismissed:
            screenshot_data['dismissed'] = False
            session['screenshots'] = session.get('screenshots', []) + [screenshot_data]
        
        # Clear dismissed list
        session['dismissed_screenshots'] = []
        session.modified = True
        return count
    
    def process_uploaded_file(self, file, original_filename: str) -> Optional[Dict]:
        """Process an uploaded file and store it in the session (no permanent storage)"""
        temp_file = None
        try:
            # Generate a unique ID and secure filename for temporary storage
            screenshot_id = str(uuid.uuid4())
            secure_name = secure_filename(original_filename)
            
            # Create a unique filename in our temp folder
            unique_filename = f"{screenshot_id}_{secure_name}"
            file_path = os.path.join(self.temp_folder, unique_filename)
            
            # Save the file to temp storage for processing
            file.save(file_path)
            logger.info(f"Saved temporary file: {file_path}")
            
            # Extract text using OCR
            try:
                # Open and potentially resize the image for OCR
                image = Image.open(file_path)
                logger.info(f"Successfully opened image: {file_path} (size: {image.width}x{image.height})")
                
                # Resize large images to prevent timeouts
                max_size = (1500, 1500)
                if image.width > max_size[0] or image.height > max_size[1]:
                    image.thumbnail(max_size, Image.LANCZOS)
                    # Save the resized version
                    image.save(file_path)
                    logger.info(f"Resized large image to prevent timeout: {file_path}")
                image.close()
                
                # Extract text with OCR
                custom_config = r'--oem 3 --psm 6 -l eng'
                text = pytesseract.image_to_string(Image.open(file_path), config=custom_config)
            except Exception as ocr_error:
                logger.error(f"OCR failed for {file_path}: {str(ocr_error)}")
                text = "[No text detected]"
            
            # Analyze text with NLP to determine priority
            if text and text.strip():
                try:
                    urgency_score, action_score = nlp_analyzer.analyze_text(text)
                except Exception as nlp_error:
                    logger.error(f"NLP analysis failed: {str(nlp_error)}")
                    # Fallback to random scores if NLP fails
                    urgency_score = random.uniform(0.3, 0.5)
                    action_score = random.uniform(0.3, 0.5)
            else:
                # Assign moderate-low scores for images without text
                urgency_score = random.uniform(0.2, 0.4)
                action_score = random.uniform(0.2, 0.4)
                text = "[No text detected]"
            
            # Calculate priority score (60% urgency, 40% action)
            priority_score = (urgency_score * 0.6) + (action_score * 0.4)
            
            # Create a new screenshot object
            screenshot = SessionScreenshot(
                id=screenshot_id,
                filename=original_filename,
                path=file_path,
                text_content=text,
                priority_score=priority_score,
                urgency_score=urgency_score,
                action_score=action_score,
                dismissed=False
            )
            
            # Store in session (not in database)
            self._ensure_session_initialized()
            session['screenshots'] = session.get('screenshots', []) + [screenshot.to_dict()]
            session.modified = True
            
            logger.info(f"Processed uploaded screenshot with priority score {priority_score:.2f}")
            return screenshot.to_dict()
            
        except Exception as e:
            logger.error(f"Error processing screenshot: {str(e)}")
            return None
    
    def _dict_to_screenshot(self, data: Dict) -> SessionScreenshot:
        """Convert dictionary data to SessionScreenshot object"""
        screenshot = SessionScreenshot(
            id=data.get('id'),
            filename=data.get('filename'),
            path=data.get('path'),
            text_content=data.get('text_content'),
            priority_score=data.get('priority_score', 0.0),
            urgency_score=data.get('urgency_score', 0.0),
            action_score=data.get('action_score', 0.0),
            dismissed=data.get('dismissed', False)
        )
        
        # Convert ISO format strings back to datetime objects if they exist
        if data.get('deferred_until'):
            try:
                screenshot.deferred_until = datetime.datetime.fromisoformat(data.get('deferred_until'))
            except:
                pass
                
        if data.get('created_at'):
            try:
                screenshot.created_at = datetime.datetime.fromisoformat(data.get('created_at'))
            except:
                pass
                
        if data.get('updated_at'):
            try:
                screenshot.updated_at = datetime.datetime.fromisoformat(data.get('updated_at'))
            except:
                pass
        
        return screenshot
    
    def _cleanup_old_files(self):
        """Clean up old temporary files when session ends"""
        # Only remove files based on age, not session data
        # This avoids the "outside request context" error
        if os.path.exists(self.temp_folder):
            # Remove any expired files (older than 8 hours)
            current_time = datetime.datetime.utcnow()
            try:
                # Check for files older than 8 hours
                file_list = os.listdir(self.temp_folder)
                for filename in file_list:
                    file_path = os.path.join(self.temp_folder, filename)
                    try:
                        if not os.path.isfile(file_path):
                            continue
                            
                        file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                        # If file is older than 8 hours, remove it
                        if (current_time - file_mtime).total_seconds() > 8 * 3600:
                            os.remove(file_path)
                            logger.info(f"Removed expired temporary file: {file_path}")
                    except Exception as single_file_error:
                        # Skip this file if there's an error
                        logger.warning(f"Error processing file {file_path}: {str(single_file_error)}")
                        continue
            except Exception as e:
                logger.error(f"Error cleaning up expired files: {str(e)}")
    
    def cleanup_session(self):
        """Clean up all files associated with the current session"""
        logger.info("Cleanup session method called")
        
        try:
            # Check if the session variables exist
            logger.info(f"Session variables: 'screenshots' in session: {'screenshots' in session}, 'dismissed_screenshots' in session: {'dismissed_screenshots' in session}")
            
            # Get all file paths in the session
            paths_to_remove = []
            
            # Add paths from active screenshots
            active_count = 0
            if 'screenshots' in session:
                active_count = len(session.get('screenshots', []))
                logger.info(f"Found {active_count} active screenshots")
                for i, screenshot in enumerate(session.get('screenshots', [])):
                    logger.info(f"Processing active screenshot {i+1}/{active_count}")
                    if screenshot.get('path') and os.path.exists(screenshot.get('path')):
                        paths_to_remove.append(screenshot.get('path'))
            
            # Add paths from dismissed screenshots
            dismissed_count = 0
            if 'dismissed_screenshots' in session:
                dismissed_count = len(session.get('dismissed_screenshots', []))
                logger.info(f"Found {dismissed_count} dismissed screenshots")
                for i, screenshot in enumerate(session.get('dismissed_screenshots', [])):
                    logger.info(f"Processing dismissed screenshot {i+1}/{dismissed_count}")
                    if screenshot.get('path') and os.path.exists(screenshot.get('path')):
                        paths_to_remove.append(screenshot.get('path'))
            
            # Log the total number of files to remove
            logger.info(f"Found {len(paths_to_remove)} files to remove")
            
            # Remove all files
            files_removed = 0
            for i, path in enumerate(paths_to_remove):
                try:
                    if os.path.exists(path):
                        logger.info(f"Removing file {i+1}/{len(paths_to_remove)}: {path}")
                        os.remove(path)
                        files_removed += 1
                except Exception as e:
                    logger.error(f"Error removing file {path}: {str(e)}")
            
            # Clear session data
            logger.info("Clearing session data")
            session['screenshots'] = []
            session['dismissed_screenshots'] = []
            session.modified = True
            
            logger.info(f"Manually cleaned up {files_removed} files for the current session")
            return True
                
        except Exception as e:
            logger.error(f"Error cleaning up session files: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise  # Re-raise the exception so the API endpoint knows it failed

# Helper function for secured filenames
def secure_filename(filename):
    """Return a secure version of the filename"""
    return filename.replace(" ", "_").replace("/", "_")