import type { ReactNode } from 'react';
import type { City, Page } from '../types';
import { CITIES, CITY_LABEL, CITY_COLOR, SNAPSHOT_PERIOD } from '../types';

interface NavItem { id: Page; label: string; icon: string }

const NAV: NavItem[] = [
  { id: 'overview',   label: 'Market Overview',      icon: '📊' },
  { id: 'pricing',    label: 'Pricing Analysis',     icon: '💰' },
  { id: 'hosts',      label: 'Host & Supply',        icon: '🏠' },
  { id: 'temporal',   label: 'Temporal Trends',      icon: '📅' },
  { id: 'statistics', label: 'Statistical Findings', icon: '📈' },
  { id: 'comparison', label: 'Cross-City',           icon: '🌍' },
  { id: 'ai',         label: 'AI Insights',          icon: '🤖' },
];

interface Props {
  page: Page;
  city: City;
  onPageChange: (p: Page) => void;
  onCityChange: (c: City) => void;
  children: ReactNode;
}

export default function Layout({ page, city, onPageChange, onCityChange, children }: Props) {
  const accent = CITY_COLOR[city];

  return (
    <div className="flex h-screen bg-brand-light overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <span className="text-xl">🏠</span>
            <div>
              <p className="text-sm font-bold text-brand-dark leading-tight">Airbnb Intelligence</p>
              <p className="text-xs text-brand-gray">Expernetic Assessment</p>
            </div>
          </div>
        </div>

        {/* City toggle */}
        <div className="px-3 py-3 border-b border-gray-100">
          <p className="text-xs font-semibold text-brand-gray uppercase tracking-wider mb-1.5">City</p>
          <div className="flex gap-1">
            {CITIES.map((c) => (
              <button
                key={c}
                onClick={() => onCityChange(c)}
                className="flex-1 text-xs py-1.5 rounded font-medium transition-all"
                style={
                  city === c
                    ? { backgroundColor: CITY_COLOR[c], color: '#fff' }
                    : { backgroundColor: '#F3F4F6', color: '#767676' }
                }
              >
                {CITY_LABEL[c]}
              </button>
            ))}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 overflow-y-auto">
          {NAV.map((item) => {
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                className="w-full text-left px-3 py-2 rounded-lg mb-0.5 flex items-center gap-2 text-sm transition-colors"
                style={
                  active
                    ? { backgroundColor: `${accent}18`, color: accent, fontWeight: 600 }
                    : { color: '#484848' }
                }
              >
                <span className="text-base">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-100">
          <p className="text-xs text-brand-gray">Source: Inside Airbnb</p>
          <p className="text-xs text-brand-gray">{SNAPSHOT_PERIOD} snapshots</p>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-6xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
