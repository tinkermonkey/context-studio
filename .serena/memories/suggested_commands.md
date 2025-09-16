# Suggested Commands for Context Studio Development

## Local Server (Python Backend)

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit_tests/test_crdt_merge_engine.py

# Run with verbose output
pytest -v

# Run specific test categories
pytest -m unit    # Fast unit tests
pytest -m integration    # Integration tests
pytest -m slow    # Slow tests requiring full setup
```

### Code Quality
```bash
# Check code style and fix issues
ruff check --fix

# Type checking
mypy .

# Combined validation
ruff check --fix && mypy .
```

### Development Server
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app:app --reload
```

### Database & Schema
```bash
# Update API specifications after backend changes
python utils/update_api_specs.py
```

## Frontend (React/TypeScript)

### Development
```bash
cd ux/
npm run dev    # Start development server
npm run build  # Build for production
npm run generate-types  # Update types from OpenAPI after backend changes
```

### Code Quality
```bash
cd ux/
npm run lint   # ESLint
npm run type-check  # TypeScript checking
```

## Git & GitHub
```bash
# View GitHub issues
gh issue list
gh issue view <issue-number>

# Create GitHub issue
gh issue create --title "Title" --body "Description"

# Create sub-issue linked to parent
gh issue create --title "Sub-task" --body "Body" --label "bug,backend"
```

## System Commands (macOS)
- `ls` - List files
- `cd` - Change directory  
- `grep` - Search text (prefer `rg` for ripgrep)
- `find` - Find files
- `git` - Git operations