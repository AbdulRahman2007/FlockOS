import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';

type ReportKind =
  | 'flocks'
  | 'mortality'
  | 'feed'
  | 'weight'
  | 'financial'
  | 'profitability';
type ReportRow = Record<string, string | number | null>;
type ReportResponse = {
  items: ReportRow[];
  total: number;
  totals: Record<string, string | number | null>;
  limit: number;
  offset: number;
};
type Choice = { id: string; name: string; farm_id?: string };
type Page<T> = { items: T[]; total: number };

const reportKinds: ReportKind[] = [
  'flocks',
  'mortality',
  'feed',
  'weight',
  'financial',
  'profitability',
];
const todayInKarachi = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(
    new Date(),
  );
const monthAgo = () => {
  const date = new Date(`${todayInKarachi()}T12:00:00`);
  date.setDate(date.getDate() - 29);
  return new Intl.DateTimeFormat('en-CA').format(date);
};

export default function ReportsPage() {
  const { t } = useTranslation();
  const [kind, setKind] = useState<ReportKind>('flocks');
  const [startDate, setStartDate] = useState(monthAgo);
  const [endDate, setEndDate] = useState(todayInKarachi);
  const [farmId, setFarmId] = useState('');
  const [flockId, setFlockId] = useState('');
  const [offset, setOffset] = useState(0);
  const [printRows, setPrintRows] = useState<ReportRow[] | null>(null);
  const limit = 50;
  const farms = useQuery({
    queryKey: ['reports-farms'],
    queryFn: async () =>
      (await api.get<Page<Choice>>('/farms', { params: { limit: 100 } })).data,
  });
  const flocks = useQuery({
    queryKey: ['reports-flocks', farmId],
    queryFn: async () =>
      (
        await api.get<Page<Choice>>('/flocks', {
          params: { farm_id: farmId || undefined, limit: 100 },
        })
      ).data,
  });
  const query = useQuery({
    queryKey: ['reports', kind, startDate, endDate, farmId, flockId, offset],
    enabled: startDate !== '' && endDate !== '' && endDate >= startDate,
    queryFn: async () =>
      (
        await api.get<ReportResponse>(`/reports/${kind}`, {
          params: {
            start_date: startDate,
            end_date: endDate,
            farm_id: farmId || undefined,
            flock_id: flockId || undefined,
            limit,
            offset,
          },
        })
      ).data,
  });
  const columns = useMemo(
    () => Object.keys((printRows ?? query.data?.items)?.[0] ?? {}),
    [printRows, query.data?.items],
  );
  const visibleRows = printRows ?? query.data?.items ?? [];

  useEffect(() => {
    if (printRows === null) return;
    const clearPrintRows = () => setPrintRows(null);
    window.addEventListener('afterprint', clearPrintRows, { once: true });
    const timer = window.setTimeout(() => window.print(), 0);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('afterprint', clearPrintRows);
    };
  }, [printRows]);

  async function downloadCsv() {
    const response = await api.get<Blob>(`/reports/${kind}/export.csv`, {
      params: {
        start_date: startDate,
        end_date: endDate,
        farm_id: farmId || undefined,
        flock_id: flockId || undefined,
      },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `pouktry-${kind}-${startDate}-${endDate}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function printPdf() {
    const rows: ReportRow[] = [];
    let rowOffset = 0;
    while (true) {
      const response = await api.get<ReportResponse>(`/reports/${kind}`, {
        params: {
          start_date: startDate,
          end_date: endDate,
          farm_id: farmId || undefined,
          flock_id: flockId || undefined,
          limit: 500,
          offset: rowOffset,
        },
      });
      rows.push(...response.data.items);
      rowOffset += response.data.items.length;
      if (rowOffset >= response.data.total || response.data.items.length === 0) break;
    }
    setPrintRows(rows);
  }

  function changeKind(value: ReportKind) {
    setKind(value);
    setOffset(0);
  }

  return (
    <section className="reports-page" aria-labelledby="reports-title">
      <header className="reports-heading">
        <div>
          <p className="eyebrow">{t('reports.eyebrow')}</p>
          <h1 id="reports-title">{t('reports.title')}</h1>
        </div>
        <div className="report-actions">
          <button className="secondary-button" type="button" onClick={() => void downloadCsv()}>
            {t('reports.csv')}
          </button>
          <button className="secondary-button" type="button" onClick={() => void printPdf()}>
            {t('reports.pdf')}
          </button>
        </div>
      </header>

      <form className="report-filters" onSubmit={(event) => event.preventDefault()}>
        <label>
          {t('reports.reportType')}
          <select value={kind} onChange={(event) => changeKind(event.target.value as ReportKind)}>
            {reportKinds.map((reportKind) => (
              <option key={reportKind} value={reportKind}>
                {t(`reports.kinds.${reportKind}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('reports.startDate')}
          <input type="date" value={startDate} max={endDate} onChange={(event) => { setStartDate(event.target.value); setOffset(0); }} />
        </label>
        <label>
          {t('reports.endDate')}
          <input type="date" value={endDate} min={startDate} onChange={(event) => { setEndDate(event.target.value); setOffset(0); }} />
        </label>
        <label>
          {t('reports.farm')}
          <select value={farmId} onChange={(event) => { setFarmId(event.target.value); setFlockId(''); setOffset(0); }}>
            <option value="">{t('reports.allFarms')}</option>
            {farms.data?.items.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
          </select>
        </label>
        <label>
          {t('reports.flock')}
          <select value={flockId} onChange={(event) => { setFlockId(event.target.value); setOffset(0); }}>
            <option value="">{t('reports.allFlocks')}</option>
            {flocks.data?.items.map((flock) => <option key={flock.id} value={flock.id}>{flock.name}</option>)}
          </select>
        </label>
      </form>

      {query.isPending ? <p role="status">{t('reports.loading')}</p> : null}
      {query.isError ? (
        <div role="alert" className="daily-error">
          <p>{t('reports.error')}</p>
          <button className="primary-button" type="button" onClick={() => void query.refetch()}>{t('reports.retry')}</button>
        </div>
      ) : null}
      {query.data ? (
        <>
          <div className="report-totals" aria-label={t('reports.totals')}>
            <strong>{t('reports.rows', { count: query.data.total })}</strong>
            {Object.entries(query.data.totals).map(([key, value]) => (
              <span key={key}>{t(`reports.fields.${key}`, { defaultValue: key })}: {value ?? '—'}</span>
            ))}
          </div>
          {query.data.items.length === 0 ? (
            <p className="empty-state">{t('reports.empty')}</p>
          ) : (
            <div
              className="report-table-wrap"
              role="region"
              aria-label={t('reports.tableRegion')}
              tabIndex={0}
            >
              <table className="report-table">
                <thead><tr>{columns.map((column) => <th key={column} scope="col">{t(`reports.fields.${column}`, { defaultValue: column.replaceAll('_', ' ') })}</th>)}</tr></thead>
                <tbody>
                  {visibleRows.map((row, index) => (
                    <tr key={String(row.record_id ?? row.flock_id ?? index)}>
                      {columns.map((column) => <td key={column}>{row[column] == null ? '—' : String(row[column])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <nav className="report-pagination" aria-label={t('reports.pagination')}>
            <button className="secondary-button" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>{t('reports.previous')}</button>
            <span>{t('reports.pageStatus', { first: query.data.total ? offset + 1 : 0, last: Math.min(offset + limit, query.data.total), total: query.data.total })}</span>
            <button className="secondary-button" type="button" disabled={offset + limit >= query.data.total} onClick={() => setOffset(offset + limit)}>{t('reports.next')}</button>
          </nav>
        </>
      ) : null}
    </section>
  );
}
