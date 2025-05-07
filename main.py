import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app():
    # create the app
    app = Flask(__name__)
    
    # setup a secret key, required by sessions
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
    
    # Configure database connection from environment variable or fallback to SQLite
    database_url = os.environ.get("DATABASE_URL")
    
    # Check if DATABASE_URL is set
    if not database_url:
        # Fallback to a local SQLite database if no PostgreSQL is available
        database_url = "sqlite:///instance/screenshots.db"
        logger.warning("DATABASE_URL not set, using SQLite database")
    
    # Configure the database 
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Debug print to verify the database URL
    logger.info(f"Using database URL: {database_url}")
    
    # initialize the app with the extension, flask-sqlalchemy >= 3.0.x
    db.init_app(app)
    
    with app.app_context():
        # Make sure to import the models here or their tables won't be created
        from models import init_db
        
        # Initialize the database schema
        init_db(db)
        
        # Create all tables
        db.create_all()
    
    # Import the views and routes from app.py (session version)
    from app_session import register_routes
    
    # Register routes
    register_routes(app)
    
    return app

# Create the app instance
app = create_app()

# Run the app directly when this file is executed
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)