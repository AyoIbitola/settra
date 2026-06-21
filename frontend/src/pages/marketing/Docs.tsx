import { Navbar } from "../../components/layout/Navbar";
import { Footer } from "../../components/layout/Footer";

export default function Docs() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-grow pt-32 pb-20 px-6 max-w-4xl mx-auto w-full space-y-12">
        <div className="space-y-4">
          <h1 className="text-display-lg text-white">Documentation</h1>
          <p className="text-body-lg text-silver">
            Everything you need to integrate Settra into your business workflow.
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
           <div className="space-y-4">
              <h3 className="text-display-md text-white">Quickstart</h3>
              <p className="text-body text-silver">
                Follow our 5-minute guide to sending your first cryptographic invoice.
              </p>
              <a href="#" className="text-white text-body-sm font-semibold hover:underline">Read Guide →</a>
           </div>
           <div className="space-y-4">
              <h3 className="text-display-md text-white">API Reference</h3>
              <p className="text-body text-silver">
                Detailed documentation for our REST API endpoints and webhooks.
              </p>
              <a href="#" className="text-white text-body-sm font-semibold hover:underline">Explore API →</a>
           </div>
        </div>

        <div className="p-8 border border-line rounded-lg bg-ink-raised space-y-4">
           <h3 className="text-body-lg font-semibold text-white">Need help?</h3>
           <p className="text-body-sm text-silver">Our engineering team is available for technical support via email or Slack.</p>
           <a href="mailto:support@settra.com" className="text-signal text-body-sm hover:underline">Contact Support</a>
        </div>
      </main>
      <Footer />
    </div>
  );
}
