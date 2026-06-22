import type { City, AskResponse } from '../types';
import { NEIGHBOURHOOD_TOP_N } from '../types';

const BASE = '/api';

/** All analytics endpoints call FastAPI via the Vite dev-server proxy (/api → :8000). */
export const endpoints = {
  neighbourhoodMap:     (city: City) => `${BASE}/analytics/geographic/neighbourhood-map?city=${city}`,
  priceByRoomType:      (city: City) => `${BASE}/analytics/listings/price-by-room-type?city=${city}`,
  priceByNeighbourhood:          (city: City) => `${BASE}/analytics/listings/price-by-neighbourhood?city=${city}&top_n=${NEIGHBOURHOOD_TOP_N}`,
  priceCiNeighbourhoodRoomType:  (city: City, roomType = 'entire_home') =>
    `${BASE}/analytics/listings/price-ci-neighbourhood-room-type?city=${city}&room_type=${roomType}`,
  availabilityBands:    (city: City) => `${BASE}/analytics/listings/availability-bands?city=${city}`,
  priceByDistance:      (city: City) => `${BASE}/analytics/geographic/price-by-distance?city=${city}`,
  hostSegments:         (city: City) => `${BASE}/analytics/hosts/segments?city=${city}`,
  hostTenure:           (city: City) => `${BASE}/analytics/hosts/tenure?city=${city}`,
  temporalAvailability: (city: City) => `${BASE}/analytics/temporal/availability?city=${city}`,
  temporalReviews:      (city: City) => `${BASE}/analytics/temporal/reviews?city=${city}`,
  weekdayWeekend:       (city: City) => `${BASE}/analytics/temporal/weekday-vs-weekend?city=${city}`,
  minimumNights:        (city: City) => `${BASE}/analytics/temporal/minimum-nights?city=${city}`,
  hypothesisTests:      (city: City) => `${BASE}/analytics/stats/hypothesis-tests?city=${city}`,
  regressionSummary:    (city: City) => `${BASE}/analytics/stats/regression/summary?city=${city}`,
  reviewSummary:             (city: City) => `${BASE}/analytics/reviews/summary?city=${city}`,
  reviewPriceScoreBuckets:   (city: City) => `${BASE}/analytics/reviews/price-score-buckets?city=${city}`,
  reviewAnomalies:           (city: City, limit = 10) => `${BASE}/analytics/reviews/anomalies?city=${city}&limit=${limit}`,
  cityComparison:       ()           => `${BASE}/analytics/comparison/cities`,
  roomTypeComparison:   ()           => `${BASE}/analytics/comparison/room-types`,
  llmSummary:           (city: City, type: string, refresh = false) =>
    `${BASE}/analytics/llm/summary?city=${city}&type=${type}&refresh=${refresh}`,
  llmCrossCity:         (refresh = false) =>
    `${BASE}/analytics/llm/cross-city?refresh=${refresh}`,
};

export async function llmAsk(
  city: City,
  question: string,
  model: string,
): Promise<AskResponse> {
  const res = await fetch(`${BASE}/analytics/llm/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city, question, model }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
