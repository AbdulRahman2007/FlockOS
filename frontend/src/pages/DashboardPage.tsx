import { useTranslation } from 'react-i18next';

export default function DashboardPage() {
  const { t } = useTranslation();
  return (
    <section className="welcome-card" aria-labelledby="welcome-title">
      <p className="eyebrow">{t('dashboard.eyebrow')}</p>
      <h1 id="welcome-title">{t('dashboard.title')}</h1>
      <p className="welcome-copy">{t('dashboard.description')}</p>
      <div className="setup-note">
        <h2>{t('dashboard.setupTitle')}</h2>
        <p>{t('dashboard.setupDescription')}</p>
      </div>
    </section>
  );
}
