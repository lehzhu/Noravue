import re
import logging
import datetime
import spacy
from spacy.matcher import Matcher

# Configure logging
logger = logging.getLogger(__name__)

# Global variables
nlp = None
matcher = None

def init():
    """Initialize the NLP analyzer with spaCy"""
    global nlp, matcher
    
    try:
        # Load English language model
        nlp = spacy.load("en_core_web_sm")
        logger.info("Loaded spaCy NLP model")
        
        # Set up the matcher with patterns
        matcher = Matcher(nlp.vocab)
        
        # Add patterns for urgency (e.g., dates, time-sensitive words)
        urgency_patterns = [
            # Today/tomorrow mentions
            [{"LOWER": {"IN": ["today", "tomorrow", "tonight", "asap", "urgent", "immediately", "emergency", "critical"]}}],
            # This week/month
            [{"LOWER": "this"}, {"LOWER": {"IN": ["week", "month", "morning", "afternoon", "evening"]}}],
            # Deadline mentions with indicators
            [{"LOWER": {"IN": ["deadline", "due", "by", "before"]}}, {"OP": "?"}],
            # Soon/quickly
            [{"LOWER": {"IN": ["soon", "quickly", "fast", "rapid", "prompt"]}}],
            # Waiting/pending
            [{"LOWER": {"IN": ["waiting", "pending", "limited", "closing"]}}],
            # Important/priority
            [{"LOWER": {"IN": ["important", "priority", "critical", "crucial", "significant"]}}],
            # Time pressure phrases
            [{"LOWER": "running"}, {"LOWER": "out"}, {"LOWER": "of"}, {"LOWER": "time"}],
            [{"LOWER": "last"}, {"LOWER": {"IN": ["chance", "opportunity", "day", "call"]}}],
            # Dates (spaCy will handle date entity recognition)
        ]
        
        # Add patterns for actionability
        action_patterns = [
            # Action verbs in imperative form (expanded)
            [{"LEMMA": {"IN": ["apply", "submit", "call", "email", "send", "register", "sign", "complete", 
                             "finish", "do", "make", "prepare", "check", "verify", "confirm", "review", 
                             "pay", "schedule", "book", "order", "buy", "download", "install", "update",
                             "contact", "follow", "attend", "join", "meet", "create", "add", "track",
                             "report", "file", "fill", "upload", "backup", "login", "access"]}}],
            # Reminder phrases
            [{"LOWER": "don't"}, {"LOWER": "forget"}, {"LOWER": "to"}],
            [{"LOWER": "reminder"}, {"OP": "?"}],
            [{"LOWER": "remind"}, {"LOWER": "me"}, {"OP": "?"}],
            # Necessity phrases
            [{"LEMMA": "need"}, {"LOWER": "to"}],
            [{"LEMMA": "have"}, {"LOWER": "to"}],
            [{"LEMMA": "must"}, {"OP": "?"}],
            [{"LEMMA": "should"}, {"OP": "?"}],
            # Memory phrases
            [{"LEMMA": "remember"}, {"LOWER": "to"}],
            [{"LOWER": "note"}, {"OP": "?"}],
            # Task indicators
            [{"LOWER": {"IN": ["task", "todo", "to-do", "checklist", "assignment"]}}],
            # Responsibility indicators
            [{"LOWER": "responsible"}, {"LOWER": "for"}],
            [{"LOWER": "your"}, {"LOWER": {"IN": ["task", "job", "responsibility", "assignment"]}}],
            # Approval/confirmation requests
            [{"LOWER": {"IN": ["approve", "confirm", "validate", "verify"]}}],
        ]
        
        # Add patterns to matcher
        matcher.add("URGENCY", urgency_patterns)
        matcher.add("ACTION", action_patterns)
        
        logger.info("NLP analyzer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize NLP analyzer: {e}")
        # Create a fallback analyzer if spaCy failed to load
        nlp = None

def analyze_text(text):
    """
    Analyze text to determine urgency and actionability scores
    Returns tuple of (urgency_score, action_score) each from 0.0 to 1.0
    """
    # Simple fallback if spaCy isn't available
    if nlp is None:
        return _fallback_analyze_text(text)
    
    try:
        # Process the text with spaCy
        doc = nlp(text)
        
        # Extract dates and calculate date-based urgency
        date_urgency = _calculate_date_urgency(doc)
        
        # Use matcher to identify urgency and action patterns
        matches = matcher(doc)
        
        urgency_count = 0
        action_count = 0
        
        for match_id, start, end in matches:
            string_id = nlp.vocab.strings[match_id]
            if string_id == "URGENCY":
                urgency_count += 1
            elif string_id == "ACTION":
                action_count += 1
        
        # Calculate scores (normalize by text length)
        text_length_factor = min(1.0, max(0.5, len(text) / 300))  # Between 0.5 and 1.0
        
        # Add base scores to ensure non-zero values
        base_urgency = 0.15
        base_action = 0.15
        
        # Combine explicit pattern matches with date-based urgency
        urgency_score = min(0.95, base_urgency + (urgency_count * 0.15 * text_length_factor) + date_urgency)
        action_score = min(0.95, base_action + (action_count * 0.12 * text_length_factor))
        
        logger.debug(f"Text analyzed - Urgency: {urgency_score:.2f}, Action: {action_score:.2f}")
        return urgency_score, action_score
        
    except Exception as e:
        logger.exception(f"Error in NLP analysis: {e}")
        return _fallback_analyze_text(text)

def _calculate_date_urgency(doc):
    """Calculate urgency based on dates mentioned in the text"""
    today = datetime.datetime.now().date()
    max_urgency = 0.0
    
    # Find date entities
    for ent in doc.ents:
        if ent.label_ == "DATE":
            try:
                # Try to parse date entities
                if any(term in ent.text.lower() for term in ["today", "tonight", "now"]):
                    return 1.0  # Maximum urgency for today
                elif "tomorrow" in ent.text.lower():
                    return 0.9  # High urgency for tomorrow
                elif "this week" in ent.text.lower():
                    return 0.7  # Medium-high urgency for this week
                elif "next week" in ent.text.lower():
                    return 0.4  # Medium urgency for next week
            except:
                continue
    
    # Look for time patterns
    time_pattern = re.compile(r'\b([0-1]?[0-9]|2[0-3]):([0-5][0-9])\b')
    if time_pattern.search(doc.text):
        return max(max_urgency, 0.6)  # Medium-high urgency for specific times
    
    return max_urgency

def _fallback_analyze_text(text):
    """Enhanced keyword-based analysis as fallback if spaCy fails"""
    text_lower = text.lower()
    
    # Expanded urgency keywords
    urgency_keywords = [
        # Time indicators
        "today", "tomorrow", "tonight", "asap", "urgent", "immediately", 
        "emergency", "critical", "this week", "this month", "this morning",
        "this afternoon", "this evening", "deadline", "due", "by", "before",
        "soon", "quickly", "fast", "rapid", "prompt", "waiting", "pending",
        "limited", "closing", "important", "priority", "crucial", "significant",
        "running out of time", "last chance", "last opportunity", "last day",
        "last call", "hurry"
    ]
    
    # Expanded action keywords
    action_keywords = [
        # Action verbs
        "apply", "submit", "call", "email", "send", "register", "sign", "complete", 
        "finish", "do", "make", "prepare", "check", "verify", "confirm", "review", 
        "pay", "schedule", "book", "order", "buy", "download", "install", "update",
        "contact", "follow", "attend", "join", "meet", "create", "add", "track",
        "report", "file", "fill", "upload", "backup", "login", "access",
        # Phrases
        "don't forget", "reminder", "remind me", "need to", "have to", "must",
        "should", "remember to", "note", "task", "todo", "to-do", "checklist", 
        "assignment", "responsible for", "your task", "your job", "approve",
        "confirm", "validate", "verify"
    ]
    
    # Count matches with extra weight for certain important keywords
    high_urgency_keywords = ["today", "asap", "urgent", "immediately", "emergency", "critical"]
    high_action_keywords = ["need to", "have to", "must", "don't forget"]
    
    urgency_count = 0
    action_count = 0
    
    # Regular keywords
    for keyword in urgency_keywords:
        if keyword in text_lower:
            # Add extra weight for high urgency keywords
            if keyword in high_urgency_keywords:
                urgency_count += 1.5
            else:
                urgency_count += 1
                
    for keyword in action_keywords:
        if keyword in text_lower:
            # Add extra weight for high action keywords
            if keyword in high_action_keywords:
                action_count += 1.5
            else:
                action_count += 1
    
    # Check for dates and times
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or similar
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}\b',  # Month Day
        r'\b\d{1,2}:\d{2}\b'  # HH:MM
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, text_lower):
            urgency_count += 1.5
    
    # Add a base score to ensure non-zero values
    base_urgency = 0.15
    base_action = 0.15
    
    # Normalize by text length but ensure meaningful scores
    text_length_factor = min(1.0, max(0.5, len(text) / 300))  # Between 0.5 and 1.0
    
    # Calculate final scores with base values
    urgency_score = min(0.95, base_urgency + (urgency_count * 0.15 * text_length_factor))
    action_score = min(0.95, base_action + (action_count * 0.12 * text_length_factor))
    
    return urgency_score, action_score
