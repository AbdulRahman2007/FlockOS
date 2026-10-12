import { useTranslation } from 'react-i18next';

type ResourcePageProps = { titleKey: string };

export default function ResourcePage({ titleKey }: ResourcePageProps) {
  const { t } = useTranslation();
  return (
    <section className="welcome-card">
      <p className="eyebrow">{t('workspace')}</p>
      <h1>{t(titleKey)}</h1>
      <p className="welcome-copy">{t('dashboard.setupDescription')}</p>
    </section>
  );
}
