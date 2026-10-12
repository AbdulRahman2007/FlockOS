import { expect, test } from '@playwright/test';

test('loads the responsive app shell', async ({ page }) => {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Welcome to POUKTRY' }),
  ).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Main navigation' }).first(),
  ).toBeVisible();
});
