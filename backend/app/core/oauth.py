"""
OAuth 2.0 configuration for Google SSO
"""
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import os

# Load environment variables
config = Config(os.path.join(os.path.dirname(__file__), '../../.env'))

# Initialize OAuth
oauth = OAuth()

# Google OAuth Configuration
oauth.register(
    name='google',
    client_id=config.get('GOOGLE_CLIENT_ID', default=''),
    client_secret=config.get('GOOGLE_CLIENT_SECRET', default=''),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


def get_oauth_config(provider: str):
    """Get OAuth configuration for a specific provider"""
    return oauth.create_client(provider)
