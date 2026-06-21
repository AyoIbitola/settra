import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Card } from "../../components/ui/Card";
import { useAuth } from "../../lib/hooks/useAuth";

export default function Signup() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(email, businessName, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.message || "Failed to create account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink p-6">
      <Card className="w-full max-w-md p-8 space-y-8 bg-ink-raised border-line shadow-2xl">
        <div className="space-y-2 text-center">
          <Link to="/" className="text-white font-display text-2xl font-bold">Settra</Link>
          <h1 className="text-display-md text-white">Create your account</h1>
          <p className="text-body-sm text-silver-dim">Start getting paid in Bitcoin & stablecoins natively</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Business Name</label>
            <Input 
              type="text" 
              placeholder="Settra Labs Ltd" 
              required 
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Email address</label>
            <Input 
              type="email" 
              placeholder="name@company.com" 
              required 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Password</label>
            <Input 
              type="password" 
              placeholder="••••••••" 
              required 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          
          {error && <p className="text-body-sm text-danger text-center">{error}</p>}
          
          <Button 
            type="submit" 
            disabled={loading}
            variant="primary" 
            className="w-full bg-white text-ink hover:bg-silver py-6 text-body font-semibold"
          >
            {loading ? "Creating account..." : "Create account"}
          </Button>
        </form>

        <div className="text-center">
          <p className="text-body-sm text-silver-dim">
            Already have an account?{" "}
            <Link to="/login" className="text-white hover:underline transition-all">Sign in</Link>
          </p>
        </div>
      </Card>
    </div>
  );
}

