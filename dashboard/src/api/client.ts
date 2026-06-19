import type { City } from '../types';
import { NEIGHBOURHOOD_TOP_N } from '../types';

const BASE = '/api';

/** All analytics endpoints call FastAPI via the Vite dev-server proxy (/api → :8000). */
export const endpoints = {
  priceByRoomType:      (city: City) => `${BASE}/analytics/listings/price-by-room-type?city=${city}`,
  priceByNeighbourhood: (city: City) => `${BASE}/analytics/listings/price-by-neighbourhood?city=${city}&top_n=${NEIGHBOURHOOD_TOP_N}`,
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
  reviewSummary:        (city: City) => `${BASE}/analytics/reviews/summary?city=${city}`,
  cityComparison:       ()           => `${BASE}/analytics/comparison/cities`,
  roomTypeComparison:   ()           => `${BASE}/analytics/comparison/room-types`,
};
