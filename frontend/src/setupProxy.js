const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Proxy all /api requests and preserve the full path
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8002',
      changeOrigin: true,
      logLevel: 'debug'
      // No pathRewrite - let the default behavior preserve the path
    })
  );
};