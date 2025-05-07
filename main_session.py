#!/usr/bin/env python3
"""
Main entry point for the Nora screenshot management application
Privacy-Focused Session Mode - No permanent storage
"""

# Import the app from app_session instead of app to use the privacy-focused version
from app_session import app

# Run the app if this file is executed directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)