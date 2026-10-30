import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/useAuth';
import { useRole } from '../hooks/useRole';

type AppShellProps = { children: ReactNode };

const navigation = [
  { to: '/', label: 'nav.home' },
  { to: '/farms', label: 'nav.farms' },
  { to: '/flocks', label: 'nav.flocks' },
  { to: '/daily', label: 'nav.daily' },
] as const;

export default function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const role = useRole();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">
            P
          </span>
          <span>{t('appName')}</span>
        </Link>
        <span className="workspace-label">{t('workspace')}</span>
        <button
          className="profile-button"
          type="button"
          onClick={() => void logout()}
        >
          {t('auth.signOut')}
        </button>
      </header>
      <div className="page-frame">
        <aside className="sidebar" aria-label={t('mainNavigation')}>
          <nav aria-label={t('mainNavigation')}>
            {[
              ...navigation,
              ...(role === 'owner'
                ? [{ to: '/settings', label: 'nav.settings' }]
                : []),
              ...(role === 'owner' || role === 'manager' || role === 'accountant'
                ? [{ to: '/reports', label: 'nav.reports' }]
                : []),
            ].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `nav-link${isActive ? ' is-active' : ''}`
                }
              >
                {t(item.label)}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="main-content">{children}</main>
      </div>
      <nav className="mobile-nav" aria-label={t('mainNavigation')}>
        {[
          ...navigation,
          ...(role === 'owner'
            ? [{ to: '/settings', label: 'nav.settings' }]
            : []),
          ...(role === 'owner' || role === 'manager' || role === 'accountant'
            ? [{ to: '/reports', label: 'nav.reports' }]
            : []),
        ].map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'}>
            {t(item.label)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
