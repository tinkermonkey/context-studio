import { test, expect } from "../../fixtures/app-test";

// The status bar says only what the app knows (#1651): no fixed encoding string,
// no uptime labelled as a sync time, and a sync item that follows the sync status API.
const SYNC_ITEM = '[data-testid="statusbar-sync"]';

test.describe("Status bar", () => {
  test("shows the real sync state and no placeholders", async ({ page }) => {
    const statusResponse = page.waitForResponse("**/api/v1/versioning/sync/status");
    await page.goto("/app");
    const status = await (await statusResponse).json();

    const item = page.locator(SYNC_ITEM);
    await expect(item).toBeVisible();
    if (!status.is_configured) {
      await expect(item).toHaveText("sync off");
    } else if (status.is_degraded) {
      await expect(item).toHaveText("sync degraded");
    } else if (status.unprocessed_count > 0) {
      await expect(item).toHaveText(`${status.unprocessed_count} unsynced`);
    } else {
      await expect(item).toHaveText(/^(synced .+|never synced)$/);
    }

    const statusbar = page.locator(".statusbar");
    await expect(statusbar).not.toContainText("UTF-8");
    await expect(statusbar).not.toContainText("syncing…");
  });
});
