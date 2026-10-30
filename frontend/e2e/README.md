Playwright specs placeholder; browser tooling is deferred to Phase 2.

# Browser tests

The farm-to-flock Playwright flow uses a real running API/database and an already-provisioned Owner account. Install the browser once with `npx playwright install chrome`. Start PostgreSQL and migrate it, then start the API and Vite app in separate PowerShell terminals. Set `E2E_OWNER_EMAIL`, `E2E_OWNER_PASSWORD`, and `VITE_API_URL` in the test process before running `npm run e2e`. The test creates uniquely named farm data and does not delete it.

The test account must be an Owner in a disposable development tenant because the flow writes farms, sheds, and placements.
