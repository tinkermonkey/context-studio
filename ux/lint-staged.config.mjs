// validate-selectors is a whole-project check (it scans all of src/ and e2e/),
// so we run it once via a function — ignoring the staged file list lint-staged
// would otherwise append — whenever a commit touches code or the registry.
export default {
  "*.{ts,tsx,jsx,js,yaml,yml}": () => "npm run validate-selectors",
};
