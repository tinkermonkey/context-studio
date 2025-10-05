# Test Fixtures

This directory contains test fixtures used by the test suite.

## Schema.org Fixtures

### Version Pinning

The Schema.org test fixtures are pinned to a specific version to ensure test reproducibility and stability. This prevents breaking changes in the upstream Schema.org vocabulary from affecting our tests.

**Current Version**: Schema.org 25.0 (2024-Q4 release)

**Source URL**: https://schema.org/version/latest/schemaorg-current-https.jsonld

### Why Pin the Version?

1. **Test Stability**: Upstream changes to Schema.org can introduce new entities, modify existing ones, or change the structure, which could break our tests.

2. **Reproducibility**: Tests should produce the same results across different runs and environments. Pinning the version ensures this.

3. **Controlled Updates**: We can review and test Schema.org updates before incorporating them into our test suite.

### Updating the Schema.org Version

When a new version of Schema.org is released and you want to update the fixtures:

1. **Download the new version**:
   ```bash
   cd /workspace/local-server/tests/fixtures
   wget https://schema.org/version/latest/schemaorg-current-https.jsonld -O schema-org-vX.Y.jsonld
   ```

2. **Update test references**:
   - Update test files that reference the fixture to use the new version
   - Check for any structural changes that might affect tests

3. **Run the test suite**:
   ```bash
   pytest tests/ -v
   ```

4. **Update this README**:
   - Update the "Current Version" section above
   - Document any significant changes or migration notes

5. **Commit the changes**:
   ```bash
   git add tests/fixtures/schema-org-vX.Y.jsonld tests/fixtures/README.md
   git commit -m "Update Schema.org test fixtures to version X.Y"
   ```

### Manual Fixture Creation

For specific test cases, you can create minimal fixtures:

```json
{
  "@context": "https://schema.org/",
  "@graph": [
    {
      "@type": "rdfs:Class",
      "@id": "schema:Thing",
      "rdfs:label": "Thing",
      "rdfs:comment": "The most generic type of item."
    }
  ]
}
```

Save these as `<test-name>-fixture.jsonld` in this directory.

## Other Fixtures

### Embedding Fixtures

Pre-generated embeddings for test data can be stored here to speed up tests and avoid requiring the embedding service to be running.

Example structure:
```
fixtures/
  embeddings/
    test-embeddings.pkl  # Pickled embedding data
    test-embeddings.json # JSON embedding data
```

### Database Fixtures

Test database files should be created fresh for each test run and not committed to the repository. Use temporary files or test-specific databases.

## Best Practices

1. **Keep fixtures small**: Only include the minimum data needed for tests
2. **Document purpose**: Add comments explaining what each fixture tests
3. **Version control**: Commit fixtures to git for reproducibility
4. **Don't commit generated data**: Database files and cached embeddings should be generated during tests
5. **Clean up**: Remove temporary fixtures created during test runs
