import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { api } from '../services/api';

type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type Farm = { id: string; name: string };
type Flock = { id: string; farm_id: string; name: string; status: string };
type Party = { id: string; name: string; phone: string | null };
type Sale = {
  id: string; flock_id: string; buyer_id: string; sale_on: string; birds: number;
  total_weight_kg: string; rate_per_kg_pkr: string; amount_pkr: string; version: number;
};
type Expense = {
  id: string; scope: 'direct' | 'farm'; flock_id: string | null; incurred_on: string;
  amount_pkr: string; description: string; supplier_id: string | null; version: number;
};
type Balance = { buyer_id: string; buyer_name: string; outstanding_pkr: string };

const decimal = (maxWhole: number, scale: number, allowZero = false) =>
  z.string().regex(
    new RegExp(`^(?:${allowZero ? '0|' : ''}[0-9]{1,${maxWhole}})(?:\\.[0-9]{1,${scale}})?$`),
  ).refine((value) => allowZero || /[1-9]/.test(value));
const partySchema = z.object({ name: z.string().trim().min(1).max(160), phone: z.string().max(40) });
const saleSchema = z.object({
  flock_id: z.string().min(1), buyer_id: z.string().min(1), sale_on: z.string().min(1),
  birds: z.coerce.number().int().positive(), total_weight_kg: decimal(9, 3),
  rate_per_kg_pkr: decimal(12, 2, true), amount_pkr: decimal(12, 2, true),
});
const paymentSchema = z.object({ sale_id: z.string().min(1), paid_on: z.string().min(1), amount_pkr: decimal(12, 2), reference: z.string().max(160) });
const expenseSchema = z.object({
  scope: z.enum(['direct', 'farm']), flock_id: z.string(), supplier_id: z.string(), incurred_on: z.string().min(1),
  amount_pkr: decimal(12, 2), description: z.string().trim().min(1).max(240),
  allocation_start: z.string(), allocation_end: z.string(), eligible_flock_ids: z.array(z.string()),
}).superRefine((value, ctx) => {
  if (value.scope === 'direct' && !value.flock_id) ctx.addIssue({ code: 'custom', path: ['flock_id'], message: 'required' });
  if (value.scope === 'farm' && (!value.allocation_start || !value.allocation_end || value.eligible_flock_ids.length === 0)) {
    ctx.addIssue({ code: 'custom', path: ['eligible_flock_ids'], message: 'required' });
  }
  if (value.scope === 'farm' && value.allocation_end < value.allocation_start) {
    ctx.addIssue({ code: 'custom', path: ['allocation_end'], message: 'range' });
  }
});

const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Karachi' });
const pageSize = 20;

export default function FinancePage() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [section, setSection] = useState<'sales' | 'expenses' | 'parties'>('sales');
  const [farmId, setFarmId] = useState('');
  const [salesOffset, setSalesOffset] = useState(0);
  const [expenseOffset, setExpenseOffset] = useState(0);
  const [partyOffset, setPartyOffset] = useState(0);
  const [balanceOffset, setBalanceOffset] = useState(0);

  const farms = useQuery({ queryKey: ['finance', 'farms'], queryFn: async () => (await api.get<Page<Farm>>('/farms?limit=100&offset=0')).data, staleTime: 300_000 });
  const flocks = useQuery({ queryKey: ['finance', 'flocks'], queryFn: async () => (await api.get<Page<Flock>>('/flocks?limit=100&offset=0')).data, staleTime: 120_000 });
  const buyers = useQuery({ queryKey: ['finance', 'buyers', partyOffset], queryFn: async () => (await api.get<Party[]>(`/buyers?limit=${pageSize}&offset=${partyOffset}`)).data, staleTime: 60_000 });
  const suppliers = useQuery({ queryKey: ['finance', 'suppliers', partyOffset], queryFn: async () => (await api.get<Party[]>(`/suppliers?limit=${pageSize}&offset=${partyOffset}`)).data, staleTime: 60_000 });
  const balances = useQuery({ queryKey: ['finance', 'balances', balanceOffset], queryFn: async () => (await api.get<Balance[]>(`/buyers/outstanding?limit=${pageSize}&offset=${balanceOffset}`)).data, staleTime: 30_000 });
  const sales = useQuery({ enabled: Boolean(farmId), queryKey: ['finance', 'sales', farmId, salesOffset], queryFn: async () => (await api.get<Sale[]>(`/farms/${farmId}/sales?limit=${pageSize}&offset=${salesOffset}`)).data, staleTime: 30_000 });
  const expenses = useQuery({ enabled: Boolean(farmId), queryKey: ['finance', 'expenses', farmId, expenseOffset], queryFn: async () => (await api.get<Expense[]>(`/farms/${farmId}/expenses?limit=${pageSize}&offset=${expenseOffset}`)).data, staleTime: 30_000 });

  const saleForm = useForm<z.input<typeof saleSchema>>({ resolver: zodResolver(saleSchema), defaultValues: { sale_on: today(), flock_id: '', buyer_id: '', birds: 1, total_weight_kg: '', rate_per_kg_pkr: '', amount_pkr: '' } });
  const paymentForm = useForm<z.input<typeof paymentSchema>>({ resolver: zodResolver(paymentSchema), defaultValues: { sale_id: '', paid_on: today(), amount_pkr: '', reference: '' } });
  const buyerForm = useForm<z.input<typeof partySchema>>({ resolver: zodResolver(partySchema), defaultValues: { name: '', phone: '' } });
  const supplierForm = useForm<z.input<typeof partySchema>>({ resolver: zodResolver(partySchema), defaultValues: { name: '', phone: '' } });
  const expenseForm = useForm<z.input<typeof expenseSchema>>({ resolver: zodResolver(expenseSchema), defaultValues: { scope: 'direct', flock_id: '', supplier_id: '', incurred_on: today(), amount_pkr: '', description: '', allocation_start: '', allocation_end: '', eligible_flock_ids: [] } });
  const expenseScope = useWatch({ control: expenseForm.control, name: 'scope' });

  const refreshFinance = () => {
    void client.invalidateQueries({ queryKey: ['finance'] });
    void client.invalidateQueries({ queryKey: ['dashboard'] });
  };
  const addSale = useMutation({ mutationFn: (v: z.output<typeof saleSchema>) => api.post(`/farms/${farmId}/sales`, { ...v, rate_per_kg_pkr: v.rate_per_kg_pkr, amount_pkr: v.amount_pkr }), onSuccess: () => { saleForm.reset({ sale_on: today(), flock_id: '', buyer_id: '', birds: 1, total_weight_kg: '', rate_per_kg_pkr: '', amount_pkr: '' }); refreshFinance(); } });
  const addPayment = useMutation({ mutationFn: (v: z.output<typeof paymentSchema>) => api.post(`/sales/${v.sale_id}/payments`, { paid_on: v.paid_on, amount_pkr: v.amount_pkr, reference: v.reference || null }), onSuccess: () => { paymentForm.reset({ sale_id: '', paid_on: today(), amount_pkr: '', reference: '' }); refreshFinance(); } });
  const addBuyer = useMutation({ mutationFn: (v: z.output<typeof partySchema>) => api.post('/buyers', { ...v, phone: v.phone || null }), onSuccess: () => { buyerForm.reset(); refreshFinance(); } });
  const addSupplier = useMutation({ mutationFn: (v: z.output<typeof partySchema>) => api.post('/suppliers', { ...v, phone: v.phone || null }), onSuccess: () => { supplierForm.reset(); refreshFinance(); } });
  const addExpense = useMutation({ mutationFn: (v: z.output<typeof expenseSchema>) => api.post(`/farms/${farmId}/expenses`, {
    scope: v.scope, flock_id: v.scope === 'direct' ? v.flock_id : null, supplier_id: v.supplier_id || null,
    incurred_on: v.incurred_on, amount_pkr: v.amount_pkr, description: v.description,
    allocation_start: v.scope === 'farm' ? v.allocation_start : null,
    allocation_end: v.scope === 'farm' ? v.allocation_end : null,
    eligible_flock_ids: v.scope === 'farm' ? v.eligible_flock_ids : [],
  }), onSuccess: () => { expenseForm.reset({ scope: 'direct', flock_id: '', supplier_id: '', incurred_on: today(), amount_pkr: '', description: '', allocation_start: '', allocation_end: '', eligible_flock_ids: [] }); refreshFinance(); } });

  const loading = farms.isLoading || flocks.isLoading || buyers.isLoading || suppliers.isLoading || balances.isLoading;
  const loadError = farms.isError || flocks.isError || buyers.isError || suppliers.isError || balances.isError;
  const eligibleFlocks = flocks.data?.items.filter((flock) => flock.farm_id === farmId) ?? [];
  const formErrors = (form: { formState: { errors: Record<string, unknown> } }) => Object.keys(form.formState.errors).length > 0;
  const pageControls = (offset: number, rows: unknown[] | undefined, change: (next: number) => void, label: string) => (
    <nav className="finance-pagination" aria-label={label}>
      <button type="button" className="secondary-button" disabled={offset === 0} onClick={() => change(Math.max(0, offset - pageSize))}>{t('finance.previous')}</button>
      <span>{t('finance.page', { page: offset / pageSize + 1 })}</span>
      <button type="button" className="secondary-button" disabled={!rows || rows.length < pageSize} onClick={() => change(offset + pageSize)}>{t('finance.next')}</button>
    </nav>
  );

  return (
    <section className="page-section finance-page" aria-labelledby="finance-title">
      <header className="page-heading"><div><p className="eyebrow">{t('finance.eyebrow')}</p><h1 id="finance-title">{t('finance.title')}</h1></div></header>
      {loading ? <p role="status" className="loading-state">{t('finance.loading')}</p> : loadError ? <div role="alert" className="daily-error"><p>{t('finance.loadError')}</p><button className="primary-button" type="button" onClick={() => { void farms.refetch(); void flocks.refetch(); void buyers.refetch(); void suppliers.refetch(); void balances.refetch(); }}>{t('finance.retry')}</button></div> : (
        <>
          <div className="finance-tabs" role="tablist" aria-label={t('finance.sections')}>
            {(['sales', 'expenses', 'parties'] as const).map((key) => <button key={key} type="button" role="tab" aria-selected={section === key} className={section === key ? 'finance-tab is-active' : 'finance-tab'} onClick={() => setSection(key)}>{t(`finance.tabs.${key}`)}</button>)}
          </div>
          <label className="finance-farm">{t('finance.farm')}<select value={farmId} onChange={(event) => { setFarmId(event.target.value); setSalesOffset(0); setExpenseOffset(0); }}><option value="">{t('finance.chooseFarm')}</option>{farms.data?.items.map((farm) => <option value={farm.id} key={farm.id}>{farm.name}</option>)}</select></label>

          {section === 'sales' && <>
            <section className="finance-card" aria-labelledby="sale-form-title"><h2 id="sale-form-title">{t('finance.recordSale')}</h2>
              {!farmId ? <p className="empty-state">{t('finance.chooseFarmFirst')}</p> : <form className="finance-form" onSubmit={saleForm.handleSubmit((v) => addSale.mutate(v as z.output<typeof saleSchema>))}>
                <label>{t('finance.flock')}<select {...saleForm.register('flock_id')}><option value="">{t('finance.chooseFlock')}</option>{eligibleFlocks.filter((f) => f.status === 'active').map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
                <label>{t('finance.buyer')}<select {...saleForm.register('buyer_id')}><option value="">{t('finance.chooseBuyer')}</option>{buyers.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
                {pageControls(partyOffset, buyers.data, setPartyOffset, t('finance.partyPages'))}
                <label>{t('finance.saleDate')}<input type="date" {...saleForm.register('sale_on')} /></label>
                <label>{t('finance.birdsSold')}<input inputMode="numeric" type="number" min="1" {...saleForm.register('birds')} /></label>
                <label>{t('finance.totalWeight')}<input inputMode="decimal" {...saleForm.register('total_weight_kg')} /></label>
                <label>{t('finance.ratePerKg')}<input inputMode="decimal" {...saleForm.register('rate_per_kg_pkr')} /></label>
                <label>{t('finance.saleAmount')}<input inputMode="decimal" {...saleForm.register('amount_pkr')} /></label>
                {formErrors(saleForm) && <p className="field-error" role="alert">{t('finance.validation')}</p>}
                {addSale.isError && <p className="field-error" role="alert">{t('finance.saveError')}</p>}
                {addSale.isSuccess && <p role="status">{t('finance.saleSaved')}</p>}
                <button className="primary-button" disabled={addSale.isPending}>{t('finance.saveSale')}</button>
              </form>}
            </section>
            <section className="finance-card" aria-labelledby="payment-title"><h2 id="payment-title">{t('finance.recordPayment')}</h2>
              {!farmId ? <p className="empty-state">{t('finance.chooseFarmFirst')}</p> : <form className="finance-form" onSubmit={paymentForm.handleSubmit((v) => addPayment.mutate(v as z.output<typeof paymentSchema>))}>
                <label>{t('finance.paymentSale')}<select {...paymentForm.register('sale_id')}><option value="">{t('finance.chooseSale')}</option>{sales.data?.map((sale) => <option key={sale.id} value={sale.id}>{sale.sale_on} · {sale.birds} · PKR {sale.amount_pkr}</option>)}</select></label>
                <label>{t('finance.paymentDate')}<input type="date" {...paymentForm.register('paid_on')} /></label>
                <label>{t('finance.paymentAmount')}<input inputMode="decimal" {...paymentForm.register('amount_pkr')} /></label>
                <label>{t('finance.paymentReference')}<input {...paymentForm.register('reference')} /></label>
                {formErrors(paymentForm) && <p className="field-error" role="alert">{t('finance.validation')}</p>}
                {addPayment.isError && <p className="field-error" role="alert">{t('finance.saveError')}</p>}
                {addPayment.isSuccess && <p role="status">{t('finance.paymentSaved')}</p>}
                <button className="primary-button" disabled={addPayment.isPending}>{t('finance.savePayment')}</button>
              </form>}
            </section>
            <section className="finance-card" aria-labelledby="outstanding-title"><h2 id="outstanding-title">{t('finance.outstanding')}</h2>
              {balances.isError ? <p role="alert">{t('finance.balanceError')}</p> : balances.isLoading ? <p role="status">{t('finance.loading')}</p> : balances.data?.length ? <div className="finance-table-wrap"><table><thead><tr><th>{t('finance.buyer')}</th><th>{t('finance.balance')}</th></tr></thead><tbody>{balances.data.map((row) => { const credit = row.outstanding_pkr.startsWith('-'); return <tr key={row.buyer_id}><td>{row.buyer_name}</td><td>{credit ? `${t('finance.credit')} · PKR ${row.outstanding_pkr.slice(1)}` : `PKR ${row.outstanding_pkr}`}</td></tr>; })}</tbody></table></div> : <p className="empty-state">{t('finance.noBalances')}</p>}
              {pageControls(balanceOffset, balances.data, setBalanceOffset, t('finance.balancePages'))}
            </section>
            <section className="finance-card" aria-labelledby="sales-list-title"><h2 id="sales-list-title">{t('finance.salesHistory')}</h2>
              {!farmId ? <p className="empty-state">{t('finance.chooseFarmFirst')}</p> : sales.isLoading ? <p role="status">{t('finance.loading')}</p> : sales.isError ? <p role="alert">{t('finance.salesError')}</p> : sales.data?.length ? <div className="finance-table-wrap"><table><thead><tr><th>{t('finance.saleDate')}</th><th>{t('finance.birdsSold')}</th><th>{t('finance.totalWeight')}</th><th>{t('finance.saleAmount')}</th></tr></thead><tbody>{sales.data.map((sale) => <tr key={sale.id}><td>{sale.sale_on}</td><td>{sale.birds}</td><td>{sale.total_weight_kg} kg</td><td>PKR {sale.amount_pkr}</td></tr>)}</tbody></table></div> : <p className="empty-state">{t('finance.noSales')}</p>}
              {farmId && pageControls(salesOffset, sales.data, setSalesOffset, t('finance.salesPages'))}
            </section>
          </>}

          {section === 'expenses' && <>
            <section className="finance-card" aria-labelledby="expense-form-title"><h2 id="expense-form-title">{t('finance.recordExpense')}</h2>
              {!farmId ? <p className="empty-state">{t('finance.chooseFarmFirst')}</p> : <form className="finance-form" onSubmit={expenseForm.handleSubmit((v) => addExpense.mutate(v as z.output<typeof expenseSchema>))}>
                <label>{t('finance.expenseType')}<select {...expenseForm.register('scope')}><option value="direct">{t('finance.directExpense')}</option><option value="farm">{t('finance.farmExpense')}</option></select></label>
                {expenseScope === 'direct' ? <label>{t('finance.flock')}<select {...expenseForm.register('flock_id')}><option value="">{t('finance.chooseFlock')}</option>{eligibleFlocks.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label> : <>
                  <label>{t('finance.allocationStart')}<input type="date" {...expenseForm.register('allocation_start')} /></label>
                  <label>{t('finance.allocationEnd')}<input type="date" {...expenseForm.register('allocation_end')} /></label>
                  <fieldset><legend>{t('finance.eligibleFlocks')}</legend>{eligibleFlocks.map((flock) => <label className="finance-check" key={flock.id}><input type="checkbox" value={flock.id} {...expenseForm.register('eligible_flock_ids')} />{flock.name}</label>)}</fieldset>
                </>}
                <label>{t('finance.supplier')}<select {...expenseForm.register('supplier_id')}><option value="">{t('finance.noSupplier')}</option>{suppliers.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
                {pageControls(partyOffset, suppliers.data, setPartyOffset, t('finance.partyPages'))}
                <label>{t('finance.expenseDate')}<input type="date" {...expenseForm.register('incurred_on')} /></label>
                <label>{t('finance.amount')}<input inputMode="decimal" {...expenseForm.register('amount_pkr')} /></label>
                <label>{t('finance.description')}<input maxLength={240} {...expenseForm.register('description')} /></label>
                {formErrors(expenseForm) && <p className="field-error" role="alert">{t('finance.validation')}</p>}
                {addExpense.isError && <p className="field-error" role="alert">{t('finance.saveError')}</p>}
                {addExpense.isSuccess && <p role="status">{t('finance.expenseSaved')}</p>}
                <button className="primary-button" disabled={addExpense.isPending}>{t('finance.saveExpense')}</button>
              </form>}
            </section>
            <section className="finance-card" aria-labelledby="expenses-list-title"><h2 id="expenses-list-title">{t('finance.expenseHistory')}</h2>
              {!farmId ? <p className="empty-state">{t('finance.chooseFarmFirst')}</p> : expenses.isLoading ? <p role="status">{t('finance.loading')}</p> : expenses.isError ? <p role="alert">{t('finance.expensesError')}</p> : expenses.data?.length ? <div className="finance-table-wrap"><table><thead><tr><th>{t('finance.expenseDate')}</th><th>{t('finance.expenseType')}</th><th>{t('finance.description')}</th><th>{t('finance.amount')}</th></tr></thead><tbody>{expenses.data.map((expense) => <tr key={expense.id}><td>{expense.incurred_on}</td><td>{t(expense.scope === 'direct' ? 'finance.directExpense' : 'finance.farmExpense')}</td><td>{expense.description}</td><td>PKR {expense.amount_pkr}</td></tr>)}</tbody></table></div> : <p className="empty-state">{t('finance.noExpenses')}</p>}
              {farmId && pageControls(expenseOffset, expenses.data, setExpenseOffset, t('finance.expensePages'))}
            </section>
          </>}

          {section === 'parties' && <div className="finance-party-grid">
            <section className="finance-card" aria-labelledby="buyers-title"><h2 id="buyers-title">{t('finance.buyers')}</h2><form className="finance-form" onSubmit={buyerForm.handleSubmit((v) => addBuyer.mutate(v))}><label>{t('finance.partyName')}<input {...buyerForm.register('name')} /></label><label>{t('finance.phone')}<input inputMode="tel" {...buyerForm.register('phone')} /></label>{formErrors(buyerForm) && <p className="field-error" role="alert">{t('finance.validation')}</p>}{addBuyer.isError && <p role="alert">{t('finance.saveError')}</p>}<button className="primary-button" disabled={addBuyer.isPending}>{t('finance.addBuyer')}</button></form>{buyers.data?.length ? <ul className="finance-party-list">{buyers.data.map((item) => <li key={item.id}>{item.name}{item.phone && <small>{item.phone}</small>}</li>)}</ul> : <p className="empty-state">{t('finance.noBuyers')}</p>}{pageControls(partyOffset, buyers.data, setPartyOffset, t('finance.partyPages'))}</section>
            <section className="finance-card" aria-labelledby="suppliers-title"><h2 id="suppliers-title">{t('finance.suppliers')}</h2><form className="finance-form" onSubmit={supplierForm.handleSubmit((v) => addSupplier.mutate(v))}><label>{t('finance.partyName')}<input {...supplierForm.register('name')} /></label><label>{t('finance.phone')}<input inputMode="tel" {...supplierForm.register('phone')} /></label>{formErrors(supplierForm) && <p className="field-error" role="alert">{t('finance.validation')}</p>}{addSupplier.isError && <p role="alert">{t('finance.saveError')}</p>}<button className="primary-button" disabled={addSupplier.isPending}>{t('finance.addSupplier')}</button></form>{suppliers.data?.length ? <ul className="finance-party-list">{suppliers.data.map((item) => <li key={item.id}>{item.name}{item.phone && <small>{item.phone}</small>}</li>)}</ul> : <p className="empty-state">{t('finance.noSuppliers')}</p>}{pageControls(partyOffset, suppliers.data, setPartyOffset, t('finance.partyPages'))}</section>
          </div>}
        </>
      )}
    </section>
  );
}
