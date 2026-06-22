import { useState } from 'react';
import { useFetch } from '../hooks/useFetch';
import { endpoints } from '../api/client';
import { Loading, Err } from '../components/StateViews';
import NeighbourhoodMap from '../components/NeighbourhoodMap';
import type { MapMetric } from '../components/NeighbourhoodMap';
import type { City, NeighbourhoodMapGeoJSON, NeighbourhoodMapProps } from '../types';
import { CURRENCY, CITY_NAME, SNAPSHOT_PERIOD } from '../types';

interface Props { city: City }

const METRICS: { key: MapMetric; label: string }[] = [
  { key: 'median_price',    label: 'Median Price' },
  { key: 'listings_per_km2', label: 'Listing Density' },
];

export default function Geography({ city }: Props) {
  const cur = CURRENCY[city];
  const [metric, setMetric] = useState<MapMetric>('median_price');

  const geo = useFetch<NeighbourhoodMapGeoJSON>(endpoints.neighbourhoodMap(city));

  const topRows: NeighbourhoodMapProps[] = geo.data
    ? [...geo.data.features.map(f => f.properties)]
        .filter(p => p[metric] != null)
        .sort((a, b) => (b[metric] as number) - (a[metric] as number))
        .slice(0, 10)
    : [];

  const fmtValue = (p: NeighbourhoodMapProps) =>
    metric === 'median_price'
      ? `${cur}${p.median_price}`
      : `${p.listings_per_km2}/km²`;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Geographic Distribution</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          Neighbourhood map · {CITY_NAME[city]} {SNAPSHOT_PERIOD}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        {/* Metric toggle */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-brand-dark">Neighbourhood Choropleth</h2>
          <div className="flex gap-1">
            {METRICS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setMetric(key)}
                className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                  metric === key
                    ? 'bg-brand-red text-white border-brand-red'
                    : 'bg-white text-brand-gray border-gray-300 hover:border-brand-red'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {geo.loading && <Loading />}
        {geo.error   && <Err message={geo.error} />}
        {geo.data && (
          <NeighbourhoodMap data={geo.data} metric={metric} city={city} />
        )}
        <p className="text-xs text-brand-gray mt-2">
          Hover over a neighbourhood for details · scroll to zoom disabled — use +/− controls
        </p>
      </div>

      {/* Top-10 table */}
      {topRows.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-brand-dark mb-4">
            Top 10 Neighbourhoods by {metric === 'median_price' ? 'Median Price' : 'Listing Density'}
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-brand-gray border-b border-gray-100">
                <th className="pb-2 font-medium">#</th>
                <th className="pb-2 font-medium">Neighbourhood</th>
                <th className="pb-2 font-medium text-right">
                  {metric === 'median_price' ? 'Median Price' : 'Listings / km²'}
                </th>
                <th className="pb-2 font-medium text-right">Listings</th>
                {metric === 'median_price' && (
                  <th className="pb-2 font-medium text-right">Density / km²</th>
                )}
              </tr>
            </thead>
            <tbody>
              {topRows.map((p, i) => (
                <tr
                  key={p.neighbourhood}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-2 text-brand-gray">{i + 1}</td>
                  <td className="py-2 font-medium text-brand-dark">{p.neighbourhood}</td>
                  <td className="py-2 text-right">{fmtValue(p)}</td>
                  <td className="py-2 text-right text-brand-gray">
                    {p.listing_count?.toLocaleString() ?? '—'}
                  </td>
                  {metric === 'median_price' && (
                    <td className="py-2 text-right text-brand-gray">
                      {p.listings_per_km2 ?? '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
