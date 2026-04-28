import { fmtUsd, fmtPct } from "@/lib/api";
import { Wallet, RotateCcw } from "lucide-react";

export default function PortfolioPanel({ portfolio, onReset }) {
  const p = portfolio;
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
        <span className="text-sm font-medium">Paper Portfolio</span>
        <button className="kbd-label ml-auto inline-flex items-center gap-1 hover:text-white" onClick={onReset} data-testid="reset-portfolio-btn">
          <RotateCcw className="w-3 h-3" /> Reset
        </button>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <div className="kbd-label">Total Equity</div>
          <div className="mono text-3xl font-medium" data-testid="equity-value">{fmtUsd(p?.total_equity ?? 0)}</div>
          <div className={`mono text-sm ${(p?.total_return_pct ?? 0) >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}`}>
            {fmtPct(p?.total_return_pct ?? 0)} from {fmtUsd(p?.initial_balance ?? 10000)}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10">
          <div>
            <div className="kbd-label">Cash</div>
            <div className="mono text-sm">{fmtUsd(p?.balance ?? 0)}</div>
          </div>
          <div>
            <div className="kbd-label">Position Value</div>
            <div className="mono text-sm">{fmtUsd(p?.total_positions_value ?? 0)}</div>
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
                    <div className="kbd-label">@{fmtUsd(pos.entry_price)}</div>
                  </div>
                  <div className="text-right">
                    <div className="mono text-xs">{fmtUsd(pos.value || 0)}</div>
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
