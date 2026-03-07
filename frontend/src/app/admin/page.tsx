"use client";

import { useState } from "react";
import { PageShell } from "@/components/layout/PageShell";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY ?? "";

async function triggerEndpoint(path: string) {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    method: "POST",
    headers: { "X-Admin-Key": ADMIN_KEY, "Content-Type": "application/json" },
  });
  return res.json();
}

const ACTIONS = [
  { label: "Ingest Domain API", path: "/admin/ingest/domain_api" },
  { label: "Ingest Valuer General", path: "/admin/ingest/valuer_general" },
  { label: "Ingest NSW Sales", path: "/admin/ingest/nsw_sales" },
  { label: "Retrain ML Model", path: "/admin/ml/retrain" },
  { label: "Run Batch Predictions", path: "/admin/ml/predict-all" },
  { label: "Enrich OSM Amenities", path: "/admin/ml/osm-enrich" },
];

export default function AdminPage() {
  const [results, setResults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<string | null>(null);

  async function run(action: { label: string; path: string }) {
    setLoading(action.path);
    try {
      const data = await triggerEndpoint(action.path);
      setResults((r) => ({ ...r, [action.path]: JSON.stringify(data, null, 2) }));
    } catch (e) {
      setResults((r) => ({ ...r, [action.path]: `Error: ${e}` }));
    } finally {
      setLoading(null);
    }
  }

  return (
    <PageShell title="Admin">
      <div className="max-w-2xl space-y-4">
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
          Admin actions require <code>X-Admin-Key</code> header. Set{" "}
          <code>NEXT_PUBLIC_ADMIN_KEY</code> in your environment.
        </div>

        {ACTIONS.map((action) => (
          <div
            key={action.path}
            className="bg-white rounded-xl border border-gray-200 p-4 flex items-start gap-4"
          >
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">{action.label}</p>
              <p className="text-xs text-gray-400 font-mono mt-0.5">POST {action.path}</p>
              {results[action.path] && (
                <pre className="mt-2 text-xs bg-gray-50 rounded p-2 overflow-auto max-h-24 text-gray-700">
                  {results[action.path]}
                </pre>
              )}
            </div>
            <button
              onClick={() => run(action)}
              disabled={loading === action.path}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {loading === action.path ? "Running…" : "Run"}
            </button>
          </div>
        ))}
      </div>
    </PageShell>
  );
}
