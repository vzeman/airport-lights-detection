import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const error = searchParams.get('error');
    const message = searchParams.get('message');

    if (error) {
      // OAuth failed, redirect to login with error message
      console.error('OAuth error:', message);
      alert(`OAuth authentication failed: ${message || error}`);
      navigate('/login');
      return;
    }

    if (accessToken && refreshToken) {
      // Store tokens in localStorage
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);

      // Redirect to dashboard
      navigate('/');
    } else {
      // No tokens received, redirect to login
      navigate('/login');
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-lg font-medium">Processing authentication...</p>
        <p className="text-sm text-muted-foreground">Please wait while we log you in</p>
      </div>
    </div>
  );
};

export default AuthCallback;
