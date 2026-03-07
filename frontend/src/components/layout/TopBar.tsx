"use client";

import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const qc = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    await qc.invalidateQueries();
    setTimeout(() => setRefreshing(false), 800);
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center px-6 gap-4">
      <h1 className="text-lg font-semibold text-gray-900 flex-1">{title}</h1>

      <button
        onClick={handleRefresh}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
      >
        <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
        Refresh
      </button>

      <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white text-xs font-semibold">
        SRE
      </div>
    </header>
  );
}
