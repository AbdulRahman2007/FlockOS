import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm, useWatch } from 'react-hook-form';
import { useSearchParams } from 'react-router-dom';
import { z } from 'zod';
import { useRole } from '../hooks/useRole';
import { api } from '../services/api';

type Flock = {
  id: string;
  farm_id: string;
  name: string;
  status: 'active' | 'closed';
  placed_birds: number;
};
type Page<T> = { items: T[]; total: number };
type DailyRecord = {
  id: string;
  record_date: string;
  deaths: number;
  culling: number;
  feed_used_kg: string;
  water_liters: string;
  temperature_c: string;
  notes: string | null;
  version: number;
  closing_birds: number;
};
type DailyList = {
  items: DailyRecord[];
  missing_dates: string[];
  total: number;
};
type Draft = {
  values: DailyValues;
  idempotencyKey: string;
  pendingCreate: boolean;
};

const numeric = (value: string) =>
  value.trim() !== '' && !Number.isNaN(Number(value));
const dailySchema = z.object({
  deaths: z
    .string()
    .refine((value) => /^\d+$/.test(value), 'Enter a whole number, such as 0.'),
  culling: z
    .string()
    .refine((value) => /^\d+$/.test(value), 'Enter a whole number, such as 0.'),
  feed_used_kg: z
    .string()
    .refine(numeric, 'Enter feed used in kilograms.')
    .refine((value) => Number(value) >= 0, 'Feed used cannot be below zero.'),
  water_liters: z
    .string()
    .refine(numeric, 'Enter water used in liters.')
    .refine((value) => Number(value) >= 0, 'Water used cannot be below zero.'),
  temperature_c: z
    .string()
    .refine(numeric, 'Enter the temperature in °C.')
    .refine(
      (value) => Number(value) >= -10 && Number(value) <= 60,
      'Enter a value from -10 to 60.',
    ),
  notes: z.string().max(2000, 'Keep notes under 2,000 characters.'),
});
type DailyValues = z.infer<typeof dailySchema>;

function localDateInKarachi() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(
    new Date(),
  );
}

function makeKey() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}

function readDraft(key: string): Draft | null {
  try {
    const value = localStorage.getItem(key);
    return value ? (JSON.parse(value) as Draft) : null;
  } catch {
    return null;
  }
}

export default function DailyEntryPage() {
  const { t } = useTranslation();
  const role = useRole();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [recordDate, setRecordDate] = useState(localDateInKarachi);
  const [saved, setSaved] = useState(false);
  const [draftKey, setDraftKey] = useState('');
  const idempotencyKey = useRef('');
  const initializedKey = useRef('');
  const pendingCreate = useRef(false);
  const form = useForm<DailyValues>({
    resolver: zodResolver(dailySchema),
    defaultValues: {
      deaths: '0',
      culling: '0',
      feed_used_kg: '0',
      water_liters: '0',
      temperature_c: '',
      notes: '',
    },
  });
  const watchedValues = useWatch({ control: form.control });

  const flocksQuery = useQuery({
    queryKey: ['flocks', 'daily-entry'],
    queryFn: async () =>
      (
        await api.get<Page<Flock>>('/flocks', {
          params: { limit: 100, status: 'active' },
        })
      ).data.items.filter((flock) => flock.status === 'active'),
  });
  const flocks = useMemo(() => flocksQuery.data ?? [], [flocksQuery.data]);
  const requestedFlockId = searchParams.get('flockId');
  const selectedFlock = useMemo(
    () =>
      flocks.find((flock) => flock.id === requestedFlockId) ??
      flocks.find((flock) => flock.status === 'active') ??
      null,
    [flocks, requestedFlockId],
  );
  const flockId = selectedFlock?.id ?? '';
  const recordsQuery = useQuery({
    enabled: Boolean(flockId),
    queryKey: ['daily-records', flockId],
    queryFn: async () =>
      (await api.get<DailyList>(`/flocks/${flockId}/daily-records`)).data,
  });
  const records = recordsQuery.data;
  const existingRecord = records?.items.find(
    (record) => record.record_date === recordDate,
  );
  const storageKey = flockId ? `pouktry.daily.${flockId}.${recordDate}` : '';

  useEffect(() => {
    if (!storageKey || !records) return;
    const formKey = `${storageKey}.${existingRecord?.id ?? 'new'}`;
    if (initializedKey.current === formKey) return;
    const draft = readDraft(storageKey);
    const lastRecord = records.items.at(-1);
    const initialValues: DailyValues = {
      deaths: '0',
      culling: '0',
      feed_used_kg: lastRecord?.feed_used_kg ?? '0',
      water_liters: lastRecord?.water_liters ?? '0',
      temperature_c: lastRecord?.temperature_c ?? '',
      notes: '',
    };
    form.reset(
      draft?.values ??
        (existingRecord
          ? {
              deaths: String(existingRecord.deaths),
              culling: String(existingRecord.culling),
              feed_used_kg: existingRecord.feed_used_kg,
              water_liters: existingRecord.water_liters,
              temperature_c: existingRecord.temperature_c,
              notes: existingRecord.notes ?? '',
            }
          : initialValues),
    );
    idempotencyKey.current = draft?.idempotencyKey ?? makeKey();
    pendingCreate.current = draft?.pendingCreate ?? false;
    setDraftKey(storageKey);
    initializedKey.current = formKey;
  }, [existingRecord, form, records, storageKey]);

  useEffect(() => {
    if (!draftKey || !idempotencyKey.current || !watchedValues.deaths) return;
    const draft: Draft = {
      values: watchedValues as DailyValues,
      idempotencyKey: idempotencyKey.current,
      pendingCreate: pendingCreate.current,
    };
    localStorage.setItem(draftKey, JSON.stringify(draft));
  }, [draftKey, watchedValues]);

  const queryKey = ['daily-records', flockId] as const;
  const submit = useMutation({
    mutationFn: async (values: DailyValues) => {
      const body = {
        record_date: recordDate,
        deaths: Number(values.deaths),
        culling: Number(values.culling),
        feed_used_kg: values.feed_used_kg,
        water_liters: values.water_liters,
        temperature_c: values.temperature_c,
        notes: values.notes || null,
      };
      if (existingRecord && !pendingCreate.current) {
        return (
          await api.patch<DailyRecord>(`/daily-records/${existingRecord.id}`, {
            ...body,
            expected_version: existingRecord.version,
          })
        ).data;
      }
      return (
        await api.post<DailyRecord>(`/flocks/${flockId}/daily-records`, body, {
          headers: { 'Idempotency-Key': idempotencyKey.current },
        })
      ).data;
    },
    onMutate: async (values) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<DailyList>(queryKey);
      if (!existingRecord) pendingCreate.current = true;
      if (draftKey) {
        localStorage.setItem(
          draftKey,
          JSON.stringify({
            values,
            idempotencyKey: idempotencyKey.current,
            pendingCreate: pendingCreate.current,
          } satisfies Draft),
        );
      }
      if (previous) {
        const optimistic: DailyRecord = {
          id: existingRecord?.id ?? 'optimistic',
          record_date: recordDate,
          deaths: Number(values.deaths),
          culling: Number(values.culling),
          feed_used_kg: values.feed_used_kg,
          water_liters: values.water_liters,
          temperature_c: values.temperature_c,
          notes: values.notes,
          version: existingRecord?.version ?? 1,
          closing_birds:
            existingRecord?.closing_birds ?? selectedFlock?.placed_birds ?? 0,
        };
        queryClient.setQueryData<DailyList>(queryKey, {
          ...previous,
          items: [
            ...previous.items.filter((item) => item.record_date !== recordDate),
            optimistic,
          ],
          total: previous.total + (existingRecord ? 0 : 1),
          missing_dates: previous.missing_dates.filter(
            (item) => item !== recordDate,
          ),
        });
      }
      setSaved(false);
      return { previous };
    },
    onError: (_error, _values, context) => {
      if (context?.previous)
        queryClient.setQueryData(queryKey, context.previous);
    },
    onSuccess: () => {
      if (draftKey) localStorage.removeItem(draftKey);
      pendingCreate.current = false;
      idempotencyKey.current = makeKey();
      setSaved(true);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const errors = submit.error as {
    response?: { data?: { error?: { message?: string } } };
  } | null;
  const missingDates = records?.missing_dates ?? [];
  const canEdit = role === 'owner' || role === 'manager' || role === 'worker';

  return (
    <section className="daily-entry-page" aria-labelledby="daily-entry-title">
      <p className="eyebrow">{t('daily.eyebrow')}</p>
      <h1 id="daily-entry-title">{t('daily.title')}</h1>
      <p className="daily-description">{t('daily.description')}</p>

      {flocksQuery.isPending ? <p role="status">{t('daily.loading')}</p> : null}
      {flocksQuery.isError ? (
        <div role="alert" className="daily-error">
          <p>{t('daily.loadError')}</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => void flocksQuery.refetch()}
          >
            {t('daily.retry')}
          </button>
        </div>
      ) : null}
      {!flocksQuery.isPending && flocks.length === 0 ? (
        <p className="empty-state">{t('daily.noFlocks')}</p>
      ) : null}

      {flocks.length > 0 && selectedFlock ? (
        <>
          <div className="daily-context">
            <label>
              {t('daily.flock')}
              <select
                value={flockId}
                onChange={(event) => {
                  initializedKey.current = '';
                  setSaved(false);
                  setSearchParams({ flockId: event.target.value });
                }}
              >
                {flocks.map((flock) => (
                  <option key={flock.id} value={flock.id}>
                    {flock.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t('daily.date')}
              <input
                type="date"
                value={recordDate}
                onChange={(event) => {
                  initializedKey.current = '';
                  setSaved(false);
                  setRecordDate(event.target.value);
                }}
              />
            </label>
          </div>

          {recordsQuery.isError ? (
            <div role="alert" className="daily-error">
              <p>{t('daily.loadError')}</p>
              <button
                className="primary-button"
                type="button"
                onClick={() => void recordsQuery.refetch()}
              >
                {t('daily.retry')}
              </button>
            </div>
          ) : null}
          {recordsQuery.isPending ? (
            <p role="status">{t('daily.loading')}</p>
          ) : null}

          {records && missingDates.length > 0 ? (
            <p className="daily-gap-notice" role="status">
              {t('daily.gapNotice', { count: missingDates.length })}
            </p>
          ) : null}
          {records && missingDates.length === 0 ? (
            <p className="daily-complete-notice">{t('daily.noGaps')}</p>
          ) : null}

          {records && canEdit ? (
            <form
              className="daily-entry-card"
              onSubmit={form.handleSubmit((values) => submit.mutate(values))}
            >
              <div className="daily-number-grid">
                <label>
                  {t('daily.deaths')}
                  <input
                    inputMode="numeric"
                    type="number"
                    min="0"
                    step="1"
                    aria-label={t('daily.deaths')}
                    {...form.register('deaths')}
                  />
                  <span className="field-error">
                    {form.formState.errors.deaths?.message}
                  </span>
                </label>
                <label>
                  {t('daily.culling')}
                  <input
                    inputMode="numeric"
                    type="number"
                    min="0"
                    step="1"
                    aria-label={t('daily.culling')}
                    {...form.register('culling')}
                  />
                  <span className="field-error">
                    {form.formState.errors.culling?.message}
                  </span>
                </label>
                <label>
                  {t('daily.feed')}
                  <input
                    inputMode="decimal"
                    type="number"
                    min="0"
                    step="0.001"
                    aria-label={t('daily.feed')}
                    {...form.register('feed_used_kg')}
                  />
                  <span className="field-error">
                    {form.formState.errors.feed_used_kg?.message}
                  </span>
                </label>
                <label>
                  {t('daily.water')}
                  <input
                    inputMode="decimal"
                    type="number"
                    min="0"
                    step="0.01"
                    aria-label={t('daily.water')}
                    {...form.register('water_liters')}
                  />
                  <span className="field-error">
                    {form.formState.errors.water_liters?.message}
                  </span>
                </label>
                <label>
                  {t('daily.temperature')}
                  <input
                    inputMode="decimal"
                    type="number"
                    min="-10"
                    max="60"
                    step="0.01"
                    aria-label={t('daily.temperature')}
                    {...form.register('temperature_c')}
                  />
                  <span className="field-error">
                    {form.formState.errors.temperature_c?.message}
                  </span>
                </label>
              </div>
              <label>
                {t('daily.notes')}
                <textarea
                  rows={2}
                  maxLength={2000}
                  {...form.register('notes')}
                />
                <span className="field-error">
                  {form.formState.errors.notes?.message}
                </span>
              </label>
              <div className="daily-submit-row">
                <button
                  className="primary-button"
                  type="submit"
                  disabled={
                    submit.isPending ||
                    (!form.formState.isDirty && Boolean(existingRecord))
                  }
                >
                  {submit.isPending
                    ? t('daily.saving')
                    : existingRecord
                      ? t('daily.update')
                      : t('daily.save')}
                </button>
                <span aria-live="polite" role="status">
                  {submit.isPending
                    ? t('daily.saving')
                    : saved
                      ? t('daily.saved')
                      : existingRecord
                        ? t('daily.editing')
                        : t('daily.draftSaved')}
                </span>
              </div>
              {submit.isError ? (
                <p className="daily-error" role="alert">
                  {errors?.response?.data?.error?.message ??
                    t('daily.submitError')}{' '}
                  {t('daily.retryHint')}
                </p>
              ) : null}
            </form>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
