import { useState } from "react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useAuth } from "../../lib/hooks/useAuth";

export default function SettingsPage() {
  const { user } = useAuth();
  const [businessName, setBusinessName] = useState(user?.business_name || "");
  const [saved, setSaved] = useState(false);

  // TODO: Wire to a settings endpoint when the backend exposes one.
  // Currently the backend PRD doesn't define a settings/payment-methods-enabled endpoint.
  // Using local state for now as specified in Section 6.7.
  const [enabledMethods, setEnabledMethods] = useState({
    btc_onchain: true,
    lightning: true,
    usdc: true,
    usdt: true,
  });

  const toggleMethod = (method: keyof typeof enabledMethods) => {
    setEnabledMethods((prev) => ({ ...prev, [method]: !prev[method] }));
  };

  const handleSave = () => {
    // TODO: POST to settings endpoint when available
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-8 max-w-lg">
      <h1 className="text-display-md">Settings</h1>

      <Card className="p-6 space-y-6">
        <div className="space-y-2">
          <label className="text-body-sm font-medium text-silver">Business name</label>
          <Input
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            placeholder="My Business"
          />
        </div>
        
        <div className="space-y-4">
          <label className="text-body-sm font-medium text-silver">Enabled payment methods</label>
          {(["btc_onchain", "lightning", "usdc", "usdt"] as const).map((method) => (
            <label key={method} className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={enabledMethods[method]}
                onChange={() => toggleMethod(method)}
                className="w-4 h-4 rounded border-line bg-ink accent-white"
              />
              <span className="text-body-sm text-silver group-hover:text-white transition-colors">
                {method === "btc_onchain" ? "BTC On-chain" :
                 method === "lightning" ? "Lightning" :
                 method.toUpperCase()}
              </span>
            </label>
          ))}
        </div>
      </Card>

      <Card className="p-6 space-y-4">
        <h2 className="text-body-lg font-semibold text-white">Account</h2>
        <div className="space-y-1">
          <p className="text-body-sm text-silver-dim">Email</p>
          <p className="text-body-sm text-white">{user?.email || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-body-sm text-silver-dim">Account created</p>
          <p className="text-body-sm text-white">
            {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
          </p>
        </div>
      </Card>

      <div className="flex items-center gap-4">
        <Button
          variant="primary"
          className="bg-white text-ink hover:bg-silver"
          onClick={handleSave}
        >
          {saved ? "Saved ✓" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}
