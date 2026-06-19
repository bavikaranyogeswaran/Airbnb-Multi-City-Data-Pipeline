import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LabelList, PieChart, Pie, Cell,
} from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import type { City, HostSegment, HostTenure } from '../types';
import { CURRENCY, CITY_COLOR, CITY_NAME, PIE_COLORS } from '../types';

interface Props { city: City }

export default function Hosts({ city }: Props) {
  const cur   = CURRENCY[city];
  const color = CITY_COLOR[city];

  const seg    = useFetch<HostSegment[]>(endpoints.hostSegments(city));
  const tenure = useFetch<HostTenure[]>(endpoints.hostTenure(city));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Host & Supply</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          Host segments, tenure, and supply concentration · {CITY_NAME[city]}
        </p>
      </div>

      {/* Segments row */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        {/* Pie: listing count by segment */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Listings by Host Segment</h2>
          {seg.loading && <Loading />}
          {seg.error   && <Err message={seg.error} />}
          {seg.data && (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={seg.data}
                    dataKey="listing_count"
                    nameKey="host_segment"
                    cx="50%" cy="50%"
                    outerRadius={85}
                    label={({ name, percent }) =>
                      `${String(name)} ${((percent as number) * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {seg.data.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [(v as number).toLocaleString(), 'Listings']} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-0.5">
                {seg.data.map((d, i) => (
                  <div key={d.host_segment} className="flex items-center gap-2 text-xs text-brand-gray">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                      style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                    />
                    {d.host_segment} — {d.listing_count.toLocaleString()} listings
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Bar: median price + superhost rate by segment */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Median Price by Segment</h2>
          {seg.loading && <Loading />}
          {seg.error   && <Err message={seg.error} />}
          {seg.data && (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={seg.data} margin={{ top: 10, right: 30, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="host_segment" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${cur}${v}`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [`${cur}${v}`, 'Median price']} />
                  <Bar dataKey="median_price" fill={color} radius={[4, 4, 0, 0]}>
                    <LabelList
                      dataKey="median_price"
                      position="top"
                      formatter={(v: number) => `${cur}${v}`}
                      style={{ fontSize: 11 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              <h3 className="text-sm font-semibold text-brand-dark mt-4 mb-2">Superhost Rate (%)</h3>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={seg.data} margin={{ top: 5, right: 30, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="host_segment" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [`${(v as number).toFixed(1)}%`, 'Superhost rate']} />
                  <Bar
                    dataKey="superhost_rate"
                    fill="#FC642D"
                    radius={[4, 4, 0, 0]}
                    name="Superhost rate"
                  >
                    <LabelList
                      dataKey="superhost_rate"
                      position="top"
                      formatter={(v: number) => `${v.toFixed(0)}%`}
                      style={{ fontSize: 10 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      </div>

      {/* Tenure row */}
      <div className="grid grid-cols-2 gap-5">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Listings by Host Tenure</h2>
          {tenure.loading && <Loading />}
          {tenure.error   && <Err message={tenure.error} />}
          {tenure.data && (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={tenure.data} margin={{ top: 10, right: 20, bottom: 40, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="tenure_band"
                  tick={{ fontSize: 10 }}
                  angle={-25}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [(v as number).toLocaleString(), 'Listings']} />
                <Bar dataKey="listing_count" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Median Price by Host Tenure</h2>
          {tenure.loading && <Loading />}
          {tenure.error   && <Err message={tenure.error} />}
          {tenure.data && (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={tenure.data} margin={{ top: 10, right: 20, bottom: 40, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="tenure_band"
                  tick={{ fontSize: 10 }}
                  angle={-25}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tickFormatter={(v) => `${cur}${v}`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${cur}${v}`, 'Median price']} />
                <Bar dataKey="median_price" fill="#FC642D" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
