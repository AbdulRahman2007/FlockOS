import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useRole } from '../hooks/useRole';
import { api } from '../services/api';

type Settings = {
  feed_bag_size_kg: string | null;
  target_mortality_percent: string | null;
  target_fcr: string | null;
  manager_daily_window_days: number;
  worker_daily_window_days: number;
  updated_at: string | null;
};
const schema = z.object({
  feed_bag_size_kg: z
    .string()
    .refine(
      (value) =>
        value === '' || (Number(value) > 0 && Number.isFinite(Number(value))),
      'Enter a value greater than zero',
    ),
  target_mortality_percent: z
    .string()
    .refine(
      (value) => value === '' || (Number(value) >= 0 && Number(value) <= 100),
      'Enter a percent from 0 to 100',
    ),
  target_fcr: z
    .string()
    .refine(
      (value) =>
        value === '' || (Number(value) > 0 && Number.isFinite(Number(value))),
      'Enter a value greater than zero',
    ),
  manager_daily_window_days: z
    .string()
    .refine(
      (value) =>
        /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 30,
      'Enter 1 to 30 days.',
    ),
  worker_daily_window_days: z
    .string()
    .refine(
      (value) =>
        /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 30,
      'Enter 1 to 30 days.',
    ),
});
type Values = z.infer<typeof schema>;

export default function SettingsPage() {
  const { t } = useTranslation();
  const role = useRole();
  const client = useQueryClient();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      feed_bag_size_kg: '',
      target_mortality_percent: '',
      target_fcr: '',
      manager_daily_window_days: '7',
      worker_daily_window_days: '1',
    },
  });
  const query = useQuery({
    enabled: role === 'owner',
    queryKey: ['tenant-settings'],
    queryFn: async () => (await api.get<Settings>('/settings')).data,
  });
  useEffect(() => {
    if (!query.data) return;
    form.reset({
      feed_bag_size_kg: query.data.feed_bag_size_kg ?? '',
      target_mortality_percent: query.data.target_mortality_percent ?? '',
      target_fcr: query.data.target_fcr ?? '',
      manager_daily_window_days: String(
        query.data.manager_daily_window_days ?? 7,
      ),
      worker_daily_window_days: String(
        query.data.worker_daily_window_days ?? 1,
      ),
    });
  }, [form, query.data]);
  const save = useMutation({
    mutationFn: async (values: Values) =>
      api.put('/settings', {
        feed_bag_size_kg: values.feed_bag_size_kg
          ? Number(values.feed_bag_size_kg)
          : null,
        target_mortality_percent: values.target_mortality_percent
          ? Number(values.target_mortality_percent)
          : null,
        target_fcr: values.target_fcr ? Number(values.target_fcr) : null,
        manager_daily_window_days: Number(values.manager_daily_window_days),
        worker_daily_window_days: Number(values.worker_daily_window_days),
      }),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ['tenant-settings'] }),
  });
  if (role !== 'owner')
    return (
      <section>
        <h1>{t('settings.title')}</h1>
        <p role="alert">{t('settings.ownerOnly')}</p>
      </section>
    );
  return (
    <section className="resource-page">
      <h1>{t('settings.title')}</h1>
      <p>{t('settings.description')}</p>
      {query.isLoading ? (
        <p role="status">{t('settings.loading')}</p>
      ) : query.isError ? (
        <p role="alert">{t('settings.loadError')}</p>
      ) : (
        <form onSubmit={form.handleSubmit((values) => save.mutate(values))}>
          <label>
            {t('settings.feedBagSize')}
            <input inputMode="decimal" {...form.register('feed_bag_size_kg')} />
          </label>
          <p>{form.formState.errors.feed_bag_size_kg?.message}</p>
          <label>
            {t('settings.targetMortality')}
            <input
              inputMode="decimal"
              {...form.register('target_mortality_percent')}
            />
          </label>
          <p>{form.formState.errors.target_mortality_percent?.message}</p>
          <label>
            {t('settings.targetFcr')}
            <input inputMode="decimal" {...form.register('target_fcr')} />
          </label>
          <p>{form.formState.errors.target_fcr?.message}</p>
          <label>
            {t('settings.managerDailyWindow')}
            <input
              inputMode="numeric"
              type="number"
              min="1"
              max="30"
              {...form.register('manager_daily_window_days')}
            />
          </label>
          <p>{form.formState.errors.manager_daily_window_days?.message}</p>
          <label>
            {t('settings.workerDailyWindow')}
            <input
              inputMode="numeric"
              type="number"
              min="1"
              max="30"
              {...form.register('worker_daily_window_days')}
            />
          </label>
          <p>{form.formState.errors.worker_daily_window_days?.message}</p>
          {save.isError && <p role="alert">{t('settings.saveError')}</p>}
          <button disabled={save.isPending}>{t('settings.save')}</button>
        </form>
      )}
    </section>
  );
}
