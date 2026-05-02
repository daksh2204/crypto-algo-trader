import { useState } from "react";
import { api, fmtInr, fmtPct } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";

const STRATS = [
  { id: "MA_CROSSOVER", label: "MA" },
  { id: "RSI", label: "RSI" },
  { id: "MACD", label: "MACD" },
  { id: "BOLLINGER", label: "BB" },
];

const DEFAULT_SYMBOLS = ["BTCINR", "ETHINR", "SOLINR", "BNBINR", "XRPINR", "DOGEINR"];

export default function BacktestPanel() {
  const [cfg, setCfg] = useState({
    symbol: "BTCINR",
    interval: "1h",
    limit: 500,
    strategies: ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
    initial_balance: 3000,
    position_size_pct: 5,
    stop_loss_pct: 2,
    take_profit_pct: 5,
    min_confidence: 0.65,
    min_strategies_agree: 2,
    trailing_stop: true,
  });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);

  const run = async () => {
    setBusy(true); setRes(null);
    try {
      const { data } = await api.post("/backtest", cfg);
      setRes(data);
      toast.success(`Backtest: ${data.total_trades} trades, ${fmtPct(data.total_return_pct)} return`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Backtest failed");
    } finally { setBusy(false); }
  };

  const toggleStrat = (id) => {
    setCfg((c) => ({ ...c, strategies: c.strategies.includes(id) ? c.strategies.filter((x) => x !== id) : [...c.strategies, id] }));
  };

  return (
    <div className="panel" data-testid="backtest-panel">
      <div className="px-4 md:px-6 py-3 border-b border-white/10 flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-[#007AFF]" />
        <span className="text-sm font-medium">Backtest Engine</span>
        <span className="kbd-label ml-auto">Historical Simulation</span>
      </div>

      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="kbd-label mb-1">Symbol</div>
              <select value={cfg.symbol} onChange={(e) => setCfg({ ...cfg, symbol: e.target.value })} className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-xs px-2 py-2 focus:border-[#007AFF] outline-none" data-testid="bt-symbol">
                {DEFAULT_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <div className="kbd-label mb-1">Interval</div>
              <select value={cfg.interval} onChange={(e) => setCfg({ ...cfg, interval: e.target.value })} className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-xs px-2 py-2" data-testid="bt-interval">
                {["15m", "1h", "4h", "1d"].map((iv) => <option key={iv} value={iv}>{iv}</option>)}
              </select>
            </div>
          </div>

          <div>
            <div className="kbd-label mb-1">Strategies</div>
            <div className="flex gap-1">
              {STRATS.map((s) => {
                const on = cfg.strategies.includes(s.id);
                return (
                  <button key={s.id} onClick={() => toggleStrat(s.id)} className={`text-[11px] px-2 py-1 rounded-sm border ${on ? "bg-[#007AFF]/10 border-[#007AFF]" : "border-white/10 text-white/70"}`} data-testid={`bt-strat-${s.id}`}>
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <NumF label="Candles" v={cfg.limit} s={50} onC={(v) => setCfg({ ...cfg, limit: Math.min(1000, Math.max(80, v)) })} t="bt-limit" />
            <NumF label="Start ₹" v={cfg.initial_balance} s={500} onC={(v) => setCfg({ ...cfg, initial_balance: v })} t="bt-start" />
            <NumF label="Size %" v={cfg.position_size_pct} onC={(v) => setCfg({ ...cfg, position_size_pct: v })} t="bt-size" />
            <NumF label="SL %" v={cfg.stop_loss_pct} onC={(v) => setCfg({ ...cfg, stop_loss_pct: v })} t="bt-sl" />
            <NumF label="TP %" v={cfg.take_profit_pct} onC={(v) => setCfg({ ...cfg, take_profit_pct: v })} t="bt-tp" />
            <NumF label="Conf≥" v={cfg.min_confidence} s={0.05} onC={(v) => setCfg({ ...cfg, min_confidence: v })} t="bt-conf" />
          </div>

          <label className="flex items-center justify-between text-xs">
            <span>Trailing stop</span>
            <input type="checkbox" checked={cfg.trailing_stop} onChange={(e) => setCfg({ ...cfg, trailing_stop: e.target.checked })} className="accent-[#00E676]" data-testid="bt-trail" />
          </label>

          <button onClick={run} disabled={busy} className="w-full bg-[#007AFF] hover:bg-[#0056b3] text-white text-sm py-2.5 rounded-sm font-bold flex items-center justify-center gap-2 disabled:opacity-50" data-testid="run-backtest-btn">
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {busy ? "Running…" : "RUN BACKTEST"}
          </button>
        </div>

        <div className="lg:col-span-2 space-y-3">
          {!res && !busy && <div className="h-full flex items-center justify-center kbd-label min-h-[200px]">Run a backtest to see results.</div>}
          {res && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <Kpi label="Return" value={fmtPct(res.total_return_pct)} good={res.total_return_pct >= 0} testid="bt-return" />
                <Kpi label="Win Rate" value={`${res.win_rate_pct.toFixed(1)}%`} testid="bt-winrate" />
                <Kpi label="Trades" value={res.total_trades} testid="bt-trades" />
                <Kpi label="Max DD" value={`${res.max_drawdown_pct.toFixed(1)}%`} good={res.max_drawdown_pct < 10} testid="bt-dd" />
                <Kpi label="Final ₹" value={fmtInr(res.final_balance, 0)} testid="bt-final" />
                <Kpi label="Total P&L" value={fmtInr(res.total_pnl, 0)} good={res.total_pnl >= 0} testid="bt-pnl" />
                <Kpi label="Avg Win" value={fmtInr(res.avg_win, 0)} good testid="bt-avgwin" />
                <Kpi label="Avg Loss" value={fmtInr(res.avg_loss, 0)} testid="bt-avgloss" />
              </div>
              <div className="panel p-2 h-[220px] grid-bg">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={res.equity_curve}>
                    <defs>
                      <linearGradient id="bt-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#007AFF" stopOpacity={0.5} />
                        <stop offset="100%" stopColor="#007AFF" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" tickFormatter={(t) => new Date(t).toLocaleDateString()} tick={{ fill: "#a0a0a0", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#a0a0a0", fontSize: 10 }} tickFormatter={(v) => v.toFixed(0)} width={70} />
                    <Tooltip contentStyle={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)", fontSize: 11 }} formatter={(v) => [fmtInr(v), "Equity"]} labelFormatter={(t) => new Date(t).toLocaleString()} />
                    <Area type="monotone" dataKey="equity" stroke="#007AFF" fill="url(#bt-grad)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function NumF({ label, v, s = 0.5, onC, t }) {
  return (
    <div>
      <div className="kbd-label mb-1">{label}</div>
      <input type="number" step={s} value={v} onChange={(e) => onC(parseFloat(e.target.value || "0"))} className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-xs px-2 py-1.5" data-testid={t} />
    </div>
  );
}

function Kpi({ label, value, good, testid }) {
  return (
    <div className="bg-white/[0.03] border border-white/10 rounded-sm p-2" data-testid={testid}>
      <div className="kbd-label">{label}</div>
      <div className={`mono text-sm font-medium ${good === true ? "text-[#00E676]" : good === false ? "text-[#FF3D00]" : "text-white"}`}>{value}</div>
    </div>
  );
}
