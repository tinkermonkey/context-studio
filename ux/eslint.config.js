import tailwindcss from 'eslint-plugin-tailwindcss';

export default [
  {
    ignores: ['dist', 'node_modules', 'coverage', 'build'],
  },
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      tailwindcss,
    },
    rules: {
      'tailwindcss/classnames-order': 'warn',
      'tailwindcss/no-custom-class-name': 'warn',
      'tailwindcss/no-contradicting-classname': 'error',
    },
  },
];
