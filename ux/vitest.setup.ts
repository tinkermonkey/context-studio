import '@testing-library/jest-dom';
// polyfill for createPortal target in jsdom
if (typeof document !== 'undefined') {
  const root = document.getElementById('root') || document.createElement('div');
  root.setAttribute('id', 'root');
  document.body.appendChild(root);
}
