const tailwindcss = require('tailwindcss');
const autoprefixer = require('autoprefixer');

module.exports = {
  style: {
    postcss: {
      mode: 'extends',
      loaderOptions: (postcssLoaderOptions) => {
        postcssLoaderOptions.postcssOptions.plugins = [
          tailwindcss('./tailwind.config.js'),
          autoprefixer,
        ];
        return postcssLoaderOptions;
      },
    },
  },
  devServer: {
    // Fix WebSocket connection for Docker
    client: {
      webSocketURL: {
        hostname: 'localhost',
        pathname: '/ws',
        port: 3001, // Use the host port, not container port
        protocol: 'ws',
      },
    },
    // Allow connections from any host (needed for Docker)
    allowedHosts: 'all',
  },
};