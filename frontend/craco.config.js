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
};