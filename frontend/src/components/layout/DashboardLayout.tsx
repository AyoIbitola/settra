import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/hooks/useAuth";
import { LayoutDashboard, FileText, AlertTriangle, Settings, LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Overview", end: true },
  { to: "/dashboard/invoices", icon: FileText, label: "Invoices" },
  { to: "/dashboard/overpayments", icon: AlertTriangle, label: "Overpayments" },
  { to: "/dashboard/settings", icon: Settings, label: "Settings" },
];

export function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-ink flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed lg:sticky top-0 left-0 z-50 h-screen w-64 bg-ink/70 backdrop-blur-3xl border-r border-white/5 shadow-[4px_0_24px_rgba(0,0,0,0.4)] flex flex-col transition-transform duration-300",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-white/[0.04] flex items-center justify-between">
          <span className="text-white font-display text-2xl font-bold tracking-tighter" style={{ textShadow: "0 2px 10px rgba(255,255,255,0.15)" }}>Settra<span className="text-signal">.</span></span>
          <button className="lg:hidden text-silver-dim hover:text-white transition-colors" onClick={() => setSidebarOpen(false)}>
            <X size={20} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-body-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-white/10 text-white shadow-sm ring-1 ring-white/10"
                    : "text-silver-dim hover:text-white hover:bg-white/[0.04]"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User menu */}
        <div className="p-4 border-t border-white/[0.04] bg-gradient-to-t from-black/20 to-transparent space-y-3">
          <div className="px-3">
            <p className="text-body-sm text-white font-medium truncate">{user?.business_name || "My Business"}</p>
            <p className="text-[11px] text-silver-dim/80 truncate">{user?.email || ""}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-2 w-full rounded-lg text-body-sm text-silver-dim hover:text-white hover:bg-white/[0.05] transition-all duration-200 group"
          >
            <LogOut size={16} className="group-hover:translate-x-1 transition-transform" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Top bar (mobile) */}
        <header className="lg:hidden sticky top-0 z-30 bg-ink border-b border-line px-4 py-3 flex items-center gap-4">
          <button onClick={() => setSidebarOpen(true)} className="text-silver hover:text-white">
            <Menu size={22} />
          </button>
          <span className="text-white font-display font-bold">Settra</span>
        </header>

        <main className="flex-1 p-6 lg:p-10 w-full">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
