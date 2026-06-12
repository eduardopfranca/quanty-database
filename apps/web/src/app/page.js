'use client';

import { Fragment, useEffect, useState } from 'react';

const KIND_LABELS = {
  macro: 'macro',
  raw_bulk: 'raw bulk',
  raw_fundamental: 'raw fundamental',
  derived: 'derived',
};

function FreshBadge({ fresh }) {
  if (fresh === true) {
    return (
      <span className="inline-block rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
        Fresh
      </span>
    );
  }
  if (fresh === false) {
    return (
      <span className="inline-block rounded px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800">
        Stale
      </span>
    );
  }
  return <span className="text-gray-400">—</span>;
}

function formatDate(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

function formatUpdatedAt(iso) {
  if (!iso) return '—';
  return new Date(iso).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
}

function formatRows(n) {
  if (n == null) return '—';
  return n.toLocaleString();
}

// General number formatter: integers use toLocaleString(); floats show up to 4 decimal places.
function fmt(n) {
  if (n == null) return '—';
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function StatRow({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-gray-400 whitespace-nowrap">{label}</dt>
      <dd className="text-gray-700 tabular-nums text-right">{value}</dd>
    </div>
  );
}

function ReportPanel({ reportState }) {
  if (!reportState || reportState.loading) {
    return <p className="text-sm text-gray-400">Loading report…</p>;
  }
  if (reportState.error) {
    return <p className="text-sm text-red-500">{reportState.error}</p>;
  }
  const r = reportState.data;
  if (!r) return null;
  if (!r.present) {
    return <p className="text-sm text-gray-400">Indicator not yet produced — run an update first.</p>;
  }

  return (
    <div className="flex flex-wrap gap-8 text-xs">
      {/* Date span */}
      <div className="min-w-[140px]">
        <p className="font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Date span</p>
        <dl className="space-y-1">
          <StatRow label="First" value={r.first_date ?? '—'} />
          <StatRow label="Last" value={r.last_date ?? '—'} />
          <StatRow label="Days" value={fmt(r.n_days)} />
          <StatRow label="Rows" value={fmt(r.rows)} />
        </dl>
      </div>

      {/* Ticker stats — only when has_tickers */}
      {r.has_tickers && (
        <div className="min-w-[160px]">
          <p className="font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Tickers</p>
          <dl className="space-y-1">
            <StatRow label="Total distinct" value={fmt(r.tickers_total)} />
            <StatRow label="Mean / day" value={r.tickers_mean_per_day != null ? String(r.tickers_mean_per_day) : '—'} />
            <StatRow label="Median / day" value={fmt(r.tickers_median_per_day)} />
            <StatRow label="Last day" value={fmt(r.tickers_last_day)} />
          </dl>
        </div>
      )}

      {/* Value stats */}
      <div className="min-w-[160px]">
        <p className="font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
          {r.value_column ? `Values (${r.value_column})` : 'Values'}
        </p>
        {r.value_column ? (
          <dl className="space-y-1">
            <StatRow label="Min" value={fmt(r.value_min)} />
            <StatRow label="Max" value={fmt(r.value_max)} />
            <StatRow label="Mean" value={fmt(r.value_mean)} />
            <StatRow label="Median" value={fmt(r.value_median)} />
            <StatRow label="Nulls" value={fmt(r.value_nulls)} />
          </dl>
        ) : (
          <p className="text-gray-400 italic">No single value column (multiple numeric columns)</p>
        )}
      </div>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [force, setForce] = useState(false);
  const [rowState, setRowState] = useState({});
  const [expanded, setExpanded] = useState({});
  const [reportCache, setReportCache] = useState({});

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/status');
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function runUpdate(name) {
    setRowState((prev) => ({ ...prev, [name]: { status: 'running', message: '' } }));
    try {
      const url = `/api/run-update/${name}${force ? '?force=true' : ''}`;
      const res = await fetch(url, { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        const rows = body.rows ?? 0;
        setRowState((prev) => ({
          ...prev,
          [name]: { status: 'done', message: `✓ ${rows.toLocaleString()} rows` },
        }));
        load();
      } else {
        const msg = body.detail || body.error || `HTTP ${res.status}`;
        setRowState((prev) => ({ ...prev, [name]: { status: 'error', message: msg } }));
      }
    } catch {
      setRowState((prev) => ({ ...prev, [name]: { status: 'error', message: 'request failed' } }));
    }
  }

  async function fetchReport(name) {
    setReportCache((prev) => ({ ...prev, [name]: { loading: true, data: null, error: null } }));
    try {
      const res = await fetch(`/api/report/${name}`);
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        setReportCache((prev) => ({ ...prev, [name]: { loading: false, data: body, error: null } }));
      } else {
        const msg = body.detail || body.error || `HTTP ${res.status}`;
        setReportCache((prev) => ({ ...prev, [name]: { loading: false, data: null, error: msg } }));
      }
    } catch {
      setReportCache((prev) => ({ ...prev, [name]: { loading: false, data: null, error: 'request failed' } }));
    }
  }

  function toggleReport(name) {
    const willOpen = !expanded[name];
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    if (willOpen && !reportCache[name]) {
      fetchReport(name);
    }
  }

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Quanty Database</h1>
          <p className="text-sm text-gray-500 mt-0.5">Worker status</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300"
            />
            Force (bypass freshness &amp; cooldown)
          </label>
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="mb-6">
        <div className="flex gap-3">
          <a
            href="/api/download-group/indicators"
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 transition-colors"
          >
            Indicators
          </a>
          <a
            href="/api/download/quotes"
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 transition-colors"
          >
            Prices (quotes)
          </a>
          <a
            href="/api/download-group/macro"
            className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 transition-colors"
          >
            Macro
          </a>
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Downloads require the worker and tunnel to be running. Indicators ≈ 94 MB, Prices is large.
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700 mb-6">
          <strong>Worker unreachable.</strong> Make sure it&apos;s running on{' '}
          <code className="font-mono bg-red-100 px-1 rounded">http://localhost:8000</code>
          {' '}(<code className="font-mono bg-red-100 px-1 rounded">python -m src.main</code>).
        </div>
      )}

      {loading && !data && (
        <p className="text-sm text-gray-400">Loading…</p>
      )}

      {data && (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="w-full text-sm border-collapse">
            <thead className="bg-gray-50">
              <tr className="text-left text-xs text-gray-500 uppercase tracking-wide">
                <th className="px-4 py-3 font-medium border-b border-gray-200">Indicator</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Provider</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Kind</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Present</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Fresh</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Last date</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200 text-right">Rows</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Updated at</th>
                <th className="px-4 py-3 font-medium border-b border-gray-200">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.map((ind) => {
                const rs = rowState[ind.name] || { status: 'idle', message: '' };
                const muted = !ind.present ? 'opacity-40' : '';
                const isExpanded = !!expanded[ind.name];
                return (
                  <Fragment key={ind.name}>
                    <tr className="border-b border-gray-100 hover:bg-gray-50">
                      <td className={`px-4 py-2.5 font-mono font-medium text-gray-900 ${muted}`}>{ind.name}</td>
                      <td className={`px-4 py-2.5 text-gray-600 ${muted}`}>{ind.provider}</td>
                      <td className={`px-4 py-2.5 text-gray-600 ${muted}`}>{KIND_LABELS[ind.kind] ?? ind.kind}</td>
                      <td className={`px-4 py-2.5 text-gray-700 ${muted}`}>{ind.present ? 'Yes' : 'No'}</td>
                      <td className={`px-4 py-2.5 ${muted}`}>
                        <FreshBadge fresh={ind.present ? ind.fresh : undefined} />
                      </td>
                      <td className={`px-4 py-2.5 text-gray-700 tabular-nums ${muted}`}>{formatDate(ind.last_date)}</td>
                      <td className={`px-4 py-2.5 text-gray-700 text-right tabular-nums ${muted}`}>{formatRows(ind.rows)}</td>
                      <td className={`px-4 py-2.5 text-gray-500 ${muted}`}>{formatUpdatedAt(ind.updated_at)}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            onClick={() => runUpdate(ind.name)}
                            disabled={rs.status === 'running'}
                            className="px-2.5 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 transition-colors whitespace-nowrap"
                          >
                            {rs.status === 'running' ? 'Updating…' : 'Update'}
                          </button>
                          {ind.present && (
                            <button
                              onClick={() => toggleReport(ind.name)}
                              className="px-2.5 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50 transition-colors whitespace-nowrap"
                            >
                              {isExpanded ? 'Hide' : 'Report'}
                            </button>
                          )}
                          {rs.message && (
                            <span
                              className={`text-xs ${
                                rs.status === 'error' ? 'text-red-600' : 'text-green-700'
                              }`}
                            >
                              {rs.message}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr className="border-b border-gray-100 bg-gray-50">
                        <td colSpan={9} className="px-6 py-4">
                          <ReportPanel reportState={reportCache[ind.name]} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
