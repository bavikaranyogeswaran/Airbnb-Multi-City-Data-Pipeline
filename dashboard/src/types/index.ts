export type City = 'london' | 'amsterdam' | 'madrid' | 'berlin';
export type Page = 'overview' | 'pricing' | 'hosts' | 'temporal' | 'statistics' | 'comparison' | 'ai';

/** All supported cities in display order — add a new city here to propagate everywhere. */
export const CITIES: City[] = ['london', 'amsterdam', 'madrid', 'berlin'];

export const CURRENCY:   Record<City, string> = { london: '£', amsterdam: '€', madrid: '€', berlin: '€' };
export const CITY_NAME:  Record<City, string> = { london: 'London', amsterdam: 'Amsterdam', madrid: 'Madrid', berlin: 'Berlin' };
export const CITY_LABEL: Record<City, string> = { london: '🇬🇧 London', amsterdam: '🇳🇱 Amsterdam', madrid: '🇪🇸 Madrid', berlin: '🇩🇪 Berlin' };
export const CITY_COLOR: Record<City, string> = { london: '#FF5A5F', amsterdam: '#00A699', madrid: '#FC642D', berlin: '#484848' };

export const PIE_COLORS = ['#FF5A5F', '#00A699', '#FC642D', '#484848', '#767676', '#00D1C1'];

/** Data snapshot period shown in subtitles and the sidebar footer. */
export const SNAPSHOT_PERIOD = 'Sep 2025';

/** Number of neighbourhoods shown in the pricing chart. */
export const NEIGHBOURHOOD_TOP_N = 15;

/** Earliest ISO year prefix for the monthly reviews chart. */
export const REVIEW_HISTORY_FROM = '2020';

/** Review dimension keywords that are score-scale (0–5). Used to exclude count/rate rows. */
export const SCORE_DIMENSIONS = [
  'rating', 'accuracy', 'cleanliness', 'checkin', 'communication', 'location', 'value',
] as const;

export interface PriceByRoomType {
  room_type: string;
  listing_count: number;
  median_price: number;
  mean_price: number;
}

export interface CityComparison {
  city: string;
  total_listings: number;
  unique_hosts: number;
  median_price: number;
  price_null_pct: number;
  median_avail_365: number;
  superhost_rate_pct: number;
  pct_entire_home: number;
  pct_commercial: number;
  median_rating: number;
}

export interface AvailabilityBand {
  band: string;
  listing_count: number;
  share_pct: number;
  median_price: number;
}

export interface PriceByNeighbourhood {
  neighbourhood_cleansed: string;
  listing_count: number;
  median_price: number;
  mean_price: number;
}

export interface PriceByDistance {
  dist_band: string;
  listing_count: number;
  median_price: number;
}

export interface HostSegment {
  host_segment: string;
  listing_count: number;
  unique_hosts: number;
  median_price: number;
  median_rating: number;
  superhost_rate: number;
}

export interface HostTenure {
  tenure_band: string;
  listing_count: number;
  median_price: number;
  median_rating: number;
  superhost_rate: number;
}

export interface MonthlyAvailability {
  month: string;
  availability_rate: number;
  occupancy_rate: number;
}

export interface MonthlyReview {
  month: string;
  review_count: number;
}

export interface WeekdayWeekend {
  label: string;
  occupancy_rate: number;
  availability_rate: number;
}

export interface MinimumNights {
  month: string;
  median_min_nights: number;
}

export interface HypothesisTest {
  test: string;
  hypothesis: string;
  method: string;
  n_total: number;
  p_value: number | null;
  effect_size: number;
  effect_label: string;
  significant: boolean | string;
  conclusion: string;
}

export interface RegressionSummary {
  metric: string;
  value: number | string;
}

export interface ReviewSummary {
  dimension: string;
  median: number;
}

export interface RoomTypeComparison {
  room_type: string;
  'Amsterdam (EUR)': number;
  'London (GBP)': number;
}

export interface LlmSummaryResponse {
  city: string | null;
  type: string;
  model: string;
  cached: boolean;
  summary: string;
}

export interface AskResponse {
  city: string;
  question: string;
  model: string;
  sql: string;
  row_count: number;
  rows: Record<string, unknown>[];
  explanation: string;
}
