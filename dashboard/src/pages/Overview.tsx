import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import KpiCard from '../components/KpiCard';
import { Loading, Err } from '../components/StateViews';
import type { City, CityComparison, PriceByRoomType, AvailabilityBand } from '../types';
import { CURRENCY, CITY_COLOR, CITY_NAME, PIE_COLORS, SNAPSHOT_PERIOD } from '../types';

interface Props { city: City }

export default function Overview({ city }: Props) {
  const cur = CURRENCY[city];
  const color = CITY_COLOR[city];

  const cmp  = useFetch<CityComparison[]>(endpoints.cityComparison());
  const rt   = useFetch<PriceByRoomType[]>(endpoints.priceByRoomType(city));
  const ab   = useFetch<AvailabilityBand[]>(endpoints.availabilityBands(city));

  const row = cmp.data?.find((d) => d.city === city);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Market Overview</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          {CITY_NAME[city]} · Inside Airbnb snapshot {SNAPSHOT_PERIOD}
        </p>
      </div>

      {/* KPI grid */}
      {cmp.loading && <Loading />}
      {cmp.error   && <Err message={cmp.error} />}
      {row && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <KpiCard label="Total Listings"    value={row.total_listings.toLocaleString()} accent={color} />
          <KpiCard label="Unique Hosts"      value={row.unique_hosts.toLocaleString()} />
          <KpiCard label="Median Price"      value={`${cur}${row.median_price.toFixed(0)}`} />
          <KpiCard label="Median Rating"     value={`${row.median_rating.toFixed(2)} / 5`} />
          <KpiCard label="Superhost Rate"    value={`${row.superhost_rate_pct.toFixed(1)}%`} />
          <KpiCard label="Entire Home %"     value={`${row.pct_entire_home.toFixed(1)}%`} />
          <KpiCard label="Commercial Hosts"  value={`${row.pct_commercial.toFixed(1)}%`} sub="≥ 21 listings" />
          <KpiCard label="Price Null Rate"   value={`${row.price_null_pct.toFixed(0)}%`} sub="missing prices" />
        </div>
      )}

      {/* Two pie charts */}
      <div className="grid grid-cols-2 gap-5">
        {/* Room type mix */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Room Type Mix</h2>
          {rt.loading && <Loading />}
          {rt.error   && <Err message={rt.error} />}
          {rt.data && (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={rt.data}
                  dataKey="listing_count"
                  nameKey="room_type"
                  cx="50%" cy="50%"
                  outerRadius={90}
                  label={({ name, percent }) =>
                    (percent as number) > 0.02
                      ? `${(name as string).replace(/_/g, ' ')} ${((percent as number) * 100).toFixed(0)}%`
                      : ''
                  }
                  labelLine={false}
                >
                  {rt.data.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [(v as number).toLocaleString(), 'Listings']} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Availability bands */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-3">Listing Activity Level</h2>
          {ab.loading && <Loading />}
          {ab.error   && <Err message={ab.error} />}
          {ab.data && (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={ab.data}
                  dataKey="listing_count"
                  nameKey="band"
                  cx="50%" cy="50%"
                  outerRadius={90}
                  label={({ name, percent }) =>
                    `${((percent as number) * 100).toFixed(0)}%`
                  }
                >
                  {ab.data.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, name) => [(v as number).toLocaleString(), name as string]}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
          {/* Legend */}
          {ab.data && (
            <div className="mt-2 space-y-0.5">
              {ab.data.map((d, i) => (
                <div key={d.band} className="flex items-center gap-2 text-xs text-brand-gray">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                  />
                  {d.band}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
