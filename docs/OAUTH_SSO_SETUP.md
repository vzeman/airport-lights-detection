# OAuth SSO Implementation Guide

This document provides a complete guide to set up Google, Microsoft, and Facebook OAuth authentication for the Airport Lights Detection System.

## Overview

OAuth users will:
1. Authenticate via OAuth provider (Google/Microsoft/Facebook)
2. Be automatically created as VIEWER role users with no airport access
3. Require a SUPER_ADMIN to assign airports and adjust roles
4. Not be able to access airport data until assigned

## 1. Google Cloud Console Setup

### Create Google OAuth Credentials

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "OAuth 2.0 Client ID"
5. Configure OAuth consent screen if not done:
   - Application name: "Airport Lights Detection System"
   - User support email: your email
   - Developer contact: your email
6. Create OAuth Client ID:
   - Application type: "Web application"
   - Name: "Airport Lights Detection"
   - Authorized redirect URIs:
     - `http://localhost:3000/auth/google/callback` (development)
     - `https://yourdomain.com/auth/google/callback` (production)
7. Copy the **Client ID** and **Client Secret**

## 2. Microsoft Azure Setup (Optional)

### Create Microsoft OAuth App

1. Go to https://portal.azure.com/
2. Navigate to "Azure Active Directory" > "App registrations"
3. Click "New registration"
4. Fill in:
   - Name: "Airport Lights Detection System"
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: `http://localhost:3000/auth/microsoft/callback`
5. Copy the **Application (client) ID**
6. Go to "Certificates & secrets" > "New client secret"
7. Copy the **Client Secret** value

## 3. Facebook Developer Setup (Optional)

### Create Facebook App

1. Go to https://developers.facebook.com/
2. Click "My Apps" > "Create App"
3. Select "Consumer" as app type
4. Fill in app details
5. Go to "Settings" > "Basic"
6. Copy **App ID** and **App Secret**
7. Add "Facebook Login" product
8. Configure Valid OAuth Redirect URIs:
   - `http://localhost:3000/auth/facebook/callback`

## 4. Environment Configuration

Add these variables to `backend/.env`:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft OAuth (Optional)
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Facebook OAuth (Optional)
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret

# OAuth Redirect Base URL
OAUTH_REDIRECT_URL=http://localhost:3000  # Change to your frontend URL
```

## 5. Database Migration

Run the migration to add OAuth fields:

```bash
docker compose exec backend python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL.replace('+aiomysql', ''))
with engine.connect() as conn:
    conn.execute(text('''
        ALTER TABLE users
            MODIFY COLUMN hashed_password VARCHAR(255) NULL,
            ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50) NULL,
            ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255) NULL,
            ADD COLUMN IF NOT EXISTS oauth_access_token TEXT NULL,
            ADD COLUMN IF NOT EXISTS oauth_refresh_token TEXT NULL,
            ADD COLUMN IF NOT EXISTS oauth_token_expires_at DATETIME NULL;
    '''))
    conn.execute(text('CREATE INDEX IF NOT EXISTS idx_users_oauth_id ON users(oauth_id);'))
    conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth_provider_id ON users(oauth_provider, oauth_id);'))
    conn.commit()
print('Migration completed successfully!')
"
```

## 6. Backend OAuth Endpoints

The OAuth flow works as follows:

### Step 1: Initiate OAuth (/auth/{provider}/login)
Frontend redirects user to this endpoint, which redirects to OAuth provider

### Step 2: OAuth Callback (/auth/{provider}/callback)
Provider redirects back with authorization code
Backend exchanges code for tokens and user info
Creates or updates user in database
Returns JWT tokens to frontend

### Implementation in `backend/app/api/auth.py`:

```python
from starlette.requests import Request
from starlette.responses import RedirectResponse
from app.core.oauth import oauth
import uuid
from datetime import datetime

@router.get("/auth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    """Initiate OAuth login with provider"""
    if provider not in ['google', 'microsoft', 'facebook']:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    client = oauth.create_client(provider)
    redirect_uri = f"{settings.OAUTH_REDIRECT_URL}/auth/{provider}/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/auth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback and create/login user"""
    if provider not in ['google', 'microsoft', 'facebook']:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    try:
        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)

        # Get user info from provider
        if provider == 'google':
            user_info = token.get('userinfo')
            oauth_id = user_info['sub']
            email = user_info['email']
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
        elif provider == 'microsoft':
            user_info = token.get('userinfo')
            oauth_id = user_info['sub']
            email = user_info['email']
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
        elif provider == 'facebook':
            resp = await client.get('https://graph.facebook.com/me?fields=id,name,email', token=token)
            user_info = resp.json()
            oauth_id = user_info['id']
            email = user_info.get('email')
            name_parts = user_info.get('name', '').split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by OAuth provider")

        # Find or create user
        result = await db.execute(
            select(User).filter(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        user = result.scalars().first()

        if not user:
            # Check if email already exists
            result = await db.execute(select(User).filter(User.email == email))
            existing_user = result.scalars().first()

            if existing_user:
                # Link OAuth to existing user
                existing_user.oauth_provider = provider
                existing_user.oauth_id = oauth_id
                existing_user.oauth_access_token = token.get('access_token')
                existing_user.oauth_refresh_token = token.get('refresh_token')
                existing_user.oauth_token_expires_at = datetime.fromtimestamp(token.get('expires_at', 0))
                user = existing_user
            else:
                # Create new user
                username = email.split('@')[0] + '_' + provider
                user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    oauth_access_token=token.get('access_token'),
                    oauth_refresh_token=token.get('refresh_token'),
                    oauth_token_expires_at=datetime.fromtimestamp(token.get('expires_at', 0)),
                    role=UserRole.VIEWER,
                    is_active=True,
                    is_superuser=False
                )
                db.add(user)
        else:
            # Update OAuth tokens
            user.oauth_access_token = token.get('access_token')
            user.oauth_refresh_token = token.get('refresh_token')
            user.oauth_token_expires_at = datetime.fromtimestamp(token.get('expires_at', 0))
            user.last_login = datetime.utcnow()

        await db.commit()
        await db.refresh(user)

        # Create JWT tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        # Redirect to frontend with tokens
        redirect_url = f"{settings.OAUTH_REDIRECT_URL}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth authentication failed: {str(e)}")
```

## 7. Frontend Implementation

### Install Google OAuth Library

```bash
cd frontend
npm install @react-oauth/google
```

### Update Login Page

Add to `frontend/src/pages/Login.tsx`:

```typescript
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';

// In your component
const handleGoogleSuccess = async (credentialResponse: any) => {
  try {
    // Google One Tap returns an ID token, we need to exchange it
    // Redirect to backend OAuth endpoint
    window.location.href = `${process.env.REACT_APP_API_URL}/auth/google/login`;
  } catch (error) {
    console.error('Google login failed:', error);
  }
};

// In JSX
<GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
  <div className="mt-4">
    <GoogleLogin
      onSuccess={handleGoogleSuccess}
      onError={() => console.error('Google login failed')}
      text="signin_with"
      shape="rectangular"
      theme="outline"
      size="large"
    />
  </div>
</GoogleOAuthProvider>

{/* Alternative: Manual OAuth Button */}
<button
  onClick={() => window.location.href = `${process.env.REACT_APP_API_URL}/auth/google/login`}
  className="w-full flex items-center justify-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
>
  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
    {/* Google Icon SVG */}
  </svg>
  Sign in with Google
</button>
```

### Handle OAuth Callback

Create `frontend/src/pages/AuthCallback.tsx`:

```typescript
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');

    if (accessToken && refreshToken) {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  }, [searchParams, navigate]);

  return <div>Processing authentication...</div>;
};

export default AuthCallback;
```

Add route in `App.tsx`:

```typescript
<Route path="/auth/callback" element={<AuthCallback />} />
```

### Environment Variables

Add to `frontend/.env`:

```env
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## 8. Testing

### Test OAuth Login Flow:

1. Start services: `docker compose up`
2. Navigate to login page
3. Click "Sign in with Google"
4. Complete Google authentication
5. You should be redirected back and logged in
6. Check Users page as super admin - new OAuth user should appear with VIEWER role and NO airports assigned

### Verify User Restrictions:

1. Login as OAuth user
2. Should NOT see any airports (empty list)
3. Login as super admin
4. Assign airports to OAuth user
5. Login as OAuth user again
6. Should now see assigned airports

## 9. Security Considerations

1. **OAuth Tokens**: Stored in database but should be encrypted in production
2. **HTTPS**: Always use HTTPS in production
3. **CORS**: Configure properly for your domain
4. **Token Expiry**: OAuth tokens expire and should be refreshed
5. **Redirect URLs**: Must match exactly in OAuth provider settings

## 10. Troubleshooting

### "redirect_uri_mismatch" Error
- Ensure redirect URI in code matches OAuth provider settings exactly
- Check protocol (http vs https)

### "invalid_client" Error
- Verify Client ID and Secret are correct
- Check environment variables are loaded

### User Created But Can't Access Data
- This is expected! Super admin must assign airports
- Check user role is set correctly

### OAuth Provider Returns No Email
- Some providers require explicit email scope
- Facebook users must grant email permission

## Next Steps

After completing setup:
1. Test each OAuth provider
2. Configure production URLs
3. Set up SSL certificates
4. Add proper error handling in frontend
5. Consider adding MFA for sensitive operations
