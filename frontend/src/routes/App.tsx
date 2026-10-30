import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../layouts/AppShell';
import LoginPage from '../pages/LoginPage';
import { useAuth } from '../context/useAuth';
import { useRole } from '../hooks/useRole';

const DashboardPage = lazy(() => import('../pages/DashboardPage'));
const FarmsPage = lazy(() => import('../pages/FarmsPage'));
const FlocksPage = lazy(() => import('../pages/FlocksPage'));
const DailyEntryPage = lazy(() => import('../pages/DailyEntryPage'));
const SettingsPage = lazy(() => import('../pages/SettingsPage'));
const ReportsPage = lazy(() => import('../pages/ReportsPage'));
const FinancePage = lazy(() => import('../pages/FinancePage'));

function LoadingState() {
  const { t } = useTranslation();
  return (
    <p className="loading-state" role="status">
      {t('loading')}...
    </p>
  );
}

export default function App() {
  const { ready, authenticated } = useAuth();
  const role = useRole();
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            ready && authenticated ? <Navigate to="/" replace /> : <LoginPage />
          }
        />
        <Route
          path="*"
          element={
            !ready ? (
              <LoadingState />
            ) : !authenticated ? (
              <Navigate to="/login" replace />
            ) : (
              <AppShell>
                <Suspense fallback={<LoadingState />}>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/farms" element={<FarmsPage />} />
                    <Route path="/flocks" element={<FlocksPage />} />
                    <Route path="/daily" element={<DailyEntryPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route
                      path="/finance"
                      element={
                        role === 'owner' || role === 'manager' || role === 'accountant' ? (
                          <FinancePage />
                        ) : (
                          <Navigate to="/" replace />
                        )
                      }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Suspense>
              </AppShell>
            )
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
