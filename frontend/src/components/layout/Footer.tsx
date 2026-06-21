import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-line bg-ink py-16 px-6">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-12">
        <div className="space-y-4">
          <Link to="/" className="text-white font-display text-xl font-bold">
            Settra
          </Link>
          <p className="text-body-sm text-silver-dim max-w-xs">
            The modern standard for Bitcoin and stablecoin invoicing. Lock USD rates, receive crypto.
          </p>
        </div>
        
        <div>
          <h4 className="text-white font-display font-semibold mb-4">Product</h4>
          <ul className="space-y-2 text-body-sm text-silver-dim">
            <li><Link to="/" className="hover:text-white transition-colors">Features</Link></li>
            <li><Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link></li>
            <li><Link to="/docs" className="hover:text-white transition-colors">API Docs</Link></li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-display font-semibold mb-4">Company</h4>
          <ul className="space-y-2 text-body-sm text-silver-dim">
            <li><a href="#" className="hover:text-white transition-colors">About</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-display font-semibold mb-4">Legal</h4>
          <ul className="space-y-2 text-body-sm text-silver-dim">
            <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
            <li><a href="#" className="hover:text-white transition-colors">Terms</a></li>
          </ul>
        </div>
      </div>
      
      <div className="max-w-7xl mx-auto mt-16 pt-8 border-t border-line flex justify-between items-center text-body-sm text-silver-dim">
        <p>© 2026 Settra. All rights reserved.</p>
        <p>Built for the decentralized future.</p>
      </div>
    </footer>
  );
}
