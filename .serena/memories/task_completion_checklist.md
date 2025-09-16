# Task Completion Checklist

## After Making Code Changes

### Backend Changes (local-server/)
1. **Code Quality Validation**:
   ```bash
   cd local-server/
   ruff check --fix && mypy .
   ```

2. **Run Tests**:
   ```bash
   # Run relevant unit tests
   pytest tests/unit_tests/ -v
   
   # Run integration tests if applicable
   pytest tests/integration_tests/ -v
   
   # Run all tests for major changes
   pytest -v
   ```

3. **Update API Specs** (if APIs changed):
   ```bash
   python utils/update_api_specs.py
   ```

### Frontend Changes (ux/)
1. **Code Quality**:
   ```bash
   cd ux/
   npm run lint
   npm run type-check
   ```

2. **Update Types** (if backend APIs changed):
   ```bash
   npm run generate-types
   ```

3. **Build Verification**:
   ```bash
   npm run build
   ```

### Cross-functional Changes
1. **Backend First**: Complete and test backend changes
2. **API Updates**: Run `update_api_specs.py` if needed
3. **Frontend Updates**: Update types, then hooks/services, then UX
4. **Full Integration Test**: Test end-to-end functionality

## Before Committing
- [ ] All tests pass
- [ ] Code quality checks pass (ruff, mypy, lint)
- [ ] No compilation errors
- [ ] API specs updated if needed
- [ ] Types regenerated on frontend if needed

## Git Workflow
- Create feature branches for changes
- Use descriptive commit messages
- Only commit when explicitly asked by user
- Use GitHub issues for tracking and documentation