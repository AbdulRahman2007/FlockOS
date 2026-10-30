import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import { useRole } from '../hooks/useRole';
import { api } from '../services/api';

type Farm = { id: string; name: string };
type Shed = { id: string; name: string; capacity_birds: number | null };
type Flock = {
  id: string;
  farm_id: string;
  shed_id: string;
  name: string;
  status: 'active' | 'closed';
  locked: boolean;
  placed_birds: number;
};
type Page<T> = { items: T[]; total: number };
const flockSchema = z.object({
  farm_id: z.string().uuid('Choose a farm'),
  shed_id: z.string().uuid('Choose a shed'),
  name: z.string().trim().min(1).max(120),
  placed_on: z.string().min(1),
  bird_count: z
    .string()
    .refine(
      (value) => /^\d+$/.test(value) && Number(value) > 0,
      'Enter a whole number greater than zero',
    ),
  chick_source: z.string().trim().min(1).max(160),
  average_weight_kg: z
    .string()
    .refine(
      (value) =>
        value === '' || (!Number.isNaN(Number(value)) && Number(value) >= 0),
      'Enter zero or a positive weight',
    ),
});
const flockEditSchema = z.object({
  name: z.string().trim().min(1).max(120),
});
type FlockEditValues = z.infer<typeof flockEditSchema>;

export default function FlocksPage() {
  const { t } = useTranslation();
  const role = useRole();
  const queryClient = useQueryClient();
  const [editingFlockId, setEditingFlockId] = useState<string | null>(null);
  const editForm = useForm<FlockEditValues>({
    resolver: zodResolver(flockEditSchema),
    defaultValues: { name: '' },
  });
  const form = useForm({
    resolver: zodResolver(flockSchema),
    defaultValues: {
      farm_id: '',
      shed_id: '',
      name: '',
      placed_on: new Date().toISOString().slice(0, 10),
      bird_count: '',
      chick_source: '',
      average_weight_kg: '',
    },
  });
  const farmId = useWatch({ control: form.control, name: 'farm_id' });
  const farms = useQuery({
    queryKey: ['farms', 'flock-form'],
    queryFn: async () =>
      (await api.get<Page<Farm>>('/farms', { params: { limit: 100 } })).data,
  });
  const sheds = useQuery({
    enabled: Boolean(farmId),
    queryKey: ['sheds', farmId],
    queryFn: async () =>
      (
        await api.get<Page<Shed>>(`/farms/${farmId}/sheds`, {
          params: { limit: 100 },
        })
      ).data,
  });
  const flocks = useQuery({
    queryKey: ['flocks'],
    queryFn: async () =>
      (
        await api.get<Page<Flock>>('/flocks', {
          params: { limit: 25, offset: 0 },
        })
      ).data,
  });
  const create = useMutation({
    mutationFn: async (values: z.infer<typeof flockSchema>) =>
      api.post('/flocks', {
        farm_id: values.farm_id,
        shed_id: values.shed_id,
        name: values.name,
        placement: {
          placed_on: values.placed_on,
          bird_count: Number(values.bird_count),
          chick_source: values.chick_source,
          average_weight_kg: values.average_weight_kg
            ? Number(values.average_weight_kg)
            : null,
        },
      }),
    onSuccess: () => {
      form.reset({
        farm_id: '',
        shed_id: '',
        name: '',
        placed_on: new Date().toISOString().slice(0, 10),
        bird_count: '',
        chick_source: '',
        average_weight_kg: '',
      });
      void queryClient.invalidateQueries({ queryKey: ['flocks'] });
    },
  });
  const close = useMutation({
    mutationFn: async (id: string) => api.post(`/flocks/${id}/close`),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['flocks'] }),
  });
  const update = useMutation({
    mutationFn: async (values: FlockEditValues) =>
      api.patch(`/flocks/${editingFlockId}`, values),
    onSuccess: () => {
      setEditingFlockId(null);
      editForm.reset();
      void queryClient.invalidateQueries({ queryKey: ['flocks'] });
    },
  });
  return (
    <section className="resource-page">
      <h1>Flocks</h1>
      <p>{t('flocks.retained')}</p>
      {flocks.isLoading ? (
        <p role="status">Loading flocks…</p>
      ) : flocks.isError ? (
        <p role="alert">
          Flocks could not be loaded. Check your connection and retry.
        </p>
      ) : flocks.data?.items.length ? (
        <ul>
          {flocks.data.items.map((flock) => (
            <li key={flock.id}>
              <strong>{flock.name}</strong> · {flock.status} ·{' '}
              {flock.placed_birds.toLocaleString()} birds
              {flock.status === 'active' && (
                <Link to={`/daily?flockId=${flock.id}`}>
                  {t('daily.quickEntry')}
                </Link>
              )}{' '}
              {flock.status === 'active' &&
                (role === 'owner' || role === 'manager') && (
                  <button
                    type="button"
                    aria-label={`Edit ${flock.name}`}
                    onClick={() => {
                      setEditingFlockId(flock.id);
                      editForm.reset({ name: flock.name });
                    }}
                  >
                    Edit
                  </button>
                )}{' '}
              {flock.status === 'active' &&
                (role === 'owner' || role === 'manager') && (
                  <button
                    type="button"
                    onClick={() => {
                      if (
                        window.confirm(
                          'Close this flock? It will be locked until an Owner reopens it.',
                        )
                      )
                        close.mutate(flock.id);
                    }}
                  >
                    Close flock
                  </button>
                )}
            </li>
          ))}
        </ul>
      ) : (
        <p>No flocks yet. Create one with its placement details.</p>
      )}
      {editingFlockId && (
        <form
          onSubmit={editForm.handleSubmit((values) => update.mutate(values))}
        >
          <h2>Edit flock</h2>
          <label>
            Flock name
            <input {...editForm.register('name')} />
          </label>
          <p>{editForm.formState.errors.name?.message}</p>
          {update.isError && (
            <p role="alert">
              Flock was not updated. Check the name and try again.
            </p>
          )}
          <button disabled={update.isPending}>Update flock</button>
          <button
            type="button"
            onClick={() => {
              setEditingFlockId(null);
              editForm.reset();
            }}
          >
            Cancel
          </button>
        </form>
      )}{' '}
      {(role === 'owner' || role === 'manager') && (
        <form onSubmit={form.handleSubmit((values) => create.mutate(values))}>
          <h2>Create flock and placement</h2>
          <label>
            Farm
            <select {...form.register('farm_id')}>
              <option value="">Choose farm</option>
              {farms.data?.items.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.name}
                </option>
              ))}
            </select>
          </label>
          <p>{form.formState.errors.farm_id?.message}</p>
          <label>
            Shed
            <select {...form.register('shed_id')}>
              <option value="">Choose shed</option>
              {sheds.data?.items.map((shed) => (
                <option key={shed.id} value={shed.id}>
                  {shed.name}
                  {shed.capacity_birds ? ` (${shed.capacity_birds} birds)` : ''}
                </option>
              ))}
            </select>
          </label>
          <p>{form.formState.errors.shed_id?.message}</p>
          <label>
            Flock name
            <input {...form.register('name')} />
          </label>
          <p>{form.formState.errors.name?.message}</p>
          <label>
            Placement date
            <input type="date" {...form.register('placed_on')} />
          </label>
          <label>
            Birds placed
            <input inputMode="numeric" {...form.register('bird_count')} />
          </label>
          <p>{form.formState.errors.bird_count?.message}</p>
          <label>
            Chick source
            <input {...form.register('chick_source')} />
          </label>
          <p>{form.formState.errors.chick_source?.message}</p>
          <label>
            Average placement weight (kg, optional)
            <input
              inputMode="decimal"
              {...form.register('average_weight_kg')}
            />
          </label>
          <p>{form.formState.errors.average_weight_kg?.message}</p>
          {create.isError && (
            <p role="alert">
              Flock was not saved. Check shed capacity and the details, then
              retry.
            </p>
          )}
          <button disabled={create.isPending}>Save flock</button>
        </form>
      )}
    </section>
  );
}
