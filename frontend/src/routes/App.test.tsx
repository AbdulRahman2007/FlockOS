import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('../context/useAuth', () => ({
  useAuth: () => ({
    ready: true,
    authenticated: true,
    token: 'test',
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../pages/DashboardPage', () => ({
  default: () => <h1>Farm dashboard</h1>,
}));

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn((path: string) => {
      if (path === '/dashboard') {
        return Promise.resolve({
          data: { as_of: '2026-10-26', empty: true, metrics: {}, alerts: [], trends: [] },
        });
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 100, offset: 0 } });
    }),
  },
}));

describe('application shell', () => {
  it('renders the localized home screen and navigation', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole('heading', { name: 'Farm dashboard' }, { timeout: 5000 }),
    ).toBeVisible();
    expect(
      screen.getAllByRole('navigation', {
        name: 'Main navigation',
        hidden: true,
      }),
    ).toHaveLength(2);
  });
});
