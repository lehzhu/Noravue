import os
import uuid
import logging
import threading
import queue
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
import datetime
import pytesseract
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import necessary modules
import nlp_analyzer
from session_manager import SessionManager

# Initialize the session manager
session_mgr = SessionManager()

# Create a temporary Flask app for development
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set a short session timeout (8 hours) to ensure data cleanup
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(hours=8)

# Configure upload settings
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload size
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

# Configure screenshot paths to serve existing images for backward compatibility
app.config["SCREENSHOTS_FOLDER"] = os.environ.get("SCREENSHOTS_FOLDER", "./screenshots")
app.config["DOCUMENTS_FOLDER"] = os.environ.get("DOCUMENTS_FOLDER", "./documents")
os.makedirs(app.config["SCREENSHOTS_FOLDER"], exist_ok=True)
os.makedirs(app.config["DOCUMENTS_FOLDER"], exist_ok=True)

# Create a function to register routes with an app instance
def register_routes(flask_app):
    """Register routes with the Flask application"""
    
    # Configure the app
    flask_app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(hours=8)
    flask_app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload size
    flask_app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}
    
    # Configure screenshot paths to serve existing images for backward compatibility
    flask_app.config["SCREENSHOTS_FOLDER"] = os.environ.get("SCREENSHOTS_FOLDER", "./screenshots")
    flask_app.config["DOCUMENTS_FOLDER"] = os.environ.get("DOCUMENTS_FOLDER", "./documents")
    os.makedirs(flask_app.config["SCREENSHOTS_FOLDER"], exist_ok=True)
    os.makedirs(flask_app.config["DOCUMENTS_FOLDER"], exist_ok=True)
    
    # Initialize modules with the app
    with flask_app.app_context():
        # Initialize the nlp analyzer
        nlp_analyzer.init()
        
        # Initialize the session manager
        session_mgr.init_app(flask_app)
    
    # Register all routes with the Flask app
    flask_app.add_url_rule('/screenshots/<path:filename>', 'uploaded_file', uploaded_file)
    flask_app.add_url_rule('/temp_uploads/<path:filename>', 'temp_file', temp_file)
    flask_app.add_url_rule('/', 'index', index)
    flask_app.add_url_rule('/api/screenshots', 'get_screenshots', get_screenshots)
    flask_app.add_url_rule('/api/dismiss/<int:screenshot_id>', 'dismiss_screenshot', dismiss_screenshot, methods=['POST'])
    flask_app.add_url_rule('/api/restore/<int:screenshot_id>', 'restore_screenshot', restore_screenshot, methods=['POST'])
    flask_app.add_url_rule('/api/defer/<int:screenshot_id>', 'defer_screenshot', defer_screenshot, methods=['POST'])
    flask_app.add_url_rule('/settings', 'settings', settings)
    flask_app.add_url_rule('/privacy', 'privacy', privacy)
    flask_app.add_url_rule('/api/upload', 'upload_screenshots', upload_screenshots, methods=['POST'])
    flask_app.add_url_rule('/api/upload-progress', 'upload_progress_api', upload_progress_api)
    flask_app.add_url_rule('/api/has-dismissed-screenshots', 'has_dismissed_screenshots', has_dismissed_screenshots)
    flask_app.add_url_rule('/api/dismiss-all', 'dismiss_all_screenshots', dismiss_all_screenshots, methods=['POST'])
    flask_app.add_url_rule('/api/restore-dismissed', 'restore_dismissed_screenshots', restore_dismissed_screenshots, methods=['POST'])
    flask_app.add_url_rule('/api/cleanup-session', 'cleanup_session', cleanup_session, methods=['POST'])
    
    # Add template filters
    flask_app.template_filter('truncate_text')(truncate_text)
    
    return flask_app
    
# Create routes to serve the images (for backward compatibility)
@app.route('/screenshots/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['SCREENSHOTS_FOLDER'], filename)

# Temporary files in the session manager
@app.route('/temp_uploads/<path:filename>')
def temp_file(filename):
    return send_from_directory('temp_uploads', filename)

# Main route
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/screenshots')
def get_screenshots():
    """Get all active screenshots sorted by priority"""
    try:
        # Get all active screenshots from the session
        screenshots = session_mgr.get_active_screenshots()
        
        # Log the results
        app.logger.info(f"Total screenshots in session: {len(screenshots)}")
        
        return jsonify(screenshots)
    except Exception as e:
        app.logger.error(f"Error fetching screenshots: {str(e)}")
        return jsonify([]), 500

@app.route('/api/dismiss/<int:screenshot_id>', methods=['POST'])
def dismiss_screenshot(screenshot_id):
    """Mark a screenshot as dismissed"""
    try:
        success = session_mgr.dismiss_screenshot(str(screenshot_id))
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Screenshot not found'}), 404
    except Exception as e:
        app.logger.error(f"Error dismissing screenshot {screenshot_id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/restore/<int:screenshot_id>', methods=['POST'])
def restore_screenshot(screenshot_id):
    """Restore a previously dismissed screenshot"""
    try:
        success = session_mgr.restore_screenshot(str(screenshot_id))
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Screenshot not found'}), 404
    except Exception as e:
        app.logger.error(f"Error restoring screenshot {screenshot_id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/defer/<int:screenshot_id>', methods=['POST'])
def defer_screenshot(screenshot_id):
    """Defer a screenshot for later viewing"""
    try:
        data = request.get_json()
        minutes = data.get('minutes', 30)
        
        success = session_mgr.defer_screenshot(str(screenshot_id), minutes)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Screenshot not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deferring screenshot {screenshot_id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/privacy')
def privacy():
    """Privacy policy page"""
    return render_template('privacy.html')

def allowed_file(filename):
    """Check if a filename has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

# Global variables for tracking upload progress
upload_progress = {
    'total': 0,
    'processed': 0,
    'in_progress': False,
    'start_time': None
}

@app.route('/api/upload', methods=['POST'])
def upload_screenshots():
    """Handle uploaded screenshots with batch processing for large uploads"""
    global upload_progress
    
    try:
        if 'screenshots[]' not in request.files:
            return jsonify({'success': False, 'message': 'No files submitted'}), 400
            
        files = request.files.getlist('screenshots[]')
        
        if len(files) == 0:
            return jsonify({'success': False, 'message': 'No files selected'}), 400
            
        # Reset progress tracking
        upload_progress['total'] = len(files)
        upload_progress['processed'] = 0
        upload_progress['in_progress'] = True
        upload_progress['start_time'] = datetime.datetime.now()
        
        # Process files in batches to avoid timeouts with large uploads
        valid_files = []
        for file in files:
            if file and allowed_file(file.filename):
                valid_files.append(file)
                
        if len(valid_files) == 0:
            upload_progress['in_progress'] = False
            return jsonify({'success': False, 'message': 'No valid image files found'}), 400
        
        # For small uploads (under 10 files), process immediately
        if len(valid_files) <= 10:
            processed_count = 0
            
            for file in valid_files:
                result = session_mgr.process_uploaded_file(file, file.filename)
                if result:
                    processed_count += 1
                    
            upload_progress['processed'] = processed_count
            upload_progress['in_progress'] = False
            
            return jsonify({
                'success': True,
                'message': f'Processed {processed_count} screenshots',
                'count': processed_count
            })
        else:
            # For larger uploads, process in background thread
            def process_batch_background(app_context, files_to_process):
                with app_context:
                    for file in files_to_process:
                        try:
                            result = session_mgr.process_uploaded_file(file, file.filename)
                            if result:
                                upload_progress['processed'] += 1
                        except Exception as e:
                            logger.error(f"Error processing file {file.filename}: {str(e)}")
                    
                    upload_progress['in_progress'] = False
                    logger.info(f"Background processing complete. Processed {upload_progress['processed']}/{upload_progress['total']} files.")
            
            # Start background thread with proper app context
            thread = threading.Thread(
                target=process_batch_background,
                args=(app.app_context(), valid_files)
            )
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'success': True,
                'message': f'Processing {len(valid_files)} screenshots in the background',
                'background': True
            })
            
    except Exception as e:
        upload_progress['in_progress'] = False
        logger.exception(f"Error uploading screenshots: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/upload-progress')
def upload_progress_api():
    """Get the current progress of background uploads"""
    global upload_progress
    
    if not upload_progress['in_progress']:
        return jsonify({
            'in_progress': False,
            'processed': upload_progress['processed'],
            'total': upload_progress['total']
        })
    
    # Calculate estimated time remaining
    if upload_progress['processed'] > 0 and upload_progress['start_time']:
        elapsed = (datetime.datetime.now() - upload_progress['start_time']).total_seconds()
        rate = upload_progress['processed'] / elapsed if elapsed > 0 else 0
        remaining = (upload_progress['total'] - upload_progress['processed']) / rate if rate > 0 else 0
    else:
        remaining = None
    
    return jsonify({
        'in_progress': True,
        'processed': upload_progress['processed'],
        'total': upload_progress['total'],
        'percent': int(100 * upload_progress['processed'] / upload_progress['total']) if upload_progress['total'] > 0 else 0,
        'estimated_seconds_remaining': int(remaining) if remaining is not None else None
    })

@app.route('/api/has-dismissed-screenshots')
def has_dismissed_screenshots():
    """Check if there are any dismissed screenshots in the session"""
    dismissed_screenshots = session_mgr.get_dismissed_screenshots()
    dismissed_count = len(dismissed_screenshots)
    return jsonify({'has_dismissed': dismissed_count > 0, 'count': dismissed_count})
    
@app.route('/api/dismiss-all', methods=['POST'])
def dismiss_all_screenshots():
    """Dismiss all active screenshots at once"""
    try:
        # Dismiss all active screenshots
        count = session_mgr.dismiss_all_screenshots()
        
        return jsonify({
            'success': True,
            'message': f'Dismissed {count} screenshot{"s" if count != 1 else ""}',
            'count': count
        })
    except Exception as e:
        app.logger.error(f"Error dismissing all screenshots: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to dismiss all screenshots'
        }), 500

@app.route('/api/restore-dismissed', methods=['POST'])
def restore_dismissed_screenshots():
    """Restore all dismissed screenshots"""
    try:
        # Restore all dismissed screenshots
        count = session_mgr.restore_all_screenshots()
        
        app.logger.info(f"Successfully restored {count} screenshots")
        
        return jsonify({
            'success': True,
            'message': f'Restored {count} screenshot{"s" if count != 1 else ""}',
            'count': count
        })
    except Exception as e:
        app.logger.error(f"Error restoring dismissed screenshots: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to restore dismissed screenshots'
        }), 500

@app.route('/api/cleanup-session', methods=['POST'])
def cleanup_session():
    """Clean up all files and data from the current session - simple version"""
    try:
        app.logger.info("API call to cleanup session started")
        
        # Simple clear operation - no database dependencies
        # Just clean up the Flask session directly
        
        # Clear Flask session data
        session.clear()
        
        # Initialize empty lists in the session
        session['screenshots'] = []
        session['dismissed_screenshots'] = []
        session.modified = True
        
        app.logger.info("Session data cleared successfully")
        
        # Also clean any temp files in a safe manner
        try:
            import shutil
            temp_folder = "temp_uploads"
            if os.path.exists(temp_folder):
                # Get all files in the temp folder
                for filename in os.listdir(temp_folder):
                    file_path = os.path.join(temp_folder, filename)
                    # Skip directories and non-existent files
                    if os.path.isfile(file_path):
                        try:
                            os.unlink(file_path)
                            app.logger.info(f"Removed temp file: {file_path}")
                        except Exception as e:
                            app.logger.warning(f"Could not remove temp file {file_path}: {str(e)}")
                
                app.logger.info("Temporary files cleaned")
                
        except Exception as temp_error:
            app.logger.warning(f"Non-critical error cleaning temp files: {str(temp_error)}")
        
        app.logger.info("Session cleanup completed successfully")
        
        return jsonify({
            'success': True,
            'message': 'Your session data has been cleared'
        })
    except Exception as e:
        app.logger.error(f"Error cleaning up session: {str(e)}")
        # Return more detailed error message
        error_msg = f"Failed to clear session data: {str(e)}"
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.template_filter('truncate_text')
def truncate_text(text, length=100):
    if text and len(text) > length:
        return text[:length] + '...'
    return text if text else ''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)