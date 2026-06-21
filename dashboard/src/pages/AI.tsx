import { useState, useCallback } from 'react';
import { Loading, Err } from '../components/StateViews';
import { endpoints, llmAsk } from '../api/client';
import type { City, LlmSummaryResponse, AskResponse } from '../types';
import { CITY_COLOR, CITY_NAME } from '../types';

interface Props { city: City }

const SUMMARY_TYPES = [
  { id: 'city',       label: 'City Overview'    },
  { id: 'model',      label: 'Price Model'       },
  { id: 'clusters',   label: 'Listing Clusters'  },
  { id: 'hosts',      label: 'Host Profile'      },
  { id: 'cross_city', label: 'Cross-City'        },
];

const GROQ_MODELS = [
  { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B (default)' },
  { id: 'llama-3.1-8b-instant',    label: 'Llama 3.1 8B (fast)'     },
  { id: 'mixtral-8x7b-32768',      label: 'Mixtral 8x7B'            },
];

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function idle<T>(): FetchState<T> {
  return { data: null, loading: false, error: null };
}

export default function AI({ city }: Props) {
  const color = CITY_COLOR[city];

  // ── Section A: narrative summaries ───────────────────────────────────────
  const [summaryType, setSummaryType] = useState('city');
  const [summaryState, setSummaryState] = useState<FetchState<LlmSummaryResponse>>(idle());

  const generate = useCallback(async (refresh = false) => {
    setSummaryState({ data: null, loading: true, error: null });
    const url = summaryType === 'cross_city'
      ? endpoints.llmCrossCity(refresh)
      : endpoints.llmSummary(city, summaryType, refresh);
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json() as LlmSummaryResponse;
      setSummaryState({ data, loading: false, error: null });
    } catch (err: unknown) {
      setSummaryState({ data: null, loading: false, error: (err as Error).message });
    }
  }, [city, summaryType]);

  const handleTypeChange = (t: string) => {
    setSummaryType(t);
    setSummaryState(idle());
  };

  // ── Section B: Text-to-SQL Q&A ────────────────────────────────────────────
  const [question, setQuestion]       = useState('');
  const [model, setModel]             = useState(GROQ_MODELS[0].id);
  const [askState, setAskState]       = useState<FetchState<AskResponse>>(idle());
  const [askSqlOnError, setAskSqlOnError] = useState<string | null>(null);

  const handleAsk = useCallback(async () => {
    if (!question.trim()) return;
    setAskState({ data: null, loading: true, error: null });
    setAskSqlOnError(null);
    try {
      const data = await llmAsk(city, question.trim(), model);
      setAskState({ data, loading: false, error: null });
    } catch (err: unknown) {
      const e = err as { detail?: string | { error?: string; generated_sql?: string } };
      if (e.detail && typeof e.detail === 'object' && e.detail.error) {
        setAskState({ data: null, loading: false, error: e.detail.error });
        setAskSqlOnError(e.detail.generated_sql ?? null);
      } else {
        setAskState({ data: null, loading: false, error: String(e.detail ?? 'Request failed') });
      }
    }
  }, [city, question, model]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">AI Insights</h1>
        <p className="text-sm text-brand-gray mt-0.5">
          LLM-generated summaries and natural-language data queries · {CITY_NAME[city]}
        </p>
      </div>

      {/* ── Section A: Narrative Summaries ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="text-base font-semibold text-brand-dark mb-1">Narrative Summary</h2>
        <p className="text-xs text-brand-gray mb-4">
          AI-generated analysis of your selected findings. Results are cached — use Refresh to regenerate.
        </p>

        {/* Type selector */}
        <div className="flex flex-wrap gap-2 mb-4">
          {SUMMARY_TYPES.map((t) => (
            <button
              key={t.id}
              onClick={() => handleTypeChange(t.id)}
              className="px-3 py-1.5 rounded-full text-xs font-medium transition-colors border"
              style={
                summaryType === t.id
                  ? { backgroundColor: color, color: '#fff', borderColor: color }
                  : { backgroundColor: '#F9FAFB', color: '#484848', borderColor: '#E5E7EB' }
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        {summaryType === 'cross_city' && (
          <p className="text-xs text-brand-gray italic mb-3">
            Cross-City compares all four cities — city selector above is ignored.
          </p>
        )}

        {/* Generate / Refresh */}
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={() => generate(false)}
            disabled={summaryState.loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
            style={{ backgroundColor: color }}
          >
            {summaryState.loading ? 'Generating…' : summaryState.data ? 'Regenerate' : 'Generate'}
          </button>
          {summaryState.data && !summaryState.loading && (
            <button
              onClick={() => generate(true)}
              className="px-3 py-2 rounded-lg text-xs font-medium border border-gray-200 text-brand-gray hover:bg-gray-50"
            >
              ↻ Refresh
            </button>
          )}
          {summaryState.data && (
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={
                summaryState.data.cached
                  ? { backgroundColor: '#FEF3C7', color: '#92400E' }
                  : { backgroundColor: '#D1FAE5', color: '#065F46' }
              }
            >
              {summaryState.data.cached ? 'Cached' : 'Fresh'}
            </span>
          )}
        </div>

        {summaryState.loading && <Loading />}
        {summaryState.error   && <Err message={summaryState.error} />}
        {summaryState.data && !summaryState.loading && (
          <div className="border-l-4 pl-4 py-1" style={{ borderColor: color }}>
            <p className="text-xs text-brand-gray mb-1">{summaryState.data.model}</p>
            <p className="text-sm text-brand-dark leading-relaxed whitespace-pre-wrap">
              {summaryState.data.summary}
            </p>
          </div>
        )}
      </div>

      {/* ── Section B: Text-to-SQL Q&A ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-base font-semibold text-brand-dark mb-1">Ask a Question</h2>
        <p className="text-xs text-brand-gray mb-4">
          Type a question in plain English — the AI converts it to SQL, runs it, and explains the result.
        </p>

        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleAsk(); }}
          placeholder="e.g. Which neighbourhoods have the highest median price?"
          rows={2}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-brand-dark resize-none focus:outline-none focus:ring-2 mb-3"
          style={{ '--tw-ring-color': color } as React.CSSProperties}
        />

        <div className="flex items-center gap-3 mb-5">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-xs text-brand-dark focus:outline-none"
          >
            {GROQ_MODELS.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          <button
            onClick={handleAsk}
            disabled={askState.loading || !question.trim()}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity disabled:opacity-50"
            style={{ backgroundColor: color }}
          >
            {askState.loading ? 'Thinking…' : 'Ask'}
          </button>
          <span className="text-xs text-brand-gray">Ctrl+Enter to submit</span>
        </div>

        {askState.loading && <Loading />}

        {askState.error && (
          <div>
            <Err message={askState.error} />
            {askSqlOnError && (
              <div className="mt-2">
                <p className="text-xs text-brand-gray mb-1">Generated SQL (rejected)</p>
                <pre className="bg-gray-900 text-red-400 text-xs rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
                  {askSqlOnError}
                </pre>
              </div>
            )}
          </div>
        )}

        {askState.data && !askState.loading && (
          <div className="space-y-4">

            {/* SQL */}
            <div>
              <p className="text-xs font-semibold text-brand-gray uppercase tracking-wider mb-1.5">SQL</p>
              <pre className="bg-gray-900 text-green-400 text-xs rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
                {askState.data.sql}
              </pre>
            </div>

            {/* Results table */}
            <div>
              <p className="text-xs font-semibold text-brand-gray uppercase tracking-wider mb-1.5">
                Results · {askState.data.row_count} row{askState.data.row_count !== 1 ? 's' : ''}
              </p>
              {askState.data.rows.length === 0 ? (
                <p className="text-sm text-brand-gray italic">No rows returned.</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        {Object.keys(askState.data.rows[0]).map((col) => (
                          <th key={col} className="px-3 py-2 text-left font-semibold text-brand-gray whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {askState.data.rows.map((row, i) => (
                        <tr key={i} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                          {Object.values(row).map((val, j) => (
                            <td key={j} className="px-3 py-2 text-brand-dark whitespace-nowrap">
                              {val === null || val === undefined
                                ? <span className="text-brand-gray italic">null</span>
                                : typeof val === 'number'
                                  ? val.toLocaleString()
                                  : String(val)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Explanation */}
            <div>
              <p className="text-xs font-semibold text-brand-gray uppercase tracking-wider mb-1.5">Explanation</p>
              <div className="border-l-4 pl-4 py-1" style={{ borderColor: color }}>
                <p className="text-sm text-brand-dark leading-relaxed">{askState.data.explanation}</p>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
