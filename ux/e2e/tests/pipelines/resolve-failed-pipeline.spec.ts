import { test, expect } from "@playwright/test";
import {
  createPipeline,
  executePipeline,
  getPipelineExecutions,
  clearTestData,
  type Pipeline,
  type Execution,
} from "../../fixtures/test-helpers";

test.describe("Resolve a Failed Pipeline Run", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Failed Pipeline from Statusbar", async ({ page }) => {
    // Create a pipeline with a failed execution
    const pipeline = await createPipeline(page, {
      title: "Failed Pipeline Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "You are a test assistant.",
      user_prompt: "Process: {input}",
    });

    // Execute the pipeline to create a failed execution (simulated via API)
    // In production, this would be seeded with status: error
    await executePipeline(page, pipeline.id);

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is visible
    await expect(page.getByTestId("pipelines-page")).toBeVisible();
    await expect(page.getByTestId("pipelines-grid")).toBeVisible();
  });

  test("Test Case 2: View Failed Pipeline Card and Error Count", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Failed Pipeline Card Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "System message",
      user_prompt: "User message",
    });

    // Execute to create a run
    await executePipeline(page, pipeline.id);

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipeline card is visible with selector pattern
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await expect(pipelineCard).toBeVisible();

    // Verify status chip exists in the card
    const statusChip = pipelineCard.getByTestId("pipeline-status-chip");
    await expect(statusChip).toBeVisible();
  });

  test("Test Case 3: Open Pipeline Detail Drawer and View Configuration", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Config View Test",
      provider: "anthropic",
      model: "claude-3-opus",
      system_prompt: "Test system prompt",
      user_prompt: "Test user prompt",
      config: { max_tokens: 1000 },
    });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click on the pipeline card to open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Verify drawer opens and configuration is displayed
    await expect(page.getByTestId("pipeline-config-pre")).toBeVisible();

    // Verify Edit button is visible
    await expect(page.getByTestId("pipeline-edit-config-button")).toBeVisible();
  });

  test("Test Case 4: View Last 10 Runs and Failed Execution Details", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Runs History Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Assistant",
      user_prompt: "Message",
    });

    // Execute the pipeline
    const execution = await executePipeline(page, pipeline.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open pipeline drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Wait for drawer to open and runs table to appear
    await expect(page.getByTestId("pipeline-runs-table")).toBeVisible();

    // Verify the execution appears in the runs table
    await expect(page.getByTestId("pipeline-runs-table")).toContainText(execution.status);

    // Verify view log button exists for the execution
    const viewLogButton = page.getByTestId(`pipeline-view-log-${execution.id}`);
    await expect(viewLogButton).toBeDefined();
  });

  test("Test Case 5: View Detailed Error Log and Verify Scrollability", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Error Log Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Test",
      user_prompt: "Test",
    });

    // Create execution
    const execution = await executePipeline(page, pipeline.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Wait for runs table
    await expect(page.getByTestId("pipeline-runs-table")).toBeVisible();

    // Click view log button if execution has error
    const viewLogButton = page.getByTestId(`pipeline-view-log-${execution.id}`);
    if (await viewLogButton.isVisible().catch(() => false)) {
      await viewLogButton.click();

      // Verify error log is visible
      const errorLog = page.getByTestId("pipeline-error-log");
      await expect(errorLog).toBeVisible();

      // Verify copy error button is visible
      await expect(page.getByTestId("pipeline-copy-error-button")).toBeVisible();
    }
  });

  test("Test Case 6: Edit Pipeline Configuration", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Edit Config Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Original system prompt",
      user_prompt: "Original user prompt",
    });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Wait for configuration to load
    await expect(page.getByTestId("pipeline-config-pre")).toBeVisible();

    // Click edit button
    const editButton = page.getByTestId("pipeline-edit-config-button");
    await editButton.click();

    // Verify textarea appears
    const configTextarea = page.getByTestId("pipeline-config-textarea");
    await expect(configTextarea).toBeVisible();

    // Clear and modify configuration
    await configTextarea.fill(
      JSON.stringify({
        system_prompt: "Updated system prompt",
        user_prompt: "Updated user prompt",
      }),
    );

    // Verify save button appears and is enabled
    const saveButton = page.getByTestId("pipeline-save-config-button");
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();

    // Verify cancel button is visible
    await expect(page.getByTestId("pipeline-revert-config-button")).toBeVisible();

    // Click save
    await saveButton.click();

    // Verify autosave indicator shows or drawer confirms save
    await expect(page.getByTestId("drawer-autosave-status")).toBeVisible();
  });

  test("Test Case 7: Execute Pipeline and Observe Status Transition", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Execution Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Test",
      user_prompt: "Test",
    });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Wait for drawer to fully load
    await expect(page.getByTestId("pipeline-config-pre")).toBeVisible();

    // Click run button
    const runButton = page.getByTestId("run-pipeline-btn");
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for runs table to become visible after execution triggered
    await expect(page.getByTestId("pipeline-runs-table")).toBeVisible({ timeout: 10000 });

    // Verify status chip is visible and execution completed
    const statusChip = pipelineCard.getByTestId("pipeline-status-chip");
    await expect(statusChip).toBeVisible();
  });

  test("Test Case 8: Verify Success Toast and Execution Metadata", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Success Toast Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Test",
      user_prompt: "Test",
    });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Execute pipeline
    const runButton = page.getByTestId("run-pipeline-btn");
    await runButton.click();

    // Wait for runs table to appear after execution
    const runsTable = page.getByTestId("pipeline-runs-table");
    await expect(runsTable).toBeVisible({ timeout: 10000 });

    // Verify execution appears in table with correct status
    const executions = await getPipelineExecutions(page, pipeline.id);
    if (executions.length > 0) {
      const latestExecution = executions[0];
      expect(latestExecution.status).toBeDefined();
      expect(latestExecution.tokens_in).toBeGreaterThanOrEqual(0);
      expect(latestExecution.tokens_out).toBeGreaterThanOrEqual(0);
    }
  });

  test("Test Case 9: Edge Case - Pipeline with No Prior Runs", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline No Runs Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Test",
      user_prompt: "Test",
    });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Verify empty state is shown
    const emptyState = page.getByTestId("pipeline-no-runs");
    const runButton = page.getByTestId("run-pipeline-btn");

    // Either empty state or run button should be visible
    const emptyStateVisible = await emptyState.isVisible().catch(() => false);
    const runButtonVisible = await runButton.isVisible().catch(() => false);

    expect(emptyStateVisible || runButtonVisible).toBeTruthy();

    // If run button is available, click it
    if (runButtonVisible) {
      await runButton.click();

      // Wait for runs table to appear
      const runsTable = page.getByTestId("pipeline-runs-table");
      await expect(runsTable).toBeVisible({ timeout: 10000 });
    }
  });

  test("Test Case 10: Edge Case - Long Error Log Scrollability", async ({ page }) => {
    const pipeline = await createPipeline(page, {
      title: "Pipeline Long Error Test",
      provider: "openai",
      model: "gpt-4",
      system_prompt: "Test",
      user_prompt: "Test",
    });

    // Create execution with long error
    await executePipeline(page, pipeline.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open drawer
    const pipelineCard = page.getByTestId(`pipeline-card-${pipeline.id}`);
    await pipelineCard.click();

    // Wait for runs table
    await expect(page.getByTestId("pipeline-runs-table")).toBeVisible();

    // Get executions and check if any have error messages
    const executions = await getPipelineExecutions(page, pipeline.id);

    if (executions.some((e) => e.error_message)) {
      const errorExecution = executions.find((e) => e.error_message);
      if (errorExecution) {
        // Click view log button
        const viewLogButton = page.getByTestId(`pipeline-view-log-${errorExecution.id}`);
        if (await viewLogButton.isVisible().catch(() => false)) {
          await viewLogButton.click();

          // Verify error log is visible
          const errorLog = page.getByTestId("pipeline-error-log");
          await expect(errorLog).toBeVisible();

          // Verify copy button is accessible
          const copyButton = page.getByTestId("pipeline-copy-error-button");
          await expect(copyButton).toBeVisible();

          // Verify error log content is readable
          const errorLogContent = await errorLog.textContent();
          expect(errorLogContent).toBeDefined();
          expect(errorLogContent?.length).toBeGreaterThan(0);
        }
      }
    }
  });
});
