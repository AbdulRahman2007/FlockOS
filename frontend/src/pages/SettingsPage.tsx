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
  high_daily_mortality_percent: string;
  early_daily_mortality_percent: string;
  early_mortality_days: number;
  feed_cover_threshold_days: string;
  feed_cover_usage_window_days: number;
  fcr_tolerance_percent: string;
  target_weight_curve: { age_day: number; average_weight_kg: string }[];
  manager_daily_window_days: number;
  worker_daily_window_days: number;
  updated_at: string | null;
};
const targetDays = [7, 14, 21, 28, 35] as const;
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
  high_daily_mortality_percent: z.string().refine(
    (value) => Number(value) >= 0 && Number(value) <= 100,
    'Enter a percent from 0 to 100',
  ),
  early_daily_mortality_percent: z.string().refine(
    (value) => Number(value) >= 0 && Number(value) <= 100,
    'Enter a percent from 0 to 100',
  ),
  early_mortality_days: z.string().refine(
    (value) => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 30,
    'Enter 1 to 30 days.',
  ),
  feed_cover_threshold_days: z.string().refine(
    (value) => Number(value) > 0 && Number.isFinite(Number(value)),
    'Enter a value greater than zero',
  ),
  feed_cover_usage_window_days: z.string().refine(
    (value) => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 30,
    'Enter 1 to 30 days.',
  ),
  fcr_tolerance_percent: z.string().refine(
    (value) => Number(value) >= 0 && Number(value) <= 100,
    'Enter a percent from 0 to 100',
  ),
  target_weight_7: z.string().refine((value) => Number(value) > 0, 'Enter a value greater than zero'),
  target_weight_14: z.string().refine((value) => Number(value) > 0, 'Enter a value greater than zero'),
  target_weight_21: z.string().refine((value) => Number(value) > 0, 'Enter a value greater than zero'),
  target_weight_28: z.string().refine((value) => Number(value) > 0, 'Enter a value greater than zero'),
  target_weight_35: z.string().refine((value) => Number(value) > 0, 'Enter a value greater than zero'),
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
      high_daily_mortality_percent: '0.5',
      early_daily_mortality_percent: '1',
      early_mortality_days: '7',
      feed_cover_threshold_days: '3',
      feed_cover_usage_window_days: '3',
      fcr_tolerance_percent: '5',
      target_weight_7: '0.185',
      target_weight_14: '0.465',
      target_weight_21: '0.920',
      target_weight_28: '1.480',
      target_weight_35: '2.050',
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
      high_daily_mortality_percent: query.data.high_daily_mortality_percent,
      early_daily_mortality_percent: query.data.early_daily_mortality_percent,
      early_mortality_days: String(query.data.early_mortality_days),
      feed_cover_threshold_days: query.data.feed_cover_threshold_days,
      feed_cover_usage_window_days: String(query.data.feed_cover_usage_window_days),
      fcr_tolerance_percent: query.data.fcr_tolerance_percent,
      target_weight_7: query.data.target_weight_curve.find((point) => point.age_day === 7)?.average_weight_kg ?? '0.185',
      target_weight_14: query.data.target_weight_curve.find((point) => point.age_day === 14)?.average_weight_kg ?? '0.465',
      target_weight_21: query.data.target_weight_curve.find((point) => point.age_day === 21)?.average_weight_kg ?? '0.920',
      target_weight_28: query.data.target_weight_curve.find((point) => point.age_day === 28)?.average_weight_kg ?? '1.480',
      target_weight_35: query.data.target_weight_curve.find((point) => point.age_day === 35)?.average_weight_kg ?? '2.050',
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
        high_daily_mortality_percent: Number(values.high_daily_mortality_percent),
        early_daily_mortality_percent: Number(values.early_daily_mortality_percent),
        early_mortality_days: Number(values.early_mortality_days),
        feed_cover_threshold_days: Number(values.feed_cover_threshold_days),
        feed_cover_usage_window_days: Number(values.feed_cover_usage_window_days),
        fcr_tolerance_percent: Number(values.fcr_tolerance_percent),
        target_weight_curve: targetDays.map((age_day) => ({
          age_day,
          average_weight_kg: Number(values[`target_weight_${age_day}` as keyof Values]),
        })),
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
            {t('settings.highDailyMortality')}
            <input inputMode="decimal" {...form.register('high_daily_mortality_percent')} />
          </label>
          <p>{form.formState.errors.high_daily_mortality_percent?.message}</p>
          <label>
            {t('settings.earlyDailyMortality')}
            <input inputMode="decimal" {...form.register('early_daily_mortality_percent')} />
          </label>
          <p>{form.formState.errors.early_daily_mortality_percent?.message}</p>
          <label>
            {t('settings.earlyMortalityDays')}
            <input inputMode="numeric" type="number" min="1" max="30" {...form.register('early_mortality_days')} />
          </label>
          <p>{form.formState.errors.early_mortality_days?.message}</p>
          <label>
            {t('settings.feedCoverThreshold')}
            <input inputMode="decimal" {...form.register('feed_cover_threshold_days')} />
          </label>
          <p>{form.formState.errors.feed_cover_threshold_days?.message}</p>
          <label>
            {t('settings.feedCoverWindow')}
            <input inputMode="numeric" type="number" min="1" max="30" {...form.register('feed_cover_usage_window_days')} />
          </label>
          <p>{form.formState.errors.feed_cover_usage_window_days?.message}</p>
          <label>
            {t('settings.fcrTolerance')}
            <input inputMode="decimal" {...form.register('fcr_tolerance_percent')} />
          </label>
          <p>{form.formState.errors.fcr_tolerance_percent?.message}</p>
          <fieldset>
            <legend>{t('settings.targetWeightCurve')}</legend>
            {targetDays.map((day) => {
              const field = `target_weight_${day}` as const;
              return (
                <div key={day}>
                  <label>
                    {t('settings.targetWeightDay', { day })}
                    <input inputMode="decimal" {...form.register(field)} />
                  </label>
                  <p>{form.formState.errors[field]?.message}</p>
                </div>
              );
            })}
          </fieldset>
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
