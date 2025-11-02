# E2E Testing Setup Guide

This guide walks you through setting up and running end-to-end tests for Context Studio.

## Initial Setup

### 1. Install Playwright and Dependencies

From the `/ux` directory:

```bash
npm install
```

This installs all dependencies including `@playwright/test`.

### 2. Install Playwright Browsers

```bash
npx playwright install
```

This downloads the browser binaries needed for testing (Chromium, Firefox, WebKit).

### 3. Verify Backend Setup

Ensure the Python backend is properly configured:

```bash
cd ../local-server

# Check if virtual environment exists
ls .venv

# If not, create it:
python -m venv .venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running Tests

### First Test Run

From the `/ux` directory:

```bash
# Run all E2E tests in headless mode
npm run test:e2e
```

**What happens during test execution:**

1. ✅ Test databases cleaned in `/local-server/datafiles/e2e-test/`
2. 🐍 Python backend starts on port 8001 (using `config.e2e.json`)
3. ⚛️ Vite dev server starts on port 3101 (using `.env.e2e`)
4. ⏳ Waits for both servers to be ready
5. 🧪 Runs all test files in `e2e/tests/*.spec.ts`
6. 🧹 Stops both servers
7. 📊 Generates HTML report

### Development Workflow

**UI Mode (Recommended for development):**

```bash
npm run test:e2e:ui
```

This opens Playwright's UI where you can:
- See all tests
- Run individual tests
- Watch tests execute in real-time
- Debug with time-travel debugging
- View trace files

**Headed Mode (See the browser):**

```bash
npm run test:e2e:headed
```

**Debug Mode (Step through tests):**

```bash
npm run test:e2e:debug
```

**View Last Test Report:**

```bash
npm run test:e2e:report
```

## Project Structure

```
context-studio/
├── local-server/
│   ├── config.e2e.json              # E2E backend configuration
│   ├── datafiles/e2e-test/          # Isolated test databases (auto-created)
│   ├── api/health.py                # Health check endpoint
│   └── ...
└── ux/
    ├── e2e/
    │   ├── fixtures/                # Test utilities
    │   │   └── test-helpers.ts
    │   ├── tests/                   # Test files
    │   │   ├── example.spec.ts
    │   │   └── structure-nodes.spec.ts
    │   ├── global-setup.ts          # Server startup
    │   ├── global-teardown.ts       # Server shutdown
    │   └── README.md                # Detailed testing guide
    ├── playwright.config.ts         # Playwright configuration
    ├── .env.e2e                     # E2E environment variables
    └── package.json                 # E2E scripts
```

## Writing Your First Test

1. Create a new file in `e2e/tests/`:

```typescript
// e2e/tests/my-feature.spec.ts
import { test, expect } from '@playwright/test';

test('should do something', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // Your test here
  await expect(page).toHaveTitle(/Context Studio/);
});
```

2. Run it:

```bash
npm run test:e2e:ui
```

3. Select your test in the UI and watch it run

## Troubleshooting

### "Address already in use" Error

Kill existing processes:

```bash
# macOS/Linux
lsof -ti:8001 -ti:3101 | xargs kill -9

# Windows
netstat -ano | findstr :8001
netstat -ano | findstr :3101
taskkill /PID <PID> /F
```

### Tests Timeout During Setup

1. Check backend logs:
   ```bash
   tail -f local-server/logs/context_studio_e2e.log
   ```

2. Increase timeout in `global-setup.ts`:
   ```typescript
   await waitForUrl('http://localhost:8001/health', 60000); // 60 seconds
   ```

3. Verify virtual environment:
   ```bash
   which python  # Should point to .venv/bin/python
   ```

### "Virtual environment not found"

```bash
cd local-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Won't Start

```bash
cd ux
rm -rf node_modules package-lock.json
npm install
```

### Database Migration Errors

Delete test databases and let them be recreated:

```bash
rm -rf local-server/datafiles/e2e-test
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install backend dependencies
        run: |
          cd local-server
          python -m venv .venv
          source .venv/bin/activate
          pip install -r requirements.txt

      - name: Install frontend dependencies
        run: |
          cd ux
          npm ci

      - name: Install Playwright browsers
        run: |
          cd ux
          npx playwright install --with-deps

      - name: Run E2E tests
        run: |
          cd ux
          npm run test:e2e

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: ux/playwright-report/
          retention-days: 30
```

## Configuration Details

### Backend Configuration (`config.e2e.json`)

- **Port**: 8001 (different from dev port 8000)
- **Databases**: Isolated in `/datafiles/e2e-test/`
- **Logging**: WARNING level to reduce noise
- **Features**: LLM and web search disabled for speed
- **CORS**: Only allows `http://localhost:3101`

### Frontend Configuration (`.env.e2e`)

- **API URL**: `http://localhost:8001` (E2E backend)
- **Environment**: `e2e-test` identifier

### Playwright Configuration (`playwright.config.ts`)

- **Workers**: 1 (sequential execution)
- **Timeout**: 30 seconds per test
- **Retries**: 0 locally, 2 in CI
- **Browsers**: Chromium (Firefox/WebKit available)
- **Artifacts**: Screenshots on failure, traces on retry

## Best Practices

1. **Use data-testid**: Add to your React components
   ```tsx
   <button data-testid="submit-button">Submit</button>
   ```

2. **Wait for app ready**: Use helper function
   ```typescript
   await waitForAppReady(page);
   ```

3. **Validate backend**: Don't just test UI
   ```typescript
   const data = await apiRequest(page, '/api/endpoint');
   expect(data).toBeDefined();
   ```

4. **Keep tests independent**: Don't rely on execution order

5. **Use descriptive names**:
   ```typescript
   test('should create layer and navigate to domains', ...);
   ```

## Next Steps

1. ✅ Setup complete - you can now run E2E tests
2. 📝 Write tests for your features (see `e2e/tests/structure-nodes.spec.ts` for examples)
3. 🏷️ Add `data-testid` attributes to your UI components
4. 🔄 Integrate into your CI/CD pipeline
5. 📚 Read `/ux/e2e/README.md` for detailed testing guide

## Getting Help

- **Playwright Docs**: https://playwright.dev/docs/intro
- **Best Practices**: https://playwright.dev/docs/best-practices
- **Discord**: https://discord.com/invite/playwright

## Quick Reference

```bash
# Common commands (from /ux directory)
npm run test:e2e           # Run all tests (headless)
npm run test:e2e:ui        # UI mode (development)
npm run test:e2e:headed    # See browser (debugging)
npm run test:e2e:debug     # Step through tests
npm run test:e2e:report    # View last report

# Playwright CLI
npx playwright test                    # Run tests
npx playwright test --headed          # Run with browser visible
npx playwright test --debug           # Debug mode
npx playwright test example.spec.ts   # Run specific file
npx playwright test --grep "create"   # Run tests matching pattern
npx playwright show-report            # Open report
npx playwright codegen                # Generate test code
```
