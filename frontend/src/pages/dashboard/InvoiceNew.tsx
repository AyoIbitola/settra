import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { createInvoice } from "../../lib/api/invoices";
import { Check, Copy } from "lucide-react";

export default function InvoiceNew() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: string; link: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const [form, setForm] = useState({
    client_name: "",
    client_email: "",
    description: "",
    amount_usd: "",
    due_date: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const invoice = await createInvoice({
        client_name: form.client_name,
        client_email: form.client_email,
        description: form.description || undefined,
        amount_usd: form.amount_usd,
        due_date: form.due_date || undefined,
      });
      const link = `${window.location.origin}/pay/${invoice.id}`;
      setCreated({ id: invoice.id, link });
    } catch (err: any) {
      setError(err.message || "Failed to create invoice");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (created) {
      navigator.clipboard.writeText(created.link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (created) {
    return (
      <div className="max-w-lg mx-auto space-y-8">
        <h1 className="text-display-md">Invoice created</h1>
        <Card className="p-8 space-y-6">
          <div className="flex items-center gap-3 text-signal">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-body-lg font-semibold">Ready to share</span>
          </div>
          <p className="text-body-sm text-silver">Send this link to your client so they can pay:</p>
          <div className="flex items-center gap-2">
            <Input value={created.link} readOnly isMono className="flex-1 text-mono-sm" />
            <Button variant="primary" className="shrink-0 gap-2" onClick={handleCopy}>
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <div className="flex gap-4 pt-4">
            <Button variant="ghost" onClick={() => navigate("/dashboard/invoices")}>Back to invoices</Button>
            <Button variant="ghost" onClick={() => navigate(`/dashboard/invoices/${created.id}`)}>View detail</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto space-y-8">
      <h1 className="text-display-md">New Invoice</h1>

      <Card className="p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Client name</label>
            <Input
              required
              placeholder="Acme Corp"
              value={form.client_name}
              onChange={(e) => setForm({ ...form, client_name: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Client email</label>
            <Input
              type="email"
              required
              placeholder="billing@acme.com"
              value={form.client_email}
              onChange={(e) => setForm({ ...form, client_email: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Description</label>
            <textarea
              placeholder="Logo design, brand guidelines delivery…"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="flex w-full rounded-md border border-line bg-ink px-4 py-3 text-body text-white placeholder:text-silver-dim focus-visible:outline-none focus-visible:border-silver-dim transition-colors min-h-[80px] resize-y"
            />
          </div>

          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Amount (USD)</label>
            <Input
              required
              type="text"
              inputMode="decimal"
              placeholder="500.00"
              isMono
              className="text-display-md h-16"
              value={form.amount_usd}
              onChange={(e) => setForm({ ...form, amount_usd: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <label className="text-body-sm font-medium text-silver">Due date (optional)</label>
            <Input
              type="date"
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            />
          </div>

          {error && <p className="text-body-sm text-danger">{error}</p>}

          <Button
            type="submit"
            disabled={loading}
            variant="primary"
            className="w-full bg-white text-ink hover:bg-silver py-4 text-body font-semibold"
          >
            {loading ? "Creating…" : "Create Invoice"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
