/**
 * SQLAlchemy URLs of the isolated E2E databases, relative to local-server/
 * (the backend's working directory). global-setup migrates them; fixtures that
 * seed rows directly write to the same files.
 */
export const TEST_DB_URLS = {
  local: "sqlite:///./datafiles/e2e-test/local.db",
  operations: "sqlite:///./datafiles/e2e-test/operations.db",
} as const;
