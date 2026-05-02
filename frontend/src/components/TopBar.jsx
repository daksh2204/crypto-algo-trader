import { fmtInr, fmtPct } from "@/lib/api";
import { Activity, TrendingUp, Zap, RefreshCw, ShieldCheck } from "lucide-react";

export default function TopBar({ portfolio, metrics, botStatus, onRefresh }) {
  const equity = portfolio?.total_equity ?? 0;
  const ret = portfolio?.total_return_pct ?? 0;
  const pnl = metrics?.total_pnl ?? 0;
  const win = metrics?.win_rate_pct ?? 0;
  const running = botStatus?.running;
  const tripped = botStatus?.circuit_tripped;
  const targetHit = botStatus?.target_hit;

  return (
    <div className="panel mb-3 md:mb-4" data-testid="top-bar">
      <div className="flex flex-wrap items-center gap-4 md:gap-6 px-4 md:px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-sm bg-[#007AFF] flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <div className="text-sm font-medium tracking-tight">QUANTEDGE</div>
            <div className="kbd-label">CoinDCX · INR Terminal</div>
          </div>
        </div>

        <div className="flex-1 min-w-[200px] flex items-center gap-2 flex-wrap">
          <span className="kbd-label inline-flex items-center gap-2 px-2 py-1 bg-[#FFC107]/15 text-[#FFC107] rounded-sm font-bold tracking-widest" data-testid="mode-badge">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FFC107] animate-pulse"></span>
            PAPER
          </span>
          <span className={`kbd-label inline-flex items-center gap-2 px-2 py-1 rounded-sm font-bold tracking-widest ${running ? "bg-[#00E676]/15 text-[#00E676]" : targetHit ? "bg-[#00E676]/25 text-[#00E676]" : tripped ? "bg-[#FF3D00]/15 text-[#FF3D00]" : "bg-white/5 text-white/60"}`} data-testid="bot-status-badge">
            <span className={`w-1.5 h-1.5 rounded-full ${running ? "bg-[#00E676] animate-pulse" : targetHit ? "bg-[#00E676]" : tripped ? "bg-[#FF3D00]" : "bg-white/40"}`}></span>
            {running ? "AUTO-RUNNING" : targetHit ? "🎉 TARGET HIT" : tripped ? "CIRCUIT TRIPPED" : "BOT IDLE"}
          </span>
          <span className="kbd-label inline-flex items-center gap-1 text-[#00E676]">
            <ShieldCheck className="w-3 h-3" /> SAFE MODE
          </span>
        </div>

        <Stat icon={<TrendingUp className="w-3.5 h-3.5" />} label="Equity" value={fmtInr(equity, 0)} sub={<span className={ret >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}>{fmtPct(ret)}</span>} testid="stat-equity" />
        <Stat icon={<Activity className="w-3.5 h-3.5" />} label="Total P&L" value={<span className={pnl >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}>{fmtInr(pnl, 0)}</span>} testid="stat-pnl" />
        <Stat label="Win Rate" value={`${win.toFixed(1)}%`} testid="stat-winrate" />
        <Stat label="Trades" value={metrics?.total_trades ?? 0} testid="stat-trades" />

        <button className="kbd-label inline-flex items-center gap-2 px-3 py-2 border border-white/10 hover:bg-white/5 rounded-sm transition-colors" onClick={onRefresh} data-testid="refresh-btn">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>
    </div>
  );
}

function Stat({ icon, label, value, sub, testid }) {
  return (
    <div className="flex flex-col" data-testid={testid}>
      <div className="kbd-label flex items-center gap-1.5">{icon}{label}</div>
      <div className="mono text-lg font-medium leading-tight">{value}</div>
      {sub && <div className="mono text-xs">{sub}</div>}
    </div>
  );
}
