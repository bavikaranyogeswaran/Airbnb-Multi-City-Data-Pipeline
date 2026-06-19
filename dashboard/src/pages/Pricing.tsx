import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LabelList,
} from 'recharts';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import type { City, PriceByRoomType, PriceByNeighbourhood, PriceByDistance } from '../types';
import { CURRENCY, CITY_COLOR, CITY_NAME, SNAPSHOT_PERIOD } from '../types';

interface Props { city: City }

/** Format a month string "2025-09-01" or "2025-09" to "Sep '25" */
function fmt(v: number, cur: string) {
  return `${cur}${Math.round(v)}`;
}

export default function Pricing({ city }: Props) {
  const cur   = CURRENCY[city];
  const color = CITY_COLOR[city];

  const rt   = useFetch<PriceByRoomType[]>(endpoints.priceByRoomType(city));
  const nb   = useFetch<PriceByNeighbourhood[]>(endpoints.priceByNeighbourhood(city));
  const dist = useFetch<PriceByDistance[]>(endpoints.priceByDistance(city));

  // Sort ascending for the horizontal bar (longest bar at the bottom)
  const rtAsc  = rt.data  ? [...rt.data].sort((a, b) => a.median_price - b.median_price) : [];
  // Neighbourhood data comes pre-sorted desc from the API — reverse for asc display
  const nbAsc  = nb.data  ? [...nb.data].reverse() : [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Pricing Analysis</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          Median nightly prices ({CURRENCY[city]}) · {CITY_NAME[city]} {SNAPSHOT_PERIOD}
        </p>
      </div>

      {/* Price by room type */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Median Price by Room Type</h2>
        {rt.loading && <Loading />}
        {rt.error   && <Err message={rt.error} />}
        {rtAsc.length > 0 && (
          <ResponsiveContainer width="100%" height={rtAsc.length * 52 + 30}>
            <BarChart data={rtAsc} layout="vertical" margin={{ left: 20, right: 70, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmt(v, cur)} tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="room_type"
                width={160}
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => (v as string).replace(/_/g, ' ')}
              />
              <Tooltip formatter={(v) => [fmt(v as number, cur), 'Median price']} />
              <Bar dataKey="median_price" fill={color} radius={[0, 4, 4, 0]}>
                <LabelList
                  dataKey="median_price"
                  position="right"
                  formatter={(v: number) => fmt(v, cur)}
                  style={{ fontSize: 11, fontWeight: 600 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Price by neighbourhood — top 15 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Top 15 Neighbourhoods by Median Price</h2>
        {nb.loading && <Loading />}
        {nb.error   && <Err message={nb.error} />}
        {nbAsc.length > 0 && (
          <ResponsiveContainer width="100%" height={nbAsc.length * 32 + 30}>
            <BarChart data={nbAsc} layout="vertical" margin={{ left: 20, right: 70, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(v) => fmt(v, cur)} tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="neighbourhood_cleansed"
                width={180}
                tick={{ fontSize: 11 }}
              />
              <Tooltip formatter={(v) => [fmt(v as number, cur), 'Median price']} />
              <Bar dataKey="median_price" fill={color} radius={[0, 3, 3, 0]}>
                <LabelList
                  dataKey="median_price"
                  position="right"
                  formatter={(v: number) => fmt(v, cur)}
                  style={{ fontSize: 10 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Price by distance band */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-base font-semibold text-brand-dark mb-4">Median Price by Distance from City Centre</h2>
        {dist.loading && <Loading />}
        {dist.error   && <Err message={dist.error} />}
        {dist.data && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={dist.data} margin={{ top: 10, right: 30, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="dist_band" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(v) => fmt(v, cur)} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [fmt(v as number, cur), 'Median price']} />
              <Bar dataKey="median_price" fill={color} radius={[4, 4, 0, 0]}>
                <LabelList
                  dataKey="median_price"
                  position="top"
                  formatter={(v: number) => fmt(v, cur)}
                  style={{ fontSize: 11, fontWeight: 600 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
