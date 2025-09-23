"""
Configuration file for PAPI Detection Web UI
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
    
    # File upload settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
    REPORTS_FOLDER = os.environ.get('REPORTS_FOLDER', os.path.join(BASE_DIR, 'reports'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))  # 16MB default
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    MAX_IMAGE_DIMENSIONS = (4000, 4000)  # Max width, height
    
    # Server settings
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '127.0.0.1')
    
    # Processing settings
    PROCESSING_TIMEOUT = int(os.environ.get('PROCESSING_TIMEOUT', 300))  # 5 minutes default
    MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', 50))
    CLEANUP_INTERVAL = int(os.environ.get('CLEANUP_INTERVAL', 3600))  # 1 hour default
    STATUS_RETENTION_HOURS = int(os.environ.get('STATUS_RETENTION_HOURS', 1))
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with configuration"""
        # Ensure directories exist
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.REPORTS_FOLDER, exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production-specific initialization
        # Add any production logging handlers here
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/papi_detector.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    
    # Use temporary directories for testing
    UPLOAD_FOLDER = '/tmp/test_uploads'
    REPORTS_FOLDER = '/tmp/test_reports'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])