import { useState } from 'react';
import Layout from './components/Layout';
import Overview   from './pages/Overview';
import Pricing    from './pages/Pricing';
import Hosts      from './pages/Hosts';
import Temporal   from './pages/Temporal';
import Statistics from './pages/Statistics';
import Comparison from './pages/Comparison';
import AI         from './pages/AI';
import type { City, Page } from './types';

export default function App() {
  const [page, setPage] = useState<Page>('overview');
  const [city, setCity] = useState<City>('london');

  return (
    <Layout page={page} city={city} onPageChange={setPage} onCityChange={setCity}>
      {page === 'overview'   && <Overview   city={city} />}
      {page === 'pricing'    && <Pricing    city={city} />}
      {page === 'hosts'      && <Hosts      city={city} />}
      {page === 'temporal'   && <Temporal   city={city} />}
      {page === 'statistics' && <Statistics city={city} />}
      {page === 'comparison' && <Comparison />}
      {page === 'ai'         && <AI         city={city} />}
    </Layout>
  );
}
