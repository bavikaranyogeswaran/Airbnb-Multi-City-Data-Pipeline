import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import type { City, MonthlyReview, MonthlyAvailability, WeekdayWeekend, MinimumNights } from '../types';
import { CITY_COLOR, CITY_NAME, REVIEW_HISTORY_FROM } from '../types';

interface Props { city: City }

/** Parse "2025-09-01" or "2025-09" to a short label "Sep '25" */
function shortMonth(m: string): string {
  const parts = m.split('-');
  const d = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

function pct(v: number) { return `${(v * 100).toFixed(0)}%`; }

export default function Temporal({ city }: Props) {
  const color = CITY_COLOR[city];

  const reviews  = useFetch<MonthlyReview[]>(endpoints.temporalReviews(city));
  const avail    = useFetch<MonthlyAvailability[]>(endpoints.temporalAvailability(city));
  const ww       = useFetch<WeekdayWeekend[]>(endpoints.weekdayWeekend(city));
  const minN     = useFetch<MinimumNights[]>(endpoints.minimumNights(city));

  // Keep only post-2020 review data to keep the chart readable
  const recentReviews = reviews.data
    ?.filter((r) => r.month >= REVIEW_HISTORY_FROM)
    .map((r) => ({ ...r, label: shortMonth(r.month) })) ?? [];

  const availFmt = avail.data?.map((r) => ({ ...r, label: shortMonth(r.month) })) ?? [];
  const minNFmt  = minN.data?.map((r) => ({ ...r, label: shortMonth(r.month) })) ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Temporal Trends</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          Monthly review activity, availability, and seasonality · {CITY_NAME[city]}
        </p>
      </div>

      {/* Monthly review volume */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Monthly Review Volume (2020–)</h2>
        {reviews.loading && <Loading />}
        {reviews.error   && <Err message={reviews.error} />}
        {recentReviews.length > 0 && (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={recentReviews} margin={{ top: 5, right: 20, bottom: 35, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                angle={-35}
                textAnchor="end"
                interval={3}
              />
              <YAxis tickFormatter={(v) => (v as number).toLocaleString()} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [(v as number).toLocaleString(), 'Reviews']} />
              <Line
                type="monotone"
                dataKey="review_count"
                stroke={color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Availability / occupancy rate */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Monthly Occupancy vs. Availability Rate</h2>
        {avail.loading && <Loading />}
        {avail.error   && <Err message={avail.error} />}
        {availFmt.length > 0 && (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={availFmt} margin={{ top: 5, right: 20, bottom: 35, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10 }}
                angle={-35}
                textAnchor="end"
                interval={2}
              />
              <YAxis tickFormatter={pct} tick={{ fontSize: 11 }} domain={[0, 1]} />
              <Tooltip formatter={(v) => [pct(v as number)]} />
              <Legend />
              <Bar dataKey="occupancy_rate"    name="Occupied"    stackId="a" fill={color} />
              <Bar dataKey="availability_rate" name="Available"   stackId="a" fill="#CBD5E1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Weekday vs Weekend + Minimum nights */}
      <div className="grid grid-cols-2 gap-5">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-4">Weekday vs. Weekend Occupancy</h2>
          {ww.loading && <Loading />}
          {ww.error   && <Err message={ww.error} />}
          {ww.data && (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={ww.data} margin={{ top: 10, right: 30, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={pct} domain={[0, 1]} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [pct(v as number)]} />
                <Bar dataKey="occupancy_rate" name="Occupancy" fill={color} radius={[4, 4, 0, 0]} />
                <Bar dataKey="availability_rate" name="Availability" fill="#CBD5E1" radius={[4, 4, 0, 0]} />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-4">Median Minimum Nights</h2>
          {minN.loading && <Loading />}
          {minN.error   && <Err message={minN.error} />}
          {minNFmt.length > 0 && (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={minNFmt} margin={{ top: 5, right: 20, bottom: 35, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10 }}
                  angle={-35}
                  textAnchor="end"
                  interval={2}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${v} nights`, 'Median min nights']} />
                <Line
                  type="monotone"
                  dataKey="median_min_nights"
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
