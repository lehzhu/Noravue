import os
import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import datetime
import pytesseract
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///screenshots.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure screenshot paths
app.config["SCREENSHOTS_FOLDER"] = os.environ.get("SCREENSHOTS_FOLDER", "./screenshots")
app.config["DOCUMENTS_FOLDER"] = os.environ.get("DOCUMENTS_FOLDER", "./documents")

# Ensure folders exist
os.makedirs(app.config["SCREENSHOTS_FOLDER"], exist_ok=True)
os.makedirs(app.config["DOCUMENTS_FOLDER"], exist_ok=True)

# Configure the app to serve screenshot images directly
app.config["UPLOADED_PHOTOS_DEST"] = app.config["SCREENSHOTS_FOLDER"]

# Create routes to serve the images
@app.route('/screenshots/<path:filename>')
def uploaded_file(filename):
    full_path = os.path.join(app.config['SCREENSHOTS_FOLDER'], filename)
    directory = os.path.dirname(full_path)
    base_filename = os.path.basename(full_path)
    return send_from_directory(directory, base_filename)

# Initialize the app with the extension
db.init_app(app)

# Import and initialize models
import models
models.init_db(db)

# Define screenshot model using the mixin from models.py
class Screenshot(db.Model, models.ScreenshotMixin):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(512), nullable=False, unique=True)
    text_content = db.Column(db.Text, nullable=True)
    priority_score = db.Column(db.Float, default=0.0)
    urgency_score = db.Column(db.Float, default=0.0)
    action_score = db.Column(db.Float, default=0.0)
    dismissed = db.Column(db.Boolean, default=False)
    deferred_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# Create tables and initialize services
with app.app_context():
    db.create_all()
    
    # Import and initialize other services after database is ready
    import nlp_analyzer
    import screenshot_manager
    
    # Initialize the services
    screenshot_manager.init_app(app)
    nlp_analyzer.init()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/screenshots')
def get_screenshots():
    # Get active (not dismissed) screenshots with passed defer time, ordered by priority
    now = datetime.datetime.now()
    
    # First, check if we have any screenshots in the database at all
    total_count = Screenshot.query.count()
    app.logger.info(f"Total screenshots in database: {total_count}")
    
    # Get active screenshots
    screenshots = Screenshot.query.filter(
        Screenshot.dismissed == False,  # Not dismissed
        (Screenshot.deferred_until == None) | (Screenshot.deferred_until <= now)  # Not deferred or defer time has passed
    ).order_by(Screenshot.priority_score.desc()).all()
    
    app.logger.info(f"Active screenshots found: {len(screenshots)}")
    
    # Convert to dictionary for JSON response
    result = []
    for screenshot in screenshots:
        result.append({
            'id': screenshot.id,
            'filename': screenshot.filename,
            'path': screenshot.path,
            'text_content': screenshot.text_content,
            'priority_score': screenshot.priority_score,
            'created_at': screenshot.created_at.isoformat(),
            'deferred_until': screenshot.deferred_until.isoformat() if screenshot.deferred_until else None
        })
    
    # Log some details about what we're returning
    app.logger.info(f"Returning {len(result)} screenshots in the API response")
    return jsonify(result)

@app.route('/api/screenshots/<int:screenshot_id>/dismiss', methods=['POST'])
def dismiss_screenshot(screenshot_id):
    try:
        screenshot = Screenshot.query.get_or_404(screenshot_id)
        screenshot.dismissed = True
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error dismissing screenshot: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
        
@app.route('/api/screenshots/<int:screenshot_id>/restore', methods=['POST'])
def restore_screenshot(screenshot_id):
    """Restore a previously dismissed screenshot"""
    try:
        screenshot = Screenshot.query.get_or_404(screenshot_id)
        screenshot.dismissed = False
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error restoring screenshot: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/screenshots/<int:screenshot_id>/defer', methods=['POST'])
def defer_screenshot(screenshot_id):
    try:
        screenshot = Screenshot.query.get_or_404(screenshot_id)
        
        # Get defer time from request (in hours)
        defer_hours = request.json.get('defer_hours', 24)
        screenshot.deferred_until = datetime.datetime.now() + datetime.timedelta(hours=defer_hours)
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deferring screenshot: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/settings')
def settings():
    return render_template('settings.html')

# Helper function to check if file is allowed
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def upload_screenshots():
    """Handle uploaded screenshots with batch processing for large uploads"""
    import threading
    
    if 'screenshots[]' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    
    files = request.files.getlist('screenshots[]')
    
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    
    # First, save all files to disk without processing
    saved_files = []
    errors = []
    
    # Create a progress tracker
    total_files = len(files)
    app.config['UPLOAD_PROGRESS'] = {
        'total': total_files,
        'saved': 0,
        'processed': 0,
        'completed': False
    }
    
    # Save all files first (this is fast)
    for file in files:
        if file and allowed_file(file.filename):
            # Create a unique filename to avoid collisions
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(app.config['SCREENSHOTS_FOLDER'], unique_filename)
            
            try:
                # Save the file
                file.save(file_path)
                saved_files.append({
                    'path': file_path,
                    'filename': filename
                })
                app.config['UPLOAD_PROGRESS']['saved'] += 1
            except Exception as e:
                logger.exception(f"Error saving {filename}")
                error_msg = str(e)
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                errors.append(f"Error saving {filename}: {error_msg}")
        else:
            errors.append(f"Invalid file type: {file.filename}")
    
    # Start a background thread to process saved files in batches
    if saved_files:
        def process_saved_files(flask_app, files_to_process):
            # Use application context in the thread
            with flask_app.app_context():
                try:
                    processed_count = 0
                    # Process files in small batches to avoid timeouts
                    batch_size = 10
                    
                    for i in range(0, len(files_to_process), batch_size):
                        batch = files_to_process[i:i+batch_size]
                        
                        for file_info in batch:
                            try:
                                # Process the screenshot
                                success = process_uploaded_screenshot(file_info['path'], file_info['filename'])
                                if success:
                                    processed_count += 1
                            except Exception as e:
                                logger.exception(f"Error processing {file_info['filename']}")
                                # Still try to create a record even if processing failed
                                try:
                                    screenshot = Screenshot(
                                        filename=file_info['filename'],
                                        path=file_info['path'],
                                        text_content="[Upload error]",
                                        priority_score=0.3,
                                        urgency_score=0.2,
                                        action_score=0.2
                                    )
                                    db.session.add(screenshot)
                                    db.session.commit()
                                    processed_count += 1
                                except Exception as record_error:
                                    logger.error(f"Failed to create fallback record: {str(record_error)}")
                            
                            # Update progress
                            flask_app.config['UPLOAD_PROGRESS']['processed'] += 1
                    
                    # Normalize priority scores after processing all screenshots
                    try:
                        # Get all active screenshots
                        now = datetime.datetime.now()
                        screenshots = Screenshot.query.filter(
                            Screenshot.dismissed == False,
                            (Screenshot.deferred_until == None) | (Screenshot.deferred_until <= now)
                        ).all()
                        
                        # Normalize priority scores if we have enough screenshots
                        if len(screenshots) >= 3:
                            # Get all priority scores
                            scores = [s.priority_score for s in screenshots]
                            
                            # Calculate mean and standard deviation
                            mean_score = sum(scores) / len(scores)
                            std_dev = (sum((x - mean_score) ** 2 for x in scores) / len(scores)) ** 0.5
                            
                            # Target a mean of 0.5 with most scores between 0.2 and 0.8
                            if std_dev > 0:  # Avoid division by zero
                                for screenshot in screenshots:
                                    # Normalize to z-score
                                    z_score = (screenshot.priority_score - mean_score) / std_dev
                                    # Convert to new scale (mean 0.5, std dev ~0.15)
                                    normalized_score = 0.5 + (z_score * 0.15)
                                    # Clamp between 0.1 and 0.9
                                    normalized_score = max(0.1, min(0.9, normalized_score))
                                    screenshot.priority_score = normalized_score
                                
                                # Save all changes
                                db.session.commit()
                                logger.info(f"Normalized priority scores for {len(screenshots)} screenshots")
                    except Exception as norm_error:
                        logger.error(f"Error normalizing priority scores: {str(norm_error)}")
                    
                    # Mark process as complete
                    flask_app.config['UPLOAD_PROGRESS']['completed'] = True
                    logger.info(f"Background processing complete. Processed {processed_count}/{len(files_to_process)} files.")
                except Exception as e:
                    logger.exception(f"Error in background processing: {str(e)}")
                    flask_app.config['UPLOAD_PROGRESS']['completed'] = True
        
        # Start the background thread - pass the app instance
        processing_thread = threading.Thread(target=process_saved_files, args=(app, saved_files.copy(),))
        processing_thread.daemon = True
        processing_thread.start()
    
    # Return immediately with status
    return jsonify({
        'success': len(saved_files) > 0,
        'message': f"Saved {len(saved_files)} screenshots. Processing started in background.",
        'total_files': total_files,
        'saved_files': len(saved_files),
        'warnings': errors if errors else None
    })

# Add a new endpoint to check upload progress
@app.route('/api/upload/progress', methods=['GET'])
def upload_progress():
    """Get the current progress of background uploads"""
    progress = app.config.get('UPLOAD_PROGRESS', {
        'total': 0,
        'saved': 0,
        'processed': 0,
        'completed': True
    })
    
    return jsonify(progress)

def preprocess_image_for_ocr(image_path):
    """
    Preprocess the image to improve OCR results, with robust error handling
    and more conservative image transformations
    """
    try:
        # Open the image with a timeout mechanism
        from PIL import ImageEnhance, ImageFilter
        import threading
        import queue

        # Function to open image in a separate thread
        def open_image(path, result_queue):
            try:
                img = Image.open(path)
                # Convert to RGB if the image is in RGBA mode (handles PNG with transparency)
                if img.mode == 'RGBA':
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    # Paste the image using alpha as mask
                    background.paste(img, mask=img.split()[3])
                    img = background
                result_queue.put(('success', img))
            except Exception as img_err:
                result_queue.put(('error', str(img_err)))

        # Run image opening with a timeout
        result_queue = queue.Queue()
        open_thread = threading.Thread(
            target=open_image,
            args=(image_path, result_queue)
        )
        open_thread.daemon = True
        open_thread.start()
        open_thread.join(timeout=5)  # 5 second timeout

        if open_thread.is_alive():
            logger.warning(f"Timeout opening image {image_path}")
            return image_path

        # Get the result
        status, result = result_queue.get()
        if status == 'error':
            logger.error(f"Error opening image: {result}")
            return image_path

        image = result

        # Get image dimensions and sanity check
        width, height = image.size
        if width > 5000 or height > 5000:
            # Resize very large images
            max_size = (2000, 2000)
            image.thumbnail(max_size, Image.LANCZOS)
            logger.info(f"Resized very large image for OCR: {image_path}")
        
        # Convert to grayscale
        image = image.convert('L')
        
        # More conservative contrast enhancement to avoid over-processing
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)  # Slightly increase contrast
        
        # Apply moderate sharpening
        image = image.filter(ImageFilter.SHARPEN)
        
        # Enhanced adaptive thresholding for better text extraction
        # Use a smarter threshold based on image statistics
        import numpy as np
        image_array = np.array(image)
        mean_val = np.mean(image_array)
        std_val = np.std(image_array)
        
        # Adaptive threshold based on image statistics
        threshold = max(120, min(190, mean_val - 0.5 * std_val))
        image = image.point(lambda p: p > threshold and 255)
        
        # Save temporary processed image with proper error handling
        try:
            temp_path = f"{image_path}_processed.png"
            image.save(temp_path, format='PNG')
            return temp_path
        except Exception as save_err:
            logger.error(f"Error saving processed image: {str(save_err)}")
            return image_path
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        return image_path  # Return original path if preprocessing fails

def process_uploaded_screenshot(file_path, original_filename):
    """Process a newly uploaded screenshot file"""
    try:
        # Log start of processing
        logger.info(f"Processing new screenshot: {file_path}")
        
        # IMPORTANT: Make sure newly uploaded screenshots are set to NOT dismissed
        
        # Check if this screenshot already exists
        existing = Screenshot.query.filter_by(path=file_path).first()
        if existing:
            logger.info(f"Screenshot already exists in DB: {file_path}")
            return False
        
        # Check if the image is valid and not too large
        try:
            image = Image.open(file_path)
            logger.info(f"Successfully opened image: {file_path} (size: {image.width}x{image.height})")
            
            # Resize large images to prevent timeouts
            max_size = (1500, 1500)
            if image.width > max_size[0] or image.height > max_size[1]:
                image.thumbnail(max_size, Image.LANCZOS)
                # Save the resized image
                image.save(file_path)
                logger.info(f"Resized large image to prevent timeout: {file_path}")
            image.close()
        except Exception as img_error:
            logger.error(f"Error opening image {file_path}: {str(img_error)}")
            # Create a record with no text content
            screenshot = Screenshot(
                filename=original_filename,
                path=file_path,
                text_content="[Error: Could not process image]",
                priority_score=0.3,  # Default moderate-low priority
                urgency_score=0.2,
                action_score=0.2,
                dismissed=False  # Explicitly set dismissed to False
            )
            db.session.add(screenshot)
            db.session.commit()
            logger.info(f"Created fallback record for unprocessable image: {file_path}")
            return True
            
        # Try to extract text with OCR, with timeout handling
        text = ""
        try:
            # Preprocess the image for better OCR
            processed_image_path = preprocess_image_for_ocr(file_path)
            
            # Use better OCR configuration with a reasonable timeout
            import threading
            import queue
            
            def ocr_task(img_path, result_queue):
                try:
                    custom_config = r'--oem 3 --psm 6 -l eng'
                    ocr_result = pytesseract.image_to_string(
                        Image.open(img_path),
                        config=custom_config
                    )
                    result_queue.put(ocr_result)
                except Exception as ocr_err:
                    logger.error(f"OCR processing error: {str(ocr_err)}")
                    result_queue.put("")
            
            # Run OCR with a timeout
            result_queue = queue.Queue()
            ocr_thread = threading.Thread(
                target=ocr_task, 
                args=(processed_image_path, result_queue)
            )
            ocr_thread.daemon = True
            ocr_thread.start()
            ocr_thread.join(timeout=10)  # 10 second timeout
            
            if ocr_thread.is_alive():
                logger.warning(f"OCR timeout for {file_path}, continuing with empty text")
                text = ""
            else:
                text = result_queue.get()
            
            # Clean up temporary file if created
            if processed_image_path != file_path and os.path.exists(processed_image_path):
                try:
                    os.remove(processed_image_path)
                except:
                    pass
                    
        except Exception as ocr_error:
            logger.error(f"OCR failed for {file_path}: {str(ocr_error)}")
            text = ""
        
        # Analyze text with NLP (or use default if empty)
        if text.strip():
            urgency_score, action_score = nlp_analyzer.analyze_text(text)
        else:
            # Assign random moderate-low scores for images without text
            import random
            urgency_score = random.uniform(0.2, 0.4)
            action_score = random.uniform(0.2, 0.4)
            text = "[No text detected]"
        
        # Calculate priority score (60% urgency, 40% action)
        priority_score = (urgency_score * 0.6) + (action_score * 0.4)
        
        # Create new screenshot record - ensure dismissed is explicitly set to False
        screenshot = Screenshot(
            filename=original_filename,
            path=file_path,
            text_content=text,
            priority_score=priority_score,
            urgency_score=urgency_score,
            action_score=action_score,
            dismissed=False  # Explicitly set dismissed to False for new uploads
        )
        
        # Save to database
        db.session.add(screenshot)
        db.session.commit()
        
        logger.info(f"Processed uploaded screenshot {file_path} with priority score {priority_score:.2f}")
        return True
    except Exception as e:
        logger.error(f"Error processing screenshot {file_path}: {str(e)}")
        # Still create a record to avoid losing the file
        try:
            screenshot = Screenshot(
                filename=original_filename,
                path=file_path,
                text_content="[Error during processing]",
                priority_score=0.3,
                urgency_score=0.2,
                action_score=0.2,
                dismissed=False  # Explicitly set dismissed to False
            )
            db.session.add(screenshot)
            db.session.commit()
            logger.info(f"Created fallback record for {file_path}")
            return True
        except Exception as db_error:
            logger.error(f"Could not save fallback record: {str(db_error)}")
            return False

@app.route('/api/rescan', methods=['POST'])
def rescan_screenshots():
    try:
        count = screenshot_manager.scan_for_new_screenshots()
        return jsonify({'success': True, 'message': f'Found and processed {count} new screenshots'})
    except Exception as e:
        logger.exception("Error during screenshot scan")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/has-dismissed-screenshots')
def has_dismissed_screenshots():
    """Check if there are any dismissed screenshots in the database"""
    dismissed_count = Screenshot.query.filter_by(dismissed=True).count()
    return jsonify({'has_dismissed': dismissed_count > 0, 'count': dismissed_count})
    
@app.route('/api/dismiss-all', methods=['POST'])
def dismiss_all_screenshots():
    """Dismiss all active screenshots at once"""
    try:
        # Get all active screenshots
        active_screenshots = Screenshot.query.filter_by(dismissed=False).all()
        count = len(active_screenshots)
        
        # Mark all as dismissed
        for screenshot in active_screenshots:
            screenshot.dismissed = True
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Dismissed {count} screenshot{"s" if count != 1 else ""}',
            'count': count
        })
    except Exception as e:
        app.logger.error(f"Error dismissing all screenshots: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Failed to dismiss all screenshots'
        }), 500

@app.route('/api/restore-dismissed', methods=['POST'])
def restore_dismissed_screenshots():
    """Restore all dismissed screenshots"""
    try:
        # Get all dismissed screenshots
        dismissed_screenshots = Screenshot.query.filter_by(dismissed=True).all()
        count = len(dismissed_screenshots)
        
        app.logger.info(f"Restoring {count} dismissed screenshots")
        
        # Mark all as not dismissed
        for screenshot in dismissed_screenshots:
            screenshot.dismissed = False
        
        db.session.commit()
        
        app.logger.info(f"Successfully restored {count} screenshots")
        
        return jsonify({
            'success': True,
            'message': f'Restored {count} screenshot{"s" if count != 1 else ""}',
            'count': count
        })
    except Exception as e:
        app.logger.error(f"Error restoring dismissed screenshots: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Failed to restore dismissed screenshots'
        }), 500

@app.template_filter('truncate_text')
def truncate_text(text, length=100):
    if text and len(text) > length:
        return text[:length] + '...'
    return text if text else ''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
