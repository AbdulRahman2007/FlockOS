import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useRole } from '../hooks/useRole';
import { api } from '../services/api';

type Farm = {
  id: string;
  name: string;
  location: string | null;
  timezone: string;
};
type Shed = {
  id: string;
  farm_id: string;
  name: string;
  capacity_birds: number | null;
};
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
const farmSchema = z.object({
  name: z.string().trim().min(1).max(120),
  location: z.string().max(500),
  timezone: z.string().min(1).max(64),
});
const shedSchema = z.object({
  name: z.string().trim().min(1).max(120),
  capacity_birds: z
    .string()
    .refine(
      (value) => value === '' || (/^\d+$/.test(value) && Number(value) > 0),
      'Enter a whole number greater than zero',
    ),
});
type FarmValues = z.infer<typeof farmSchema>;
type ShedValues = z.infer<typeof shedSchema>;

export default function FarmsPage() {
  const role = useRole();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedFarm, setSelectedFarm] = useState('');
  const [editingFarmId, setEditingFarmId] = useState<string | null>(null);
  const [editingShedId, setEditingShedId] = useState<string | null>(null);
  const farmForm = useForm<FarmValues>({
    resolver: zodResolver(farmSchema),
    defaultValues: { name: '', location: '', timezone: 'Asia/Karachi' },
  });
  const shedForm = useForm<ShedValues>({
    resolver: zodResolver(shedSchema),
    defaultValues: { name: '', capacity_birds: '' },
  });
  const farms = useQuery({
    queryKey: ['farms', search],
    queryFn: async () =>
      (
        await api.get<Page<Farm>>('/farms', {
          params: { search, limit: 25, offset: 0 },
        })
      ).data,
  });
  const sheds = useQuery({
    enabled: Boolean(selectedFarm),
    queryKey: ['sheds', selectedFarm],
    queryFn: async () =>
      (
        await api.get<Page<Shed>>(`/farms/${selectedFarm}/sheds`, {
          params: { limit: 25, offset: 0 },
        })
      ).data,
  });
  const createFarm = useMutation({
    mutationFn: async (values: FarmValues) =>
      api.post('/farms', { ...values, location: values.location || null }),
    onSuccess: () => {
      farmForm.reset();
      void queryClient.invalidateQueries({ queryKey: ['farms'] });
    },
  });
  const updateFarm = useMutation({
    mutationFn: async ({ id, values }: { id: string; values: FarmValues }) =>
      api.patch(`/farms/${id}`, {
        ...values,
        location: values.location || null,
      }),
    onSuccess: () => {
      farmForm.reset();
      setEditingFarmId(null);
      void queryClient.invalidateQueries({ queryKey: ['farms'] });
    },
  });
  const deleteFarm = useMutation({
    mutationFn: async (id: string) => api.delete(`/farms/${id}`),
    onSuccess: (_, id) => {
      if (selectedFarm === id) setSelectedFarm('');
      void queryClient.invalidateQueries({ queryKey: ['farms'] });
      void queryClient.invalidateQueries({ queryKey: ['sheds'] });
    },
  });
  const createShed = useMutation({
    mutationFn: async (values: ShedValues) =>
      api.post(`/farms/${selectedFarm}/sheds`, {
        name: values.name,
        capacity_birds: values.capacity_birds
          ? Number(values.capacity_birds)
          : null,
      }),
    onSuccess: () => {
      shedForm.reset();
      void queryClient.invalidateQueries({ queryKey: ['sheds', selectedFarm] });
    },
  });
  const updateShed = useMutation({
    mutationFn: async ({ id, values }: { id: string; values: ShedValues }) =>
      api.patch(`/sheds/${id}`, {
        name: values.name,
        capacity_birds: values.capacity_birds
          ? Number(values.capacity_birds)
          : null,
      }),
    onSuccess: () => {
      shedForm.reset();
      setEditingShedId(null);
      void queryClient.invalidateQueries({ queryKey: ['sheds', selectedFarm] });
    },
  });
  const deleteShed = useMutation({
    mutationFn: async (id: string) => api.delete(`/sheds/${id}`),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['sheds', selectedFarm] }),
  });

  return (
    <section className="resource-page">
      <h1>Farms and sheds</h1>
      <label>
        Search farms
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      {farms.isLoading ? (
        <p role="status">Loading farms…</p>
      ) : farms.isError ? (
        <p role="alert">
          Farms could not be loaded. Check your connection and retry.
        </p>
      ) : farms.data?.items.length ? (
        <ul>
          {farms.data.items.map((farm) => (
            <li key={farm.id}>
              <button
                type="button"
                onClick={() => {
                  setSelectedFarm(farm.id);
                  setEditingShedId(null);
                  shedForm.reset();
                }}
                aria-pressed={selectedFarm === farm.id}
              >
                {farm.name}
              </button>
              {farm.location ? ` - ${farm.location}` : ''}
              {(role === 'owner' || role === 'manager') && (
                <button
                  type="button"
                  aria-label={`Edit ${farm.name}`}
                  onClick={() => {
                    setEditingFarmId(farm.id);
                    farmForm.reset({
                      name: farm.name,
                      location: farm.location ?? '',
                      timezone: farm.timezone,
                    });
                  }}
                >
                  Edit
                </button>
              )}
              {role === 'owner' && (
                <button
                  type="button"
                  aria-label={`Delete ${farm.name}`}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Delete ${farm.name}? It must have no sheds.`,
                      )
                    )
                      deleteFarm.mutate(farm.id);
                  }}
                >
                  Delete
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>No farms yet. Add your first farm below.</p>
      )}
      {(role === 'owner' || editingFarmId !== null) && (
        <form
          onSubmit={farmForm.handleSubmit((values) =>
            editingFarmId
              ? updateFarm.mutate({ id: editingFarmId, values })
              : createFarm.mutate(values),
          )}
        >
          <h2>{editingFarmId ? 'Edit farm' : 'Add a farm'}</h2>
          <label>
            Farm name
            <input {...farmForm.register('name')} />
          </label>
          <p>{farmForm.formState.errors.name?.message}</p>
          <label>
            Location (optional)
            <input {...farmForm.register('location')} />
          </label>
          <label>
            Time zone
            <input {...farmForm.register('timezone')} />
          </label>
          {(createFarm.isError || updateFarm.isError) && (
            <p role="alert">
              Farm was not saved. Check the fields or try again.
            </p>
          )}
          {deleteFarm.isError && (
            <p role="alert">
              Farm was not deleted. Remove its sheds first, then retry.
            </p>
          )}
          <button disabled={createFarm.isPending || updateFarm.isPending}>
            {editingFarmId ? 'Update farm' : 'Save farm'}
          </button>
          {editingFarmId && (
            <button
              type="button"
              onClick={() => {
                setEditingFarmId(null);
                farmForm.reset();
              }}
            >
              Cancel
            </button>
          )}
        </form>
      )}
      {selectedFarm && (
        <>
          <h2>Sheds</h2>
          {sheds.isLoading ? (
            <p role="status">Loading sheds…</p>
          ) : sheds.isError ? (
            <p role="alert">Sheds could not be loaded.</p>
          ) : sheds.data?.items.length ? (
            <ul>
              {sheds.data.items.map((shed) => (
                <li key={shed.id}>
                  {shed.name} - capacity {shed.capacity_birds ?? 'not set'}
                  {(role === 'owner' || role === 'manager') && (
                    <button
                      type="button"
                      aria-label={`Edit ${shed.name}`}
                      onClick={() => {
                        setEditingShedId(shed.id);
                        shedForm.reset({
                          name: shed.name,
                          capacity_birds: shed.capacity_birds?.toString() ?? '',
                        });
                      }}
                    >
                      Edit
                    </button>
                  )}
                  {role === 'owner' && (
                    <button
                      type="button"
                      aria-label={`Delete ${shed.name}`}
                      onClick={() => {
                        if (
                          window.confirm(
                            `Delete ${shed.name}? It must have no flocks.`,
                          )
                        )
                          deleteShed.mutate(shed.id);
                      }}
                    >
                      Delete
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p>No sheds in this farm yet.</p>
          )}
          {(role === 'owner' || role === 'manager') && (
            <form
              onSubmit={shedForm.handleSubmit((values) =>
                editingShedId
                  ? updateShed.mutate({ id: editingShedId, values })
                  : createShed.mutate(values),
              )}
            >
              <h3>{editingShedId ? 'Edit shed' : 'Add a shed'}</h3>
              <label>
                Shed name
                <input {...shedForm.register('name')} />
              </label>
              <p>{shedForm.formState.errors.name?.message}</p>
              <label>
                Capacity in birds
                <input
                  inputMode="numeric"
                  {...shedForm.register('capacity_birds')}
                />
              </label>
              <p>{shedForm.formState.errors.capacity_birds?.message}</p>
              {(createShed.isError || updateShed.isError) && (
                <p role="alert">
                  Shed was not saved. Check capacity or try again.
                </p>
              )}
              {deleteShed.isError && (
                <p role="alert">
                  Shed was not deleted. Remove its flocks first, then retry.
                </p>
              )}
              <button disabled={createShed.isPending || updateShed.isPending}>
                {editingShedId ? 'Update shed' : 'Save shed'}
              </button>
              {editingShedId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingShedId(null);
                    shedForm.reset();
                  }}
                >
                  Cancel
                </button>
              )}
            </form>
          )}
        </>
      )}
    </section>
  );
}
