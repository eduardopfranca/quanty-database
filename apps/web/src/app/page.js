'use client';

import { useEffect, useState } from 'react';

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

export default function Home() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Quanty Database</h1>
          <p className="text-sm text-gray-500 mt-0.5">Worker status</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
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
              </tr>
            </thead>
            <tbody>
              {data.map((ind) => (
                <tr
                  key={ind.name}
                  className={`border-b border-gray-100 last:border-0 ${
                    !ind.present ? 'opacity-40' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-4 py-2.5 font-mono font-medium text-gray-900">{ind.name}</td>
                  <td className="px-4 py-2.5 text-gray-600">{ind.provider}</td>
                  <td className="px-4 py-2.5 text-gray-600">{KIND_LABELS[ind.kind] ?? ind.kind}</td>
                  <td className="px-4 py-2.5 text-gray-700">{ind.present ? 'Yes' : 'No'}</td>
                  <td className="px-4 py-2.5">
                    <FreshBadge fresh={ind.present ? ind.fresh : undefined} />
                  </td>
                  <td className="px-4 py-2.5 text-gray-700 tabular-nums">{formatDate(ind.last_date)}</td>
                  <td className="px-4 py-2.5 text-gray-700 text-right tabular-nums">{formatRows(ind.rows)}</td>
                  <td className="px-4 py-2.5 text-gray-500">{formatUpdatedAt(ind.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
