import datetime

# db will be set by init_db function
db = None

def init_db(database):
    global db
    db = database

class ScreenshotMixin:
    """Mixin class with methods for Screenshot model"""
    
    def __repr__(self):
        return f'<Screenshot {self.filename}>'
    
    @property
    def is_active(self):
        """
        Determines if a screenshot should be shown in the current view.
        It's active if it hasn't been dismissed and isn't currently deferred.
        """
        if self.dismissed:
            return False
        
        if self.deferred_until and self.deferred_until > datetime.datetime.utcnow():
            return False
            
        return True

# Use ScreenshotMixin instead of Screenshot class directly
Screenshot = ScreenshotMixin
