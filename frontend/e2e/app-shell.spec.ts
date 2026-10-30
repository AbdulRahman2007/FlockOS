import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('shows invitation-only sign in when there is no session', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(
    page.getByText('Accounts are available by invitation only.'),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});

test('creates a farm, shed and placed flock through the UI and API', async ({
  page,
}) => {
  const email = process.env.E2E_OWNER_EMAIL;
  const password = process.env.E2E_OWNER_PASSWORD;
  test.skip(
    !email || !password,
    'Set E2E_OWNER_EMAIL and E2E_OWNER_PASSWORD for a provisioned Owner.',
  );

  await page.goto('/login');
  await page.getByLabel('Email address').fill(email!);
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/');

  await page.goto('/farms');
  const unique = Date.now().toString();
  const emptyFarm = `E2E Empty Farm ${unique}`;
  await page.getByLabel('Farm name').fill(emptyFarm);
  await page.getByRole('button', { name: 'Save farm' }).click();
  await page.getByRole('button', { name: emptyFarm, exact: true }).waitFor();
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: `Delete ${emptyFarm}` }).click();
  await expect(
    page.getByRole('button', { name: emptyFarm, exact: true }),
  ).toHaveCount(0);

  const farmName = `E2E Farm ${unique}`;
  await page.getByLabel('Farm name').fill(farmName);
  await page.getByLabel('Location (optional)').fill('Lahore');
  await page.getByRole('button', { name: 'Save farm' }).click();
  const renamedFarm = `${farmName} updated`;
  await page.getByRole('button', { name: `Edit ${farmName}` }).click();
  await page.getByLabel('Farm name').fill(renamedFarm);
  await page.getByRole('button', { name: 'Update farm' }).click();
  await page.getByRole('button', { name: renamedFarm, exact: true }).click();
  await page.getByLabel('Shed name').fill('Shed A');
  await page.getByLabel('Capacity in birds').fill('5000');
  await page.getByRole('button', { name: 'Save shed' }).click();
  await expect(page.getByText(/Shed A.*capacity 5000/)).toBeVisible();
  await page.getByLabel('Shed name').fill('Spare Shed');
  await page.getByLabel('Capacity in birds').fill('100');
  await page.getByRole('button', { name: 'Save shed' }).click();
  await page.getByRole('button', { name: 'Delete Spare Shed' }).waitFor();
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: 'Delete Spare Shed' }).click();
  await expect(
    page.getByRole('button', { name: 'Delete Spare Shed' }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Edit Shed A' }).click();
  await page.getByLabel('Shed name').fill('Shed A Updated');
  await page.getByRole('button', { name: 'Update shed' }).click();
  await expect(page.getByText(/Shed A Updated.*capacity 5000/)).toBeVisible();

  await page.goto('/flocks');
  await expect(
    page.getByText(
      'Placed flocks are kept for record integrity. Close a flock to lock it; deletion is unavailable.',
    ),
  ).toBeVisible();
  await page.getByLabel('Farm').selectOption({ label: renamedFarm });
  await page
    .getByLabel('Shed')
    .selectOption({ label: 'Shed A Updated (5000 birds)' });
  const flockName = `Golden flock ${unique}`;
  await page.getByLabel('Flock name').fill(flockName);
  await page.getByLabel('Birds placed').fill('5000');
  await page.getByLabel('Chick source').fill('E2E Hatchery');
  await page.getByRole('button', { name: 'Save flock' }).click();
  await expect(
    page.getByText(new RegExp(`${flockName}.*active.*5,000 birds`)),
  ).toBeVisible();
  await page.getByRole('button', { name: `Edit ${flockName}` }).click();
  const renamedFlock = `${flockName} updated`;
  await page.getByLabel('Flock name').first().fill(renamedFlock);
  await page.getByRole('button', { name: 'Update flock' }).click();
  await expect(
    page.getByText(new RegExp(`${renamedFlock}.*active.*5,000 birds`)),
  ).toBeVisible();
});
