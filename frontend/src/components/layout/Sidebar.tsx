"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Building2, MapPin, Heart, ShieldCheck } from "lucide-react";
import { cn } from "@/components/ui/cn";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/properties", label: "Properties", icon: Building2 },
  { href: "/suburbs", label: "Suburbs", icon: MapPin },
  { href: "/watchlist", label: "Watchlist", icon: Heart },
  { href: "/admin", label: "Admin", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-[220px] bg-[#1E1B4B] flex flex-col z-50">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-indigo-900">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-500 rounded flex items-center justify-center">
            <Building2 size={16} className="text-white" />
          </div>
          <span className="text-white font-semibold text-sm">Sydney RE</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-800 text-indigo-200 border-l-2 border-indigo-400"
                  : "text-[#C7D2FE] hover:bg-indigo-800/50 hover:text-indigo-200"
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Model status */}
      <div className="px-4 py-4 border-t border-indigo-900">
        <div className="text-xs text-indigo-400 bg-indigo-900/50 rounded px-2 py-1.5">
          <span className="inline-block w-1.5 h-1.5 bg-green-400 rounded-full mr-1.5 align-middle" />
          ML Model Active
        </div>
      </div>
    </aside>
  );
}
