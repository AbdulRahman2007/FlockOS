import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useRole } from '../hooks/useRole';
import { api } from '../services/api';

type Farm = { id: string; name: string };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type Snapshot = {
  farm_id: string;
  as_of: string;
  stock_kg: string | null;
  feed_cover_days: string | null;
  status: string;
};
type Event = {
  id: string;
  occurred_on: string;
  event_type: string;
  quantity_kg: string;
  reason: string | null;
  created_by: string;
};
type EventType = 'opening' | 'purchase' | 'return_to_stock' | 'return_to_supplier' | 'adjustment';

const todayInKarachi = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date());

export default function FeedStockPage() {
  const { t } = useTranslation();
  const role = useRole();
  const client = useQueryClient();
  const [farmId, setFarmId] = useState('');
  const [eventType, setEventType] = useState<EventType>('opening');
  const [occurredOn, setOccurredOn] = useState(todayInKarachi);
  const [quantity, setQuantity] = useState('');
  const [reason, setReason] = useState('');
  const editable = role === 'owner' || role === 'manager';
  const farms = useQuery({
    queryKey: ['feed-stock-farms'],
    queryFn: async () =>
      (await api.get<Page<Farm>>('/farms', { params: { limit: 100 } })).data,
  });
  useEffect(() => {
    if (!farmId && farms.data?.items[0]) setFarmId(farms.data.items[0].id);
  }, [farmId, farms.data]);
  const stock = useQuery({
    enabled: farmId !== '',
    queryKey: ['feed-stock', farmId],
    queryFn: async () =>
      (await api.get<Snapshot>(`/farms/${farmId}/feed-stock`)).data,
  });
  const events = useQuery({
    enabled: farmId !== '',
    queryKey: ['feed-stock-events', farmId],
    queryFn: async () =>
      (await api.get<Page<Event>>(`/farms/${farmId}/feed-stock/events`, { params: { limit: 50 } })).data,
  });
  const save = useMutation({
    mutationFn: async () => {
      const amount = Number(quantity);
      if (eventType === 'purchase') {
        return api.post(`/farms/${farmId}/feed-purchases`, {
          purchased_on: occurredOn,
          quantity: amount,
          unit: 'kg',
          amount_pkr: null,
          notes: reason || null,
        });
      }
      return api.post(`/farms/${farmId}/feed-stock/events`, {
        event_type: eventType,
        occurred_on: occurredOn,
        quantity_kg: amount,
        reason: reason || null,
      });
    },
    onSuccess: async () => {
      setQuantity('');
      setReason('');
      await Promise.all([
        client.invalidateQueries({ queryKey: ['feed-stock', farmId] }),
        client.invalidateQueries({ queryKey: ['feed-stock-events', farmId] }),
        client.invalidateQueries({ queryKey: ['dashboard'] }),
        client.invalidateQueries({ queryKey: ['reports'] }),
      ]);
    },
  });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!farmId || !Number.isFinite(Number(quantity))) return;
    save.mutate();
  }

  return (
    <section className="resource-page">
      <h1>{t('feedStock.title')}</h1>
      <label>
        {t('feedStock.farm')}
        <select value={farmId} onChange={(event) => setFarmId(event.target.value)}>
          <option value="">{t('feedStock.chooseFarm')}</option>
          {(farms.data?.items ?? []).map((farm) => (
            <option key={farm.id} value={farm.id}>{farm.name}</option>
          ))}
        </select>
      </label>
      {farms.isLoading && <p role="status">{t('feedStock.loading')}</p>}
      {farms.isError && <p role="alert">{t('feedStock.loadError')}</p>}
      {farmId && (stock.isLoading ? (
        <p role="status">{t('feedStock.loading')}</p>
      ) : stock.isError ? (
        <p role="alert">{t('feedStock.loadError')}</p>
      ) : stock.data ? (
        <section aria-labelledby="feed-stock-summary">
          <h2 id="feed-stock-summary">{t('feedStock.currentStock')}</h2>
          {stock.data.stock_kg == null ? (
            <p>{t('feedStock.missingOpening')}</p>
          ) : (
            <p>{t('feedStock.stockSummary', {
              stock: Number(stock.data.stock_kg).toLocaleString(undefined, { maximumFractionDigits: 3 }),
              cover: stock.data.feed_cover_days == null
                ? t('dashboard.unavailable')
                : Number(stock.data.feed_cover_days).toFixed(2),
            })}</p>
          )}
        </section>
      ) : null)}
      {editable && farmId && (
        <form onSubmit={submit}>
          <h2>{t('feedStock.addMovement')}</h2>
          <label>
            {t('feedStock.type')}
            <select value={eventType} onChange={(event) => setEventType(event.target.value as EventType)}>
              <option value="opening">{t('feedStock.types.opening')}</option>
              <option value="purchase">{t('feedStock.types.purchase')}</option>
              <option value="return_to_stock">{t('feedStock.types.return_to_stock')}</option>
              <option value="return_to_supplier">{t('feedStock.types.return_to_supplier')}</option>
              <option value="adjustment">{t('feedStock.types.adjustment')}</option>
            </select>
          </label>
          <label>
            {t('feedStock.date')}
            <input type="date" value={occurredOn} onChange={(event) => setOccurredOn(event.target.value)} required />
          </label>
          <label>
            {eventType === 'adjustment' ? t('feedStock.adjustmentQuantity') : t('feedStock.quantity')}
            <input
              inputMode="decimal"
              type="number"
              step="0.001"
              min={eventType === 'adjustment' ? undefined : eventType === 'opening' ? '0' : '0.001'}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              required
            />
          </label>
          {eventType === 'adjustment' && <p>{t('feedStock.adjustmentHelp')}</p>}
          <label>
            {eventType === 'adjustment' ? t('feedStock.reasonRequired') : t('feedStock.reason')}
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={1000} />
          </label>
          {save.isError && <p role="alert">{t('feedStock.saveError')}</p>}
          <button disabled={save.isPending || !quantity}>{t('feedStock.save')}</button>
        </form>
      )}
      {farmId && (
        <section aria-labelledby="feed-stock-events">
          <h2 id="feed-stock-events">{t('feedStock.history')}</h2>
          {events.isLoading ? <p role="status">{t('feedStock.loading')}</p> : null}
          {events.isError ? <p role="alert">{t('feedStock.loadError')}</p> : null}
          {events.data?.items.length === 0 ? <p>{t('feedStock.empty')}</p> : null}
          {(events.data?.items ?? []).map((item) => (
            <article className="feed-stock-event" key={`${item.event_type}-${item.id}`}>
              <strong>{t(`feedStock.types.${item.event_type}`)}</strong>
              <span>{item.occurred_on}</span>
              <span>{Number(item.quantity_kg).toLocaleString(undefined, { maximumFractionDigits: 3 })} {t('dashboard.kg')}</span>
              {item.reason && <span>{item.reason}</span>}
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
