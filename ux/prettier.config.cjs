/** @type {import('prettier').Config} */
/* eslint-disable no-undef */
module.exports = {
  plugins: ["prettier-plugin-tailwindcss"],
  // tailwindcss
  tailwindAttributes: ["theme"],
  tailwindFunctions: ["twMerge", "createTheme"],
};
