import { Activity, Database, LogOut, Search, Server } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const nav = [
  { to: "/audits", label: "Audits", icon: Activity },
  { to: "/term-inference", label: "Term Inference", icon: Search },
  { to: "/targets", label: "Targets", icon: Server },
  { to: "/datasets", label: "Datasets", icon: Database }
];

export function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return (
    <div className="min-h-screen grid grid-cols-[240px_1fr]">
      <aside className="bg-white border-r border-slate-200 p-4 flex flex-col">
        <div className="font-semibold text-lg mb-6">RAG Timing Audit</div>
        <nav className="space-y-1 flex-1">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2 rounded-md text-sm ${isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`
                }
              >
                <Icon size={17} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <button
          className="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-slate-700 hover:bg-slate-100"
          onClick={async () => {
            await api.logout();
            queryClient.clear();
            navigate("/login", { replace: true });
          }}
        >
          <LogOut size={17} />
          Logout
        </button>
      </aside>
      <main className="p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
