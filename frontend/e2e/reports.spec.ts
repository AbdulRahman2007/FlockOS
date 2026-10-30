import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('owner can filter a report and download its CSV', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const token = `e30.${Buffer.from(JSON.stringify({ role: 'owner' })).toString('base64url')}.sig`;
  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({
      json: { access_token: token, token_type: 'bearer', expires_in: 600 },
    }),
  );
  await page.route('**/api/v1/farms**', (route) =>
    route.fulfill({
      json: {
        items: [{ id: 'farm-1', name: 'North Farm' }],
        total: 1,
        limit: 100,
        offset: 0,
      },
    }),
  );
  await page.route('**/api/v1/flocks**', (route) =>
    route.fulfill({
      json: {
        items: [{ id: 'flock-1', farm_id: 'farm-1', name: 'Flock A' }],
        total: 1,
        limit: 100,
        offset: 0,
      },
    }),
  );
  await page.route('**/api/v1/reports/flocks**', (route) => {
    if (route.request().url().includes('export.csv')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'flock,live_birds\nFlock A,97\n',
      });
    }
    return route.fulfill({
      json: {
        items: [
          {
            flock_id: 'flock-1',
            flock: 'Flock A',
            farm: 'North Farm',
            status: 'active',
            placed_birds: 100,
            live_birds: 97,
          },
        ],
        total: 1,
        totals: { placed_birds: 100, live_birds: 97 },
        limit: 50,
        offset: 0,
      },
    });
  });

  await page.goto('/reports');
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '97' })).toBeVisible();
  await page.getByLabel('Farm').selectOption({ label: 'North Farm' });
  await expect(page.getByRole('cell', { name: 'Flock A' })).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(accessibility.violations).toEqual([]);

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^pouktry-flocks-/);
});
