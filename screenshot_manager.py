import os
import logging
import datetime
from PIL import Image
import pytesseract
from flask import current_app
import nlp_analyzer

# Configure logging
logger = logging.getLogger(__name__)

# These will be set during init_app
db = None
Screenshot = None

def init_app(app):
    """Initialize the screenshot manager with the app context"""
    global db, Screenshot
    
    # Import the app module here to avoid circular imports
    from app import db as app_db, Screenshot as app_Screenshot
    
    # Set global variables
    db = app_db
    Screenshot = app_Screenshot
    
    app.config.setdefault('SCREENSHOTS_FOLDER', './screenshots')
    app.config.setdefault('DOCUMENTS_FOLDER', './documents')
    
    # Ensure folders exist
    os.makedirs(app.config['SCREENSHOTS_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DOCUMENTS_FOLDER'], exist_ok=True)
    
    # Check for Tesseract
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        logger.error(f"Tesseract OCR is not properly installed: {e}")
        logger.error("Please install Tesseract OCR to use this application")

def scan_for_new_screenshots():
    """
    Scan folders for new screenshots and process them
    Returns the number of new screenshots processed
    """
    count = 0
    new_screenshots = []
    
    # Get folders from config
    screenshots_folder = current_app.config['SCREENSHOTS_FOLDER']
    documents_folder = current_app.config['DOCUMENTS_FOLDER']
    
    folders_to_scan = [screenshots_folder, documents_folder]
    
    # First pass: process all screenshots and collect their data
    for folder in folders_to_scan:
        if not os.path.exists(folder):
            logger.warning(f"Folder does not exist: {folder}")
            continue
        
        for filename in os.listdir(folder):
            if not _is_image_file(filename):
                continue
                
            file_path = os.path.join(folder, filename)
            
            # Check if this screenshot is already in the database
            if Screenshot.query.filter_by(path=file_path).first():
                continue
                
            try:
                # Process the new screenshot but don't save to DB yet
                screenshot_data = process_screenshot(file_path, save_to_db=False)
                if screenshot_data:
                    new_screenshots.append(screenshot_data)
                    count += 1
            except Exception as e:
                logger.exception(f"Error processing screenshot {file_path}: {e}")
    
    # Second pass: normalize scores and save to database
    if new_screenshots:
        normalize_and_save_screenshots(new_screenshots)
    
    return count

def process_screenshot(file_path, save_to_db=True):
    """
    Process a single screenshot file:
    1. Extract text using OCR
    2. Analyze text with NLP
    3. Calculate priority score
    4. Save to database if save_to_db is True, otherwise return data
    """
    logger.debug(f"Processing screenshot: {file_path}")
    
    # Extract text using OCR
    try:
        image = Image.open(file_path)
        text_content = pytesseract.image_to_string(image)
    except Exception as e:
        logger.error(f"OCR extraction failed for {file_path}: {e}")
        text_content = ""
    
    # Handle empty text extraction
    if not text_content.strip():
        logger.warning(f"No text extracted from {file_path}")
        
        # Assign a random priority score between 0.1 and 0.4 for images without text
        # This ensures they're still prioritized somewhat but lower than text-containing images
        import random
        random_priority = random.uniform(0.1, 0.4)
        
        if save_to_db:
            # Still save to database with randomly assigned moderate-low priority
            screenshot = Screenshot(
                filename=os.path.basename(file_path),
                path=file_path,
                text_content="[No text detected]",
                priority_score=random_priority,
                urgency_score=random_priority * 0.5,
                action_score=random_priority * 0.5
            )
            db.session.add(screenshot)
            db.session.commit()
            return None
        else:
            # Return the data for normalization
            return {
                'filename': os.path.basename(file_path),
                'path': file_path,
                'text_content': "[No text detected]",
                'raw_priority_score': random_priority,
                'urgency_score': random_priority * 0.5,
                'action_score': random_priority * 0.5
            }
    
    # Analyze text with NLP
    urgency_score, action_score = nlp_analyzer.analyze_text(text_content)
    
    # Calculate overall priority score (simple weighted sum)
    raw_priority_score = (urgency_score * 0.6) + (action_score * 0.4)
    
    if save_to_db:
        # Create new screenshot record
        screenshot = Screenshot(
            filename=os.path.basename(file_path),
            path=file_path,
            text_content=text_content,
            priority_score=raw_priority_score,  # Will use raw score if saving directly
            urgency_score=urgency_score,
            action_score=action_score
        )
        
        # Save to database
        db.session.add(screenshot)
        db.session.commit()
        
        logger.info(f"Processed screenshot {file_path} with priority score {raw_priority_score:.2f}")
        return None
    else:
        # Return the data for normalization
        return {
            'filename': os.path.basename(file_path),
            'path': file_path,
            'text_content': text_content,
            'raw_priority_score': raw_priority_score,
            'urgency_score': urgency_score,
            'action_score': action_score
        }

def normalize_and_save_screenshots(screenshots):
    """
    Normalize priority scores within a batch and save screenshots to the database.
    This ensures the mean score is around 0.5 with a distribution between 0.2 and 0.8
    for the middle 60% of the screenshots.
    """
    if not screenshots:
        return
        
    # Extract raw priority scores
    raw_scores = [s['raw_priority_score'] for s in screenshots]
    
    # If there's only one screenshot, assign a default score range based on content
    if len(screenshots) == 1:
        # Check if it has text
        if screenshots[0]['text_content'] and screenshots[0]['text_content'] != "[No text detected]":
            # Single text screenshot gets higher priority (0.6 - 0.7)
            import random
            normalized_scores = [random.uniform(0.6, 0.7)]
        else:
            # Single non-text screenshot gets lower priority (0.3 - 0.5)
            import random
            normalized_scores = [random.uniform(0.3, 0.5)]
    else:
        # For multiple screenshots
        
        # First, categorize screenshots into text and non-text
        text_screenshots = []
        nontext_screenshots = []
        text_indices = []
        nontext_indices = []
        
        for i, s in enumerate(screenshots):
            if s['text_content'] and s['text_content'] != "[No text detected]":
                text_screenshots.append(s)
                text_indices.append(i)
            else:
                nontext_screenshots.append(s)
                nontext_indices.append(i)
                
        # Create initial normalized score array
        normalized_scores = [0.0] * len(screenshots)
        
        # Process text screenshots if we have any
        if text_screenshots:
            text_raw_scores = [s['raw_priority_score'] for s in text_screenshots]
            text_min = min(text_raw_scores)
            text_max = max(text_raw_scores)
            
            if text_min == text_max:
                # All text screenshots have the same score
                for i, idx in enumerate(text_indices):
                    normalized_scores[idx] = 0.6  # Higher default for text
            else:
                # Normalize text screenshots to 0.4-0.9 range
                for i, idx in enumerate(text_indices):
                    norm_score = 0.4 + 0.5 * ((text_screenshots[i]['raw_priority_score'] - text_min) / (text_max - text_min))
                    normalized_scores[idx] = norm_score
                    
        # Process non-text screenshots if we have any
        if nontext_screenshots:
            # Distribute non-text screenshots in 0.2-0.5 range
            import random
            for i, idx in enumerate(nontext_indices):
                # Give a slightly randomized score within the range to avoid ties
                normalized_scores[idx] = random.uniform(0.2, 0.5)
        
        # If we have both types, ensure proper overall distribution
        if text_screenshots and nontext_screenshots:
            # Adjust to ensure mean is close to 0.5
            current_mean = sum(normalized_scores) / len(normalized_scores)
            adjustment = 0.5 - current_mean
            
            # Apply a percentage of the adjustment to maintain the general hierarchy
            adjustment_factor = 0.7
            normalized_scores = [score + (adjustment * adjustment_factor) for score in normalized_scores]
            
        # Final clamp to [0.1, 0.9] range to avoid extremes
        normalized_scores = [max(0.1, min(0.9, score)) for score in normalized_scores]
        
        # Add small random variations to break any remaining ties
        import random
        normalized_scores = [score + random.uniform(-0.05, 0.05) for score in normalized_scores]
        
        # Final clamp again
        normalized_scores = [max(0.1, min(0.9, score)) for score in normalized_scores]
    
    # Save normalized scores to database
    for i, screenshot_data in enumerate(screenshots):
        # Create new screenshot record with normalized priority score
        screenshot = Screenshot(
            filename=screenshot_data['filename'],
            path=screenshot_data['path'],
            text_content=screenshot_data['text_content'],
            priority_score=normalized_scores[i],
            urgency_score=screenshot_data['urgency_score'],
            action_score=screenshot_data['action_score']
        )
        
        # Save to database
        db.session.add(screenshot)
    
    # Commit all at once for efficiency
    db.session.commit()
    
    logger.info(f"Normalized and saved {len(screenshots)} screenshots to database")

def _is_image_file(filename):
    """Check if a file is likely a screenshot image based on extension"""
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']
    return any(filename.lower().endswith(ext) for ext in valid_extensions)
