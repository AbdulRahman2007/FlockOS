import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const apiBase = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1';

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/');
}

async function apiSignIn(request: APIRequestContext, email: string, password: string) {
  const response = await request.post(`${apiBase}/auth/login`, { data: { email, password } });
  expect(response.ok(), 'real API login should succeed').toBeTruthy();
  return (await response.json()) as { access_token: string };
}

test('Owner records a sale and partial payment; backend balance and bird count update', async ({ page, request }) => {
  const email = process.env.E2E_OWNER_EMAIL;
  const password = process.env.E2E_OWNER_PASSWORD;
  test.skip(!email || !password, 'Set E2E_OWNER_EMAIL and E2E_OWNER_PASSWORD for a provisioned Owner.');

  const token = await apiSignIn(request, email!, password!);
  const headers = { Authorization: `Bearer ${token.access_token}` };
  const [farmResponse, flockResponse] = await Promise.all([
    request.get(`${apiBase}/farms?limit=100&offset=0`, { headers }),
    request.get(`${apiBase}/flocks?limit=100&offset=0`, { headers }),
  ]);
  expect(farmResponse.ok()).toBeTruthy();
  expect(flockResponse.ok()).toBeTruthy();
  const farmPage = (await farmResponse.json()) as { items: { id: string; name: string }[] };
  const flockPage = (await flockResponse.json()) as { items: { id: string; farm_id: string; name: string; status: string; placed_birds: number }[] };
  const flock = flockPage.items.find((item) => item.status === 'active' && item.placed_birds > 0 && farmPage.items.some((farm) => farm.id === item.farm_id));
  expect(farmPage.items.length, 'provision a farm for the Owner').toBeGreaterThan(0);
  expect(flock, 'provision an active flock with birds for the Owner').toBeTruthy();
  const farm = farmPage.items.find((item) => item.id === flock!.farm_id)!;

  await signIn(page, email!, password!);
  await page.goto('/finance');
  await page.getByLabel('Farm').selectOption(farm.id);
  const buyerName = `Finance E2E ${Date.now()}`;
  await page.getByRole('tab', { name: 'Buyers and suppliers' }).click();
  const buyerSection = page.locator('.finance-party-grid section').first();
  await buyerSection.getByLabel('Name').fill(buyerName);
  await buyerSection.getByRole('button', { name: 'Add buyer' }).click();
  await expect(buyerSection.getByText(buyerName)).toBeVisible();

  await page.getByRole('tab', { name: 'Sales and payments' }).click();
  await page.getByLabel('Flock').selectOption(flock!.id);
  await page.getByLabel('Buyer').selectOption({ label: buyerName });
  await page.getByLabel('Birds sold').fill('1');
  await page.getByLabel('Total live weight (kg)').fill('1.000');
  await page.getByLabel('Rate per kg (PKR)').fill('100.00');
  await page.getByLabel('Sale amount (PKR)').fill('100.00');
  await page.getByRole('button', { name: 'Save sale' }).click();
  await expect(page.getByText('Sale saved and flock bird count updated.')).toBeVisible();

  const updatedFlocksResponse = await request.get(`${apiBase}/flocks?limit=100&offset=0`, { headers });
  expect(updatedFlocksResponse.ok()).toBeTruthy();
  const updatedFlocks = (await updatedFlocksResponse.json()) as { items: typeof flockPage.items };
  expect(updatedFlocks.items.find((item) => item.id === flock!.id)?.placed_birds).toBe(flock!.placed_birds - 1);

  await page.getByLabel('Sale to pay').selectOption({ index: 1 });
  await page.getByLabel('Amount received (PKR)').fill('40.00');
  await page.getByRole('button', { name: 'Save payment' }).click();
  await expect(page.getByText('Payment saved. Buyer balance updated.')).toBeVisible();
  const buyerRow = page.locator('.finance-table-wrap tr').filter({ hasText: buyerName });
  await expect(buyerRow).toContainText(/PKR 60(?:\.00)?/);
});

test('Accountant can view finance and cannot edit operations', async ({ page, request }) => {
  const email = process.env.E2E_ACCOUNTANT_EMAIL;
  const password = process.env.E2E_ACCOUNTANT_PASSWORD;
  test.skip(!email || !password, 'Set E2E_ACCOUNTANT_EMAIL and E2E_ACCOUNTANT_PASSWORD for a provisioned Accountant.');
  const token = await apiSignIn(request, email!, password!);
  await signIn(page, email!, password!);
  await expect(page.getByRole('link', { name: 'Money' })).toBeVisible();
  await page.goto('/finance');
  await expect(page.getByRole('heading', { name: 'Sales and expenses' })).toBeVisible();
  await page.goto('/flocks');
  await expect(page.getByRole('button', { name: 'Save flock' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(0);

  const denied = await request.post(`${apiBase}/farms`, {
    headers: { Authorization: `Bearer ${token.access_token}` },
    data: { name: `Unauthorized finance test ${Date.now()}`, timezone: 'Asia/Karachi' },
  });
  expect(denied.status()).toBe(403);
});

test('Worker cannot reach finance screens or finance endpoints', async ({ page, request }) => {
  const email = process.env.E2E_WORKER_EMAIL;
  const password = process.env.E2E_WORKER_PASSWORD;
  test.skip(!email || !password, 'Set E2E_WORKER_EMAIL and E2E_WORKER_PASSWORD for a provisioned Worker.');
  const token = await apiSignIn(request, email!, password!);
  await signIn(page, email!, password!);
  await expect(page.getByRole('link', { name: 'Money' })).toHaveCount(0);
  await page.goto('/finance');
  await expect(page).toHaveURL('/');
  const denied = await request.get(`${apiBase}/buyers?limit=20&offset=0`, {
    headers: { Authorization: `Bearer ${token.access_token}` },
  });
  expect(denied.status()).toBe(403);
});
