import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./lib/hooks/useAuth";
import { MarketingLayout } from "./components/layout/MarketingLayout";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import Landing from "./pages/marketing/Landing";
import Pricing from "./pages/marketing/Pricing";
import Docs from "./pages/marketing/Docs";
import Login from "./pages/auth/Login";
import Signup from "./pages/auth/Signup";
import Overview from "./pages/dashboard/Overview";
import InvoiceList from "./pages/dashboard/InvoiceList";
import InvoiceNew from "./pages/dashboard/InvoiceNew";
import InvoiceDetail from "./pages/dashboard/InvoiceDetail";
import Overpayments from "./pages/dashboard/Overpayments";
import SettingsPage from "./pages/dashboard/Settings";
import Pay from "./pages/public/Pay";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Marketing Site */}
          <Route element={<MarketingLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/docs" element={<Docs />} />
          </Route>

          {/* Auth */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Public Payment Page */}
          <Route path="/pay/:id" element={<Pay />} />

          {/* Dashboard (authenticated) */}
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<Overview />} />
              <Route path="/dashboard/invoices" element={<InvoiceList />} />
              <Route path="/dashboard/invoices/new" element={<InvoiceNew />} />
              <Route path="/dashboard/invoices/:id" element={<InvoiceDetail />} />
              <Route path="/dashboard/overpayments" element={<Overpayments />} />
              <Route path="/dashboard/settings" element={<SettingsPage />} />
            </Route>
          </Route>

          {/* Fallback */}
          <Route path="*" element={
            <div className="min-h-screen bg-ink flex items-center justify-center text-white font-display text-4xl">
              404 — Not Found
            </div>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
