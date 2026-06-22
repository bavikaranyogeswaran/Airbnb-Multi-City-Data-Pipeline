import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, LabelList,
} from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import KpiCard from '../components/KpiCard';
import type { City, HypothesisTest, RegressionSummary, ReviewSummary, ReviewPriceScoreBucket, ReviewAnomaly } from '../types';
import { CITY_COLOR, CITY_NAME, CURRENCY, SCORE_DIMENSIONS } from '../types';

interface Props { city: City }

/** Hypothesis tests store 'True'/'False' strings (from CSV) or real booleans */
function isSig(v: boolean | string): boolean {
  return v === true || v === 'True';
}

/** Normalise metric keys so R² and R2 both match */
function normMetric(s: string) { return s.replace('²', '2').toLowerCase(); }

/** Pull a single metric value from the regression summary rows */
function getReg(rows: RegressionSummary[], key: string): string {
  const row = rows.find((r) => r.metric === key || normMetric(r.metric) === normMetric(key));
  if (!row) return '—';
  const n = Number(row.value);
  return isNaN(n) ? String(row.value) : n.toFixed(4);
}

export default function Statistics({ city }: Props) {
  const color = CITY_COLOR[city];
  const cur   = CURRENCY[city];

  const hyp      = useFetch<HypothesisTest[]>(endpoints.hypothesisTests(city));
  const reg      = useFetch<RegressionSummary[]>(endpoints.regressionSummary(city));
  const rev      = useFetch<ReviewSummary[]>(endpoints.reviewSummary(city));
  const buckets  = useFetch<ReviewPriceScoreBucket[]>(endpoints.reviewPriceScoreBuckets(city));
  const anomalies= useFetch<ReviewAnomaly[]>(endpoints.reviewAnomalies(city, 10));

  // Keep only rating-scale dimensions (0–5); exclude count/rate rows
  const revChart = rev.data
    ?.filter((r) => {
      const d = r.dimension.toLowerCase();
      return SCORE_DIMENSIONS.some((k) => d.includes(k));
    })
    .map((r) => ({
      ...r,
      dim: r.dimension
        .replace('review_scores_', '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase()),
    })) ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Statistical Findings</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          Hypothesis tests, OLS regression, and review scores · {CITY_NAME[city]}
        </p>
      </div>

      {/* Regression KPIs */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">OLS Regression · Log(Price) ~ Room + Neighbourhood + Host + Availability</h2>
        {reg.loading && <Loading />}
        {reg.error   && <Err message={reg.error} />}
        {reg.data && (
          <div className="grid grid-cols-4 gap-4">
            <KpiCard label="R²"           value={getReg(reg.data, 'R²')} accent={color} />
            <KpiCard label="Adjusted R²"  value={getReg(reg.data, 'Adjusted R²') !== '—'
              ? getReg(reg.data, 'Adjusted R²')
              : getReg(reg.data, 'Adj-R²')} />
            <KpiCard label="F-statistic"  value={parseFloat(getReg(reg.data, 'F-statistic')).toFixed(1)} />
            <KpiCard
              label="Observations"
              value={(() => {
                const row = reg.data.find((r) => r.metric === 'N observations' || r.metric === 'N');
                return row ? Number(row.value).toLocaleString() : '—';
              })()}
            />
          </div>
        )}
      </div>

      {/* Hypothesis tests */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-1">Hypothesis Tests</h2>
        <p className="text-xs text-brand-gray mb-4">α = 0.05 · Click to expand details</p>
        {hyp.loading && <Loading />}
        {hyp.error   && <Err message={hyp.error} />}
        {hyp.data?.map((t, i) => (
          <details key={i} className="border border-gray-200 rounded-lg overflow-hidden mb-2">
            <summary className="px-4 py-3 cursor-pointer flex items-center justify-between bg-white hover:bg-gray-50 select-none">
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white"
                  style={{ backgroundColor: isSig(t.significant) ? '#10B981' : '#EF4444' }}
                >
                  {isSig(t.significant) ? '✓' : '✗'}
                </span>
                <span className="font-semibold text-sm text-brand-dark truncate">{t.test}</span>
              </div>
              <span
                className="shrink-0 text-xs font-medium px-2.5 py-0.5 rounded-full ml-3"
                style={
                  isSig(t.significant)
                    ? { backgroundColor: '#D1FAE5', color: '#065F46' }
                    : { backgroundColor: '#FEE2E2', color: '#991B1B' }
                }
              >
                {isSig(t.significant) ? 'Significant' : 'Not Significant'}
              </span>
            </summary>
            <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
              <p className="text-xs text-brand-gray italic mb-3">{t.hypothesis}</p>
              <div className="grid grid-cols-4 gap-4 mb-3">
                <div>
                  <p className="text-xs text-brand-gray">p-value</p>
                  <p className="font-mono text-sm font-semibold">
                    {t.p_value != null ? t.p_value.toExponential(2) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-brand-gray">{t.effect_label}</p>
                  <p className="font-mono text-sm font-semibold">{Math.abs(t.effect_size).toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-xs text-brand-gray">Method</p>
                  <p className="text-sm">{t.method}</p>
                </div>
                <div>
                  <p className="text-xs text-brand-gray">n</p>
                  <p className="font-mono text-sm">{t.n_total.toLocaleString()}</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-brand-gray mb-0.5">Conclusion</p>
                <p className="text-sm font-medium text-brand-dark">{t.conclusion}</p>
              </div>
            </div>
          </details>
        ))}
      </div>

      {/* Review score dimensions */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Review Score Medians by Dimension</h2>
        {rev.loading && <Loading />}
        {rev.error   && <Err message={rev.error} />}
        {revChart.length > 0 && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={revChart} margin={{ top: 5, right: 20, bottom: 35, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="dim"
                tick={{ fontSize: 10 }}
                angle={-30}
                textAnchor="end"
                interval={0}
              />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [(v as number).toFixed(2), 'Median score']} />
              <ReferenceLine y={4.5} stroke="#94A3B8" strokeDasharray="4 2" label={{ value: "4.5", position: "insideTopRight", fontSize: 10 }} />
              <Bar dataKey="median" fill={color} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* §4.5 Review & Demand-Side Analysis */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-1">Review Count · Price &amp; Rating Relationship</h2>
        <p className="text-xs text-brand-gray mb-4">
          How median price and guest rating vary by how many reviews a listing has accumulated.
          High-volume listings (21–100 reviews) tend to be more competitively priced;
          early listings (1–5 reviews) start with inflated 5-star averages.
        </p>
        {buckets.loading && <Loading />}
        {buckets.error   && <Err message={buckets.error} />}
        {buckets.data && (
          <div className="grid grid-cols-2 gap-5">
            {/* Median price by review bucket */}
            <div>
              <p className="text-xs font-medium text-brand-gray mb-2">Median Price by Review Count</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={buckets.data} margin={{ top: 5, right: 10, bottom: 40, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="review_count_bucket" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" interval={0} />
                  <YAxis tickFormatter={(v) => `${cur}${v}`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [`${cur}${v}`, 'Median price']} />
                  <Bar dataKey="median_price" fill={color} radius={[4, 4, 0, 0]}>
                    <LabelList
                      dataKey="median_price"
                      position="top"
                      formatter={(v: number) => `${cur}${v}`}
                      style={{ fontSize: 9 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Median rating by review bucket */}
            <div>
              <p className="text-xs font-medium text-brand-gray mb-2">Median Rating by Review Count</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={buckets.data.filter((b) => b.median_rating != null)}
                  margin={{ top: 5, right: 10, bottom: 40, left: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="review_count_bucket" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" interval={0} />
                  <YAxis domain={[4.5, 5.1]} tickFormatter={(v) => v.toFixed(2)} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [(v as number).toFixed(2), 'Median rating']} />
                  <ReferenceLine y={4.8} stroke="#94A3B8" strokeDasharray="4 2" />
                  <Bar dataKey="median_rating" fill="#00A699" radius={[4, 4, 0, 0]}>
                    <LabelList
                      dataKey="median_rating"
                      position="top"
                      formatter={(v: number) => v.toFixed(2)}
                      style={{ fontSize: 9 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* High-review / low-score anomaly listings */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-base font-semibold text-brand-dark mb-1">High-Review / Low-Score Listings</h2>
        <p className="text-xs text-brand-gray mb-4">
          Listings with ≥25 reviews but rating ≤4.54 — consistently underperforming despite high demand.
          These signal a structural gap: the property generates bookings but fails on guest experience.
        </p>
        {anomalies.loading && <Loading />}
        {anomalies.error   && <Err message={anomalies.error} />}
        {anomalies.data && anomalies.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-gray-200 text-brand-gray">
                  <th className="text-left py-2 pr-3 font-medium">Neighbourhood</th>
                  <th className="text-left py-2 pr-3 font-medium">Room Type</th>
                  <th className="text-right py-2 pr-3 font-medium">Price</th>
                  <th className="text-right py-2 pr-3 font-medium">Reviews</th>
                  <th className="text-right py-2 pr-3 font-medium">Rating</th>
                  <th className="text-right py-2 font-medium">Cleanliness</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.data.map((row, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-1.5 pr-3">{row.neighbourhood_cleansed}</td>
                    <td className="py-1.5 pr-3 text-brand-gray">{row.room_type.replace('_', ' ')}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      {row.price_numeric != null ? `${cur}${row.price_numeric}` : '—'}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono">{row.number_of_reviews}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      <span className="text-amber-600 font-semibold">{row.review_scores_rating?.toFixed(2)}</span>
                    </td>
                    <td className="py-1.5 text-right font-mono">{row.review_scores_cleanliness?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
