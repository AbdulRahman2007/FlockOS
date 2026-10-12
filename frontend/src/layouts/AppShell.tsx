import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

type AppShellProps = { children: ReactNode };

const navigation = [
  { to: '/', label: 'nav.home' },
  { to: '/farms', label: 'nav.farms' },
  { to: '/flocks', label: 'nav.flocks' },
  { to: '/daily', label: 'nav.daily' },
] as const;

export default function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label={t('appName')}>
          <span className="brand-mark" aria-hidden="true">
            P
          </span>
          <span>{t('appName')}</span>
        </Link>
        <span className="workspace-label">{t('workspace')}</span>
        <button
          className="profile-button"
          type="button"
          aria-label={t('profileMenu')}
        >
          A
        </button>
      </header>
      <div className="page-frame">
        <aside className="sidebar" aria-label={t('mainNavigation')}>
          <nav aria-label={t('mainNavigation')}>
            {navigation.map((item) => (
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
        {navigation.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'}>
            {t(item.label)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
