import { useQuery } from '@tanstack/react-query';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import { useRole } from '../hooks/useRole';

type Metric = { value: number | string | null; status: string };
type Dashboard = {
  as_of: string;
  empty: boolean;
  metrics: Record<string, Metric>;
  alerts: { kind: string; message: string; flock_id: string | null }[];
  trends: {
    day: string;
    mortality_percent?: number | string | null;
    feed_used_kg?: number | string | null;
    average_weight_kg?: number | string | null;
    target_weight_kg?: number | string | null;
    flock_name?: string | null;
  }[];
};
type Farm = { id: string; name: string };
type Flock = { id: string; farm_id: string; name: string; status: string };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };

const priceSchema = z.object({
  farm_id: z.string().min(1),
  effective_on: z.string().min(1),
  price_per_kg_pkr: z.string().refine((value) => Number(value) >= 0 && Number.isFinite(Number(value))),
});
const costSchema = z.object({
  farm_id: z.string().min(1),
  flock_id: z.string().min(1),
  incurred_on: z.string().min(1),
  amount_pkr: z.string().refine((value) => Number(value) > 0 && Number.isFinite(Number(value))),
  description: z.string().trim().min(1).max(240),
});

const metricKeys = [
  'live_birds',
  'mortality_percent',
  'fcr',
  'feed_cover_days',
  'estimated_profit_pkr',
] as const;
const karachiToday = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Karachi' });

export default function DashboardPage() {
  const { t } = useTranslation();
  const role = useRole();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => (await api.get<Dashboard>('/dashboard')).data,
    staleTime: 60_000,
  });
  const data = query.data;
  const farmsQuery = useQuery({
    enabled: role !== 'worker' && role !== 'super_admin',
    queryKey: ['dashboard-farms'],
    queryFn: async () => (await api.get<Page<Farm>>('/farms?limit=100&offset=0')).data,
  });
  const flocksQuery = useQuery({
    enabled: role !== 'worker' && role !== 'super_admin',
    queryKey: ['dashboard-flocks'],
    queryFn: async () => (await api.get<Page<Flock>>('/flocks?limit=100&offset=0')).data,
  });
  const priceForm = useForm<z.infer<typeof priceSchema>>({
    resolver: zodResolver(priceSchema),
    defaultValues: { farm_id: '', effective_on: karachiToday(), price_per_kg_pkr: '' },
  });
  const costForm = useForm<z.infer<typeof costSchema>>({
    resolver: zodResolver(costSchema),
    defaultValues: { farm_id: '', flock_id: '', incurred_on: karachiToday(), amount_pkr: '', description: '' },
  });
  const selectedFarm = useWatch({ control: costForm.control, name: 'farm_id' });
  const addPrice = useMutation({
    mutationFn: (values: z.infer<typeof priceSchema>) =>
      api.post(`/farms/${values.farm_id}/market-prices`, {
        effective_on: values.effective_on,
        price_per_kg_pkr: Number(values.price_per_kg_pkr),
      }),
    onSuccess: () => {
      priceForm.reset({ farm_id: '', effective_on: karachiToday(), price_per_kg_pkr: '' });
      void client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
  const addCost = useMutation({
    mutationFn: (values: z.infer<typeof costSchema>) =>
      api.post(`/farms/${values.farm_id}/direct-costs`, {
        flock_id: values.flock_id,
        incurred_on: values.incurred_on,
        amount_pkr: Number(values.amount_pkr),
        description: values.description,
      }),
    onSuccess: () => {
      costForm.reset({ farm_id: '', flock_id: '', incurred_on: karachiToday(), amount_pkr: '', description: '' });
      void client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
  const operations = data?.trends.filter(
    (point) => point.mortality_percent != null || point.feed_used_kg != null,
  ) ?? [];
  const weights = data?.trends.filter((point) => point.average_weight_kg != null) ?? [];
  const valueText = (key: (typeof metricKeys)[number], metric: Metric | undefined) => {
    if (metric?.value == null) return t('dashboard.unavailable');
    if (key === 'estimated_profit_pkr') {
      return new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: 'PKR',
        maximumFractionDigits: 0,
      }).format(Number(metric.value));
    }
    if (key === 'mortality_percent') return `${Number(metric.value).toFixed(2)}%`;
    if (key === 'fcr') return Number(metric.value).toFixed(2);
    if (key === 'feed_cover_days') return `${Number(metric.value).toFixed(1)} ${t('dashboard.days')}`;
    return new Intl.NumberFormat().format(Number(metric.value));
  };

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <header className="dashboard-heading">
        <div>
          <p className="eyebrow">{t('dashboard.eyebrow')}</p>
          <h1 id="dashboard-title">{t('dashboard.title')}</h1>
        </div>
        {data && <p className="dashboard-as-of">{t('dashboard.asOf', { date: data.as_of })}</p>}
      </header>
      {query.isLoading ? (
        <div className="dashboard-metrics" aria-label={t('dashboard.loading')}>
          {metricKeys.map((key) => <div className="metric-skeleton" key={key} />)}
        </div>
      ) : query.isError ? (
        <div className="daily-error" role="alert">
          <p>{t('dashboard.loadError')}</p>
          <button className="primary-button" type="button" onClick={() => void query.refetch()}>
            {t('dashboard.retry')}
          </button>
        </div>
      ) : data?.empty ? (
        <p className="empty-state">{t('dashboard.empty')}</p>
      ) : data ? (
        <>
          <div className="dashboard-metrics">
            {metricKeys
              .filter((key) => key !== 'estimated_profit_pkr' || role !== 'worker')
              .map((key) => {
                const metric = data.metrics[key];
                return (
                  <article className="metric-card" key={key}>
                    <h2>{t(`dashboard.metrics.${key}`)}</h2>
                    <p>{valueText(key, metric)}</p>
                    {metric?.status === 'partial_excludes_shared_farm_costs' && (
                      <small>{t('dashboard.partialProfit')}</small>
                    )}
                    {metric?.status === 'partial_excludes_sales_and_transfers' && (
                      <small>{t('dashboard.partialBirdCount')}</small>
                    )}
                    {metric && metric.value == null && (
                      <small>{t(`dashboard.metricStatus.${metric.status}`)}</small>
                    )}
                  </article>
                );
              })}
          </div>
          <section className="dashboard-section" aria-labelledby="alerts-title">
            <h2 id="alerts-title">{t('dashboard.alerts')}</h2>
            {data.alerts.length === 0 ? (
              <p className="empty-state">{t('dashboard.noAlerts')}</p>
            ) : (
              <ul className="dashboard-alerts">
                {data.alerts.map((alert, index) => (
                  <li key={`${alert.kind}-${alert.flock_id ?? index}`}>
                    {t(`dashboard.alertKinds.${alert.kind}`)}
                  </li>
                ))}
              </ul>
            )}
          </section>
          {role !== 'worker' && role !== 'super_admin' && (
            <section className="dashboard-section finance-inputs" aria-labelledby="finance-inputs-title">
              <h2 id="finance-inputs-title">{t('dashboard.financeInputs')}</h2>
              {farmsQuery.isError || flocksQuery.isError ? (
                <p role="alert">{t('dashboard.inputsLoadError')}</p>
              ) : farmsQuery.isLoading || flocksQuery.isLoading ? (
                <p role="status">{t('dashboard.loadingInputs')}</p>
              ) : (
                <div className="dashboard-charts">
                  <form onSubmit={priceForm.handleSubmit((values) => addPrice.mutate(values))}>
                    <h3>{t('dashboard.addMarketPrice')}</h3>
                    <label>{t('dashboard.farm')}
                      <select {...priceForm.register('farm_id')}>
                        <option value="">{t('dashboard.chooseFarm')}</option>
                        {farmsQuery.data?.items.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
                      </select>
                    </label>
                    <label>{t('dashboard.effectiveDate')}<input type="date" {...priceForm.register('effective_on')} /></label>
                    <label>{t('dashboard.pricePerKg')}<input inputMode="decimal" {...priceForm.register('price_per_kg_pkr')} /></label>
                    {Object.values(priceForm.formState.errors).length > 0 && <p className="field-error">{t('dashboard.fixFields')}</p>}
                    {addPrice.isError && <p role="alert">{t('dashboard.saveError')}</p>}
                    {addPrice.isSuccess && <p role="status">{t('dashboard.saved')}</p>}
                    <button className="primary-button" disabled={addPrice.isPending}>{t('dashboard.savePrice')}</button>
                  </form>
                  <form onSubmit={costForm.handleSubmit((values) => addCost.mutate(values))}>
                    <h3>{t('dashboard.addDirectCost')}</h3>
                    <label>{t('dashboard.farm')}
                      <select {...costForm.register('farm_id')}>
                        <option value="">{t('dashboard.chooseFarm')}</option>
                        {farmsQuery.data?.items.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
                      </select>
                    </label>
                    <label>{t('dashboard.flock')}
                      <select {...costForm.register('flock_id')}>
                        <option value="">{t('dashboard.chooseFlock')}</option>
                        {flocksQuery.data?.items.filter((flock) => flock.farm_id === selectedFarm).map((flock) => <option key={flock.id} value={flock.id}>{flock.name}</option>)}
                      </select>
                    </label>
                    <label>{t('dashboard.costDate')}<input type="date" {...costForm.register('incurred_on')} /></label>
                    <label>{t('dashboard.amountPkr')}<input inputMode="decimal" {...costForm.register('amount_pkr')} /></label>
                    <label>{t('dashboard.costDescription')}<input {...costForm.register('description')} /></label>
                    {Object.values(costForm.formState.errors).length > 0 && <p className="field-error">{t('dashboard.fixFields')}</p>}
                    {addCost.isError && <p role="alert">{t('dashboard.saveError')}</p>}
                    {addCost.isSuccess && <p role="status">{t('dashboard.saved')}</p>}
                    <button className="primary-button" disabled={addCost.isPending}>{t('dashboard.saveCost')}</button>
                  </form>
                </div>
              )}
            </section>
          )}
          <div className="dashboard-charts">
            <section className="dashboard-section" aria-labelledby="mortality-title">
              <h2 id="mortality-title">{t('dashboard.mortalityTrend')}</h2>
              {operations.length === 0 ? <p className="empty-state">{t('dashboard.noTrend')}</p> : (
                <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
                  <LineChart data={operations}>
                    <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" /><YAxis /><Tooltip />
                    <Line dataKey="mortality_percent" name={t('dashboard.mortalityPercent')} stroke="#b45309" connectNulls />
                  </LineChart>
                </ResponsiveContainer></div>
              )}
            </section>
            <section className="dashboard-section" aria-labelledby="feed-title">
              <h2 id="feed-title">{t('dashboard.feedTrend')}</h2>
              {operations.length === 0 ? <p className="empty-state">{t('dashboard.noTrend')}</p> : (
                <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
                  <BarChart data={operations}>
                    <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" /><YAxis /><Tooltip />
                    <Bar dataKey="feed_used_kg" name={t('dashboard.feedUsed')} fill="#0f5b55" />
                  </BarChart>
                </ResponsiveContainer></div>
              )}
            </section>
            <section className="dashboard-section" aria-labelledby="weight-title">
              <h2 id="weight-title">{t('dashboard.weightTrend')}</h2>
              {weights.length === 0 ? <p className="empty-state">{t('dashboard.noWeight')}</p> : (
                <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
                  <LineChart data={weights}>
                    <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" /><YAxis /><Tooltip />
                    <Line dataKey="average_weight_kg" name={t('dashboard.averageWeight')} stroke="#155eef" />
                    <Line dataKey="target_weight_kg" name={t('dashboard.targetWeight')} stroke="#6b7280" strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer></div>
              )}
              {weights.length > 0 && weights.every((point) => point.target_weight_kg == null) && (
                <p className="empty-state">{t('dashboard.targetNotConfigured')}</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
