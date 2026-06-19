import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import type { CityComparison, RoomTypeComparison, HypothesisTest, RegressionSummary } from '../types';
import { CITY_COLOR, CITY_LABEL, CITY_NAME, CURRENCY, SNAPSHOT_PERIOD } from '../types';

function isSig(v: boolean | string): boolean {
  return v === true || v === 'True';
}

function getReg(rows: RegressionSummary[], key: string): string {
  const row = rows.find((r) =>
    r.metric === key ||
    r.metric.toLowerCase() === key.toLowerCase() ||
    r.metric === 'Adj-R²' && key === 'Adjusted R²'
  );
  if (!row) return '—';
  const n = Number(row.value);
  return isNaN(n) ? String(row.value) : n.toFixed(4);
}

export default function Comparison() {
  const cmp   = useFetch<CityComparison[]>(endpoints.cityComparison());
  const rt    = useFetch<RoomTypeComparison[]>(endpoints.roomTypeComparison());
  const hypLon = useFetch<HypothesisTest[]>(endpoints.hypothesisTests('london'));
  const hypAms = useFetch<HypothesisTest[]>(endpoints.hypothesisTests('amsterdam'));
  const regLon = useFetch<RegressionSummary[]>(endpoints.regressionSummary('london'));
  const regAms = useFetch<RegressionSummary[]>(endpoints.regressionSummary('amsterdam'));

  const london    = cmp.data?.find((d) => d.city === 'london');
  const amsterdam = cmp.data?.find((d) => d.city === 'amsterdam');

  const lonKey = CITY_NAME.london;
  const amsKey = CITY_NAME.amsterdam;

  // Metrics table rows
  const metricRows = london && amsterdam ? [
    { label: 'Total Listings',     lon: london.total_listings.toLocaleString(),                                 ams: amsterdam.total_listings.toLocaleString() },
    { label: 'Unique Hosts',       lon: london.unique_hosts.toLocaleString(),                                   ams: amsterdam.unique_hosts.toLocaleString() },
    { label: 'Median Price',       lon: `${CURRENCY.london}${london.median_price.toFixed(0)}`,                  ams: `${CURRENCY.amsterdam}${amsterdam.median_price.toFixed(0)}` },
    { label: 'Superhost Rate',     lon: `${london.superhost_rate_pct.toFixed(1)}%`,                             ams: `${amsterdam.superhost_rate_pct.toFixed(1)}%` },
    { label: '% Entire Home',      lon: `${london.pct_entire_home.toFixed(1)}%`,                                ams: `${amsterdam.pct_entire_home.toFixed(1)}%` },
    { label: '% Commercial Hosts', lon: `${london.pct_commercial.toFixed(1)}%`,                                 ams: `${amsterdam.pct_commercial.toFixed(1)}%` },
    { label: 'Median Rating',      lon: london.median_rating.toFixed(2),                                        ams: amsterdam.median_rating.toFixed(2) },
  ] : [];

  // R² comparison — use CITY_NAME as the dynamic dataKey so Recharts Legend is consistent
  const r2Data = (regLon.data && regAms.data) ? [
    {
      metric: 'R²',
      [lonKey]: parseFloat(getReg(regLon.data, 'R²')),
      [amsKey]: parseFloat(getReg(regAms.data, 'R²')),
    },
    {
      metric: 'Adj R²',
      [lonKey]: parseFloat(getReg(regLon.data, 'Adjusted R²') !== '—' ? getReg(regLon.data, 'Adjusted R²') : getReg(regLon.data, 'Adj-R²')),
      [amsKey]: parseFloat(getReg(regAms.data, 'Adjusted R²') !== '—' ? getReg(regAms.data, 'Adjusted R²') : getReg(regAms.data, 'Adj-R²')),
    },
  ] : [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Cross-City Comparison</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          {CITY_NAME.london} vs. {CITY_NAME.amsterdam} ({SNAPSHOT_PERIOD})
        </p>
      </div>

      {/* Metrics table */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Key Metrics Side-by-Side</h2>
        {cmp.loading && <Loading />}
        {cmp.error   && <Err message={cmp.error} />}
        {metricRows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 text-brand-gray font-medium text-xs uppercase tracking-wide">Metric</th>
                  <th className="text-right py-2 px-4 text-xs uppercase tracking-wide font-semibold" style={{ color: CITY_COLOR.london }}>
                    {CITY_LABEL.london}
                  </th>
                  <th className="text-right py-2 pl-4 text-xs uppercase tracking-wide font-semibold" style={{ color: CITY_COLOR.amsterdam }}>
                    {CITY_LABEL.amsterdam}
                  </th>
                </tr>
              </thead>
              <tbody>
                {metricRows.map((r, i) => (
                  <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                    <td className="py-2.5 pr-4 font-medium text-brand-dark">{r.label}</td>
                    <td className="py-2.5 px-4 text-right font-mono">{r.lon}</td>
                    <td className="py-2.5 pl-4 text-right font-mono">{r.ams}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Room type comparison grouped bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Room Type Share (% of listings)</h2>
        {rt.loading && <Loading />}
        {rt.error   && <Err message={rt.error} />}
        {rt.data && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={rt.data} margin={{ top: 10, right: 20, bottom: 20, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="room_type"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => (v as string).replace(/_/g, ' ')}
              />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${(v as number).toFixed(1)}%`]} />
              <Legend />
              <Bar dataKey="London (GBP)"    name={CITY_NAME.london}    fill={CITY_COLOR.london}    radius={[3, 3, 0, 0]} />
              <Bar dataKey="Amsterdam (EUR)" name={CITY_NAME.amsterdam} fill={CITY_COLOR.amsterdam} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Hypothesis test outcomes side by side */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Hypothesis Test Outcomes</h2>
        {(hypLon.loading || hypAms.loading) && <Loading />}
        {(hypLon.error || hypAms.error) && <Err message={hypLon.error ?? hypAms.error ?? ''} />}
        {hypLon.data && hypAms.data && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-3 font-medium text-brand-gray uppercase tracking-wide">Test</th>
                  <th className="text-center py-2 px-2 font-semibold" style={{ color: CITY_COLOR.london }}>{CITY_NAME.london}</th>
                  <th className="text-center py-2 px-2 font-semibold" style={{ color: CITY_COLOR.amsterdam }}>{CITY_NAME.amsterdam}</th>
                  <th className="text-left py-2 pl-3 font-medium text-brand-gray uppercase tracking-wide">Hypothesis ({CITY_NAME.london})</th>
                </tr>
              </thead>
              <tbody>
                {hypLon.data.map((t, i) => {
                  const ams = hypAms.data![i];
                  return (
                    <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                      <td className="py-2 pr-3 font-semibold text-brand-dark">{t.test}</td>
                      <td className="py-2 px-2 text-center">
                        <span
                          className="inline-block w-5 h-5 rounded-full text-xs font-bold text-white flex items-center justify-center mx-auto"
                          style={{ backgroundColor: isSig(t.significant) ? '#10B981' : '#EF4444' }}
                        >
                          {isSig(t.significant) ? '✓' : '✗'}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-center">
                        {ams ? (
                          <span
                            className="inline-block w-5 h-5 rounded-full text-xs font-bold text-white flex items-center justify-center mx-auto"
                            style={{ backgroundColor: isSig(ams.significant) ? '#10B981' : '#EF4444' }}
                          >
                            {isSig(ams.significant) ? '✓' : '✗'}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="py-2 pl-3 text-brand-gray leading-tight">{t.hypothesis}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* R² comparison */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">OLS Regression Model Fit (R²)</h2>
        {(regLon.loading || regAms.loading) && <Loading />}
        {r2Data.length > 0 && (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={r2Data} margin={{ top: 10, right: 20, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="metric" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v as number).toFixed(1)}`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [(v as number).toFixed(4)]} />
                <Legend />
                <Bar dataKey={lonKey} fill={CITY_COLOR.london}    radius={[4, 4, 0, 0]} />
                <Bar dataKey={amsKey} fill={CITY_COLOR.amsterdam} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            {(() => {
              const lonR2 = regLon.data ? parseFloat(getReg(regLon.data, 'R²')) : NaN;
              const amsR2 = regAms.data ? parseFloat(getReg(regAms.data, 'R²')) : NaN;
              if (isNaN(lonR2) || isNaN(amsR2)) return null;
              const stronger = lonR2 >= amsR2 ? CITY_NAME.london : CITY_NAME.amsterdam;
              const lonPct = (lonR2 * 100).toFixed(0);
              const amsPct = (amsR2 * 100).toFixed(0);
              return (
                <p className="mt-3 text-xs text-brand-gray leading-relaxed">
                  <span className="font-semibold" style={{ color: CITY_COLOR.london }}>{CITY_NAME.london}</span> listing
                  attributes (room type, neighbourhood, host tier, availability) explain{' '}
                  <strong>{lonPct}%</strong> of log-price variance.{' '}
                  <span className="font-semibold" style={{ color: CITY_COLOR.amsterdam }}>{CITY_NAME.amsterdam}</span>{' '}
                  explains <strong>{amsPct}%</strong>.{' '}
                  {stronger} pricing is more predictable from observable listing features alone.
                </p>
              );
            })()}
          </>
        )}
      </div>
    </div>
  );
}
