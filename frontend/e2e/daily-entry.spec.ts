import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';

const flockId = 'e88e9e37-680c-4d2a-9e90-79cc788e8738';
const today = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Karachi',
}).format(new Date());
const fields = [
  ['Birds died', '12'],
  ['Birds removed', '0'],
  ['Feed used (kg)', '142.5'],
  ['Water used (liters)', '310'],
  ['Temperature (°C)', '29.5'],
] as const;

async function prepareDailyEntry(
  page: Page,
  options: { recordsUnavailable?: boolean } = {},
) {
  await page.setViewportSize({ width: 390, height: 844 });
  const token = `e30.${Buffer.from(JSON.stringify({ role: 'owner' })).toString('base64url')}.sig`;
  let createRequests = 0;
  let savedRecord: Record<string, unknown> | null = null;
  let recordsUnavailable = options.recordsUnavailable ?? false;

  await page.route('**/api/v1/auth/refresh', (route) =>
    route.fulfill({
      json: { access_token: token, token_type: 'bearer', expires_in: 600 },
    }),
  );
  await page.route('**/api/v1/flocks**', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: flockId,
            farm_id: 'cf61ec4a-ff2b-4bed-92c3-f11a7eae8b14',
            name: 'Mobile test flock',
            status: 'active',
            placed_birds: 5000,
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      },
    }),
  );
  await page.route(
    `**/api/v1/flocks/${flockId}/daily-records`,
    async (route) => {
      if (route.request().method() === 'GET') {
        if (recordsUnavailable) {
          await route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
          return;
        }
        await route.fulfill({
          json: {
            items: savedRecord ? [savedRecord] : [],
            missing_dates: [],
            total: savedRecord ? 1 : 0,
            limit: 100,
            offset: 0,
          },
        });
        return;
      }
      createRequests += 1;
      await new Promise((resolve) => setTimeout(resolve, 180));
      const payload = route.request().postDataJSON();
      savedRecord = {
        id: '5df3bd11-7131-4cf7-b44c-7ecf53a8e08a',
        flock_id: flockId,
        ...payload,
        version: 1,
        closing_birds: 4988,
        created_by: '493e61a6-817c-48e1-8482-cd553bc56473',
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({ status: 201, json: savedRecord });
    },
  );

  await page.goto(`/daily?flockId=${flockId}`);
  await expect(
    page.getByRole('heading', { name: 'Daily flock record' }),
  ).toBeVisible();
  return {
    createCount: () => createRequests,
    record: () => savedRecord,
    restoreRecords: () => {
      recordsUnavailable = false;
    },
  };
}

async function fillDailyRecord(page: Page) {
  for (const [label, value] of fields) {
    await page.getByRole('spinbutton', { name: label }).fill(value);
  }
}

test('mobile daily entry submits a full day in six actions', async ({
  page,
}) => {
  const state = await prepareDailyEntry(page);
  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  let actions = 0;
  for (const [label, value] of fields) {
    await page.getByRole('spinbutton', { name: label }).fill(value);
    actions += 1;
  }

  await page.getByRole('button', { name: 'Save today’s record' }).click();
  actions += 1;
  await expect(
    page.getByRole('status').filter({ hasText: 'Record saved' }),
  ).toBeVisible();

  expect(actions).toBe(6);
  expect(state.createCount()).toBe(1);
  expect(state.record()).toMatchObject({
    record_date: today,
    deaths: 12,
    feed_used_kg: '142.5',
    water_liters: '310',
    temperature_c: '29.5',
  });
});

test('mobile double submit creates one record', async ({ page }) => {
  const state = await prepareDailyEntry(page);
  await fillDailyRecord(page);

  await page.getByRole('button', { name: 'Save today’s record' }).dblclick();
  await expect(
    page.getByRole('status').filter({ hasText: 'Record saved' }),
  ).toBeVisible();

  expect(state.createCount()).toBe(1);
  expect(state.record()).not.toBeNull();
});

test('daily entry retries after a temporary records load failure', async ({
  page,
}) => {
  const state = await prepareDailyEntry(page, { recordsUnavailable: true });

  await expect(page.getByRole('alert')).toContainText(
    'Could not load flock records',
    { timeout: 15_000 },
  );
  state.restoreRecords();
  await page.getByRole('button', { name: 'Retry' }).click();

  await expect(
    page.getByRole('spinbutton', { name: 'Birds died' }),
  ).toBeVisible();
});
