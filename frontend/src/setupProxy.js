const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Proxy all /api requests and preserve the full path
  // Use 'backend' as the hostname since we're running in Docker
  const target = process.env.REACT_APP_BACKEND_URL || 'http://backend:8000';

  app.use(
    '/api',
    createProxyMiddleware({
      target: target,
      changeOrigin: true,
      logLevel: 'debug'
      // No pathRewrite - let the default behavior preserve the path
    })
  );
};