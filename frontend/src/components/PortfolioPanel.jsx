import { useState } from "react";
import { api, fmtInr, fmtPct } from "@/lib/api";
import { Wallet, RotateCcw } from "lucide-react";
import { toast } from "sonner";

export default function PortfolioPanel({ portfolio, onReset, growthTarget = 4000 }) {
  const p = portfolio;
  const [balance, setBalance] = useState(3000);
  const [showReset, setShowReset] = useState(false);

  const equity = p?.total_equity ?? 0;
  const initial = p?.initial_balance ?? 3000;
  const targetProgress = Math.min(100, Math.max(0, ((equity - initial) / Math.max(1, growthTarget - initial)) * 100));
  const targetHit = equity >= growthTarget;

  const doReset = async () => {
    try {
      await api.post("/portfolio/reset", { initial_balance: Math.max(100, Math.min(20000, balance)) });
      toast.success(`Portfolio reset to ₹${balance}`);
      setShowReset(false);
      onReset?.();
    } catch { toast.error("Reset failed"); }
  };

  return (
    <div className="panel relative overflow-hidden" data-testid="portfolio-panel"
      style={{
        backgroundImage:
          "linear-gradient(rgba(10,10,10,0.92), rgba(10,10,10,0.96)), url(https://images.pexels.com/photos/14911424/pexels-photo-14911424.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
        backgroundSize: "cover",
      }}
    >
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Wallet className="w-4 h-4 text-[#00E676]" />
        <span className="text-sm font-medium">Paper Wallet</span>
        <button className="kbd-label ml-auto inline-flex items-center gap-1 hover:text-white" onClick={() => setShowReset(!showReset)} data-testid="reset-portfolio-btn">
          <RotateCcw className="w-3 h-3" /> Reset
        </button>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <div className="kbd-label">Total Equity</div>
          <div className="mono text-3xl font-medium" data-testid="equity-value">{fmtInr(p?.total_equity ?? 0, 2)}</div>
          <div className={`mono text-sm ${(p?.total_return_pct ?? 0) >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}`}>
            {fmtPct(p?.total_return_pct ?? 0)} from {fmtInr(p?.initial_balance ?? 0, 0)}
          </div>
        </div>

        <div className="border border-white/10 rounded-sm p-3 bg-white/[0.02]" data-testid="growth-target">
          <div className="flex items-center justify-between mb-1.5">
            <span className="kbd-label">{targetHit ? "🎉 Target Hit" : "Growth Target"}</span>
            <span className="mono text-xs">{fmtInr(equity, 0)} / {fmtInr(growthTarget, 0)}</span>
          </div>
          <div className="w-full bg-white/5 h-2 rounded">
            <div className={`h-2 rounded transition-all ${targetHit ? "bg-[#00E676]" : "bg-[#007AFF]"}`} style={{ width: `${targetProgress}%` }}></div>
          </div>
          {targetHit && <div className="kbd-label mt-1.5 text-[#00E676]">Bot paused — share CoinDCX API keys for live mode</div>}
        </div>

        {showReset && (
          <div className="border border-white/10 rounded-sm p-3 space-y-2 bg-white/[0.02]">
            <div className="kbd-label">Reset balance (₹100 – ₹20,000)</div>
            <div className="flex gap-2 items-center">
              <input type="number" value={balance} min={100} max={20000} onChange={(e) => setBalance(parseFloat(e.target.value || "0"))} className="flex-1 bg-[#0A0A0A] border border-white/15 rounded-sm mono text-sm px-2 py-1.5" data-testid="reset-balance-input" />
              <button onClick={doReset} className="bg-[#007AFF] hover:bg-[#0056b3] text-white text-xs px-3 py-1.5 rounded-sm font-bold" data-testid="confirm-reset-btn">CONFIRM</button>
            </div>
            <div className="flex gap-1">
              {[1000, 3000, 5000, 10000, 20000].map((v) => (
                <button key={v} onClick={() => setBalance(v)} className="kbd-label px-2 py-0.5 border border-white/10 rounded-sm hover:bg-white/5">₹{v / 1000}k</button>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10">
          <div>
            <div className="kbd-label">Cash</div>
            <div className="mono text-sm">{fmtInr(p?.balance ?? 0, 0)}</div>
          </div>
          <div>
            <div className="kbd-label">Position Value</div>
            <div className="mono text-sm">{fmtInr(p?.total_positions_value ?? 0, 0)}</div>
          </div>
        </div>

        {p?.positions?.length > 0 && (
          <div className="pt-3 border-t border-white/10">
            <div className="kbd-label mb-2">Open Positions ({p.positions.length})</div>
            <div className="space-y-1.5">
              {p.positions.map((pos) => (
                <div key={pos.symbol} className="flex items-center justify-between px-2 py-1.5 bg-white/[0.03] rounded-sm" data-testid={`position-${pos.symbol}`}>
                  <div>
                    <div className="text-xs font-medium">{pos.symbol}</div>
                    <div className="kbd-label">@{fmtInr(pos.entry_price, 2)}</div>
                  </div>
                  <div className="text-right">
                    <div className="mono text-xs">{fmtInr(pos.value || 0, 0)}</div>
                    <div className={`mono text-xs ${(pos.pnl_pct ?? 0) >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}`}>{fmtPct(pos.pnl_pct ?? 0)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
