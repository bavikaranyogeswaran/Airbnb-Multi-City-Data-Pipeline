import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import type { Layer, LeafletMouseEvent, PathOptions } from 'leaflet';
import type { Feature } from 'geojson';
import type { City, NeighbourhoodMapGeoJSON, NeighbourhoodMapProps } from '../types';
import { CURRENCY } from '../types';

export type MapMetric = 'median_price' | 'listings_per_km2';

interface Props {
  data: NeighbourhoodMapGeoJSON;
  metric: MapMetric;
  city: City;
}

const CITY_CENTER: Record<City, [number, number]> = {
  london:    [51.505, -0.118],
  amsterdam: [52.374,  4.896],
  berlin:    [52.520, 13.405],
  madrid:    [40.416, -3.703],
};
const CITY_ZOOM: Record<City, number> = {
  london: 10, amsterdam: 12, berlin: 11, madrid: 11,
};

const PRICE_COLORS   = ['#fff7ec', '#fee8c8', '#fdd49e', '#fc8d59', '#d7301f'];
const DENSITY_COLORS = ['#eff3ff', '#bdd7e7', '#6baed6', '#2171b5', '#084594'];
const NO_DATA_COLOR  = '#e5e7eb';

function quantileBreaks(values: number[], n = 5): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  const breaks: number[] = [];
  for (let i = 1; i < n; i++) {
    breaks.push(sorted[Math.floor((i / n) * sorted.length)]);
  }
  return breaks;
}

function bucketColor(value: number | null, breaks: number[], colors: string[]): string {
  if (value == null) return NO_DATA_COLOR;
  const bucket = breaks.filter(b => value > b).length;
  return colors[Math.min(bucket, colors.length - 1)];
}

/** Flies to the new city centre whenever the city prop changes. */
function FlyTo({ city }: { city: City }) {
  const map = useMap();
  useEffect(() => {
    map.setView(CITY_CENTER[city], CITY_ZOOM[city]);
  }, [city, map]);
  return null;
}

export default function NeighbourhoodMap({ data, metric, city }: Props) {
  const cur    = CURRENCY[city];
  const colors = metric === 'median_price' ? PRICE_COLORS : DENSITY_COLORS;

  const values = useMemo(
    () =>
      data.features
        .map(f => f.properties[metric as keyof NeighbourhoodMapProps] as number | null)
        .filter((v): v is number => v != null && !isNaN(v)),
    [data, metric],
  );

  const breaks = useMemo(() => quantileBreaks(values), [values]);

  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;

  function styleFeature(feature?: Feature): PathOptions {
    const props = feature?.properties as NeighbourhoodMapProps | undefined;
    const value = props?.[metric as keyof NeighbourhoodMapProps] as number | null ?? null;
    return {
      fillColor:   bucketColor(value, breaks, colors),
      fillOpacity: 0.75,
      color:       '#ffffff',
      weight:      1,
    };
  }

  function onEachFeature(feature: Feature, layer: Layer) {
    const p    = feature.properties as NeighbourhoodMapProps;
    const name    = p.neighbourhood    || 'Unknown';
    const price   = p.median_price    != null ? `${cur}${p.median_price}`        : 'n/a';
    const density = p.listings_per_km2 != null ? `${p.listings_per_km2}/km²`     : 'n/a';
    const count   = p.listing_count   != null ? p.listing_count.toLocaleString() : 'n/a';

    layer.bindTooltip(
      `<strong style="font-size:13px">${name}</strong><br/>` +
      `Median price: <b>${price}</b><br/>` +
      `Listings: ${count}<br/>` +
      `Density: ${density}`,
      { sticky: true },
    );

    layer.on({
      mouseover(e: LeafletMouseEvent) {
        (e.target as { setStyle(s: PathOptions): void }).setStyle({
          fillOpacity: 0.95, weight: 2, color: '#374151',
        });
        (e.target as { bringToFront(): void }).bringToFront();
      },
      mouseout(e: LeafletMouseEvent) {
        (e.target as { setStyle(s: PathOptions): void }).setStyle({
          fillOpacity: 0.75, weight: 1, color: '#ffffff',
        });
      },
    });
  }

  const fmtLabel = (v: number) =>
    metric === 'median_price' ? `${cur}${Math.round(v)}` : `${Math.round(v)}/km²`;

  const legendRows = breaks.length
    ? colors.map((color, i) => ({
        color,
        label: `${fmtLabel(i === 0 ? min : breaks[i - 1])} – ${fmtLabel(i < breaks.length ? breaks[i] : max)}`,
      }))
    : [];

  return (
    <div className="relative">
      <MapContainer
        center={CITY_CENTER[city]}
        zoom={CITY_ZOOM[city]}
        style={{ height: '520px', borderRadius: '0.5rem' }}
        scrollWheelZoom={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains="abcd"
          maxZoom={20}
        />
        <FlyTo city={city} />
        <GeoJSON
          key={`${city}-${metric}`}
          data={data as unknown as Parameters<typeof GeoJSON>[0]['data']}
          style={styleFeature}
          onEachFeature={onEachFeature}
        />
      </MapContainer>

      {/* Colour legend */}
      {legendRows.length > 0 && (
        <div
          className="absolute bottom-8 left-4 bg-white rounded-lg shadow-md p-3 text-xs"
          style={{ zIndex: 1000 }}
        >
          <p className="font-semibold text-brand-dark mb-1.5">
            {metric === 'median_price' ? 'Median Price' : 'Listings / km²'}
          </p>
          <div className="flex flex-col gap-1">
            {legendRows.map(({ color, label }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="w-4 h-3 rounded-sm inline-block" style={{ background: color }} />
                <span className="text-brand-gray">{label}</span>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="w-4 h-3 rounded-sm inline-block bg-gray-200" />
              <span className="text-brand-gray">No data</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
