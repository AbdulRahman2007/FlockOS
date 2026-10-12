import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('application shell', () => {
  it('renders the localized home screen and navigation', async () => {
    render(<App />);

    expect(
      await screen.findByRole('heading', { name: 'Welcome to POUKTRY' }),
    ).toBeVisible();
    expect(
      screen.getAllByRole('navigation', {
        name: 'Main navigation',
        hidden: true,
      }),
    ).toHaveLength(2);
  });
});
