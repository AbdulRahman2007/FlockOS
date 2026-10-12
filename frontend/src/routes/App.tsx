import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../layouts/AppShell';

const DashboardPage = lazy(() => import('../pages/DashboardPage'));
const FarmsPage = lazy(() => import('../pages/FarmsPage'));
const FlocksPage = lazy(() => import('../pages/FlocksPage'));
const DailyEntryPage = lazy(() => import('../pages/DailyEntryPage'));

function LoadingState() {
  const { t } = useTranslation();
  return (
    <p className="loading-state" role="status">
      {t('loading')}...
    </p>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<LoadingState />}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/farms" element={<FarmsPage />} />
            <Route path="/flocks" element={<FlocksPage />} />
            <Route path="/daily" element={<DailyEntryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}
