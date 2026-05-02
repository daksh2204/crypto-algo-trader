import { useEffect, useState } from "react";
import { api, fmtPct, fmtInr } from "@/lib/api";
import { Trophy, Zap, RotateCw, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function LeaderboardPanel() {
  const [board, setBoard] = useState([]);
  const [lastRun, setLastRun] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/leaderboard");
      setBoard(data.leaderboard || []);
      setLastRun(data.last_run);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const runSweep = async () => {
    setBusy(true);
    try {
      await api.post("/leaderboard/run");
      toast.success("Leaderboard refreshed");
      load();
    } catch { toast.error("Sweep failed"); }
    finally { setBusy(false); }
  };

  const applyBest = async () => {
    try {
      const { data } = await api.post("/leaderboard/apply-best");
      toast.success(`Auto-tuned: ${data.best.symbol}/${data.best.interval}`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Apply failed"); }
  };

  return (
    <div className="panel" data-testid="leaderboard-panel">
      <div className="px-4 md:px-6 py-3 border-b border-white/10 flex items-center gap-2 flex-wrap">
        <Trophy className="w-4 h-4 text-[#FFC107]" />
        <span className="text-sm font-medium">Strategy Leaderboard</span>
        <span className="kbd-label">auto-optimizer</span>
        {lastRun && <span className="kbd-label ml-2">Last run: {new Date(lastRun.ran_at).toLocaleString()}</span>}
        <button onClick={runSweep} disabled={busy} className="ml-auto kbd-label inline-flex items-center gap-1 px-3 py-1.5 border border-white/10 hover:bg-white/5 rounded-sm disabled:opacity-50" data-testid="run-sweep-btn">
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCw className="w-3 h-3" />}
          {busy ? "SWEEPING…" : "RUN SWEEP"}
        </button>
        <button onClick={applyBest} disabled={board.length === 0} className="kbd-label inline-flex items-center gap-1 px-3 py-1.5 bg-[#00E676]/15 text-[#00E676] border border-[#00E676]/30 hover:bg-[#00E676]/25 rounded-sm disabled:opacity-50" data-testid="apply-best-btn">
          <Zap className="w-3 h-3" /> APPLY BEST TO BOT
        </button>
      </div>

      <div className="p-4 md:p-6">
        <p className="kbd-label mb-3">Runs backtests across all INR pairs × intervals × parameter sets, then ranks by score = return − 0.5·drawdown + 2·winrate.</p>
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-xs mono min-w-[900px]">
            <thead className="kbd-label text-left">
              <tr className="border-b border-white/10">
                <th className="py-2 px-2">#</th>
                <th className="py-2 px-2">Pair</th>
                <th className="py-2 px-2">Interval</th>
                <th className="py-2 px-2">Score</th>
                <th className="py-2 px-2 text-right">Return</th>
                <th className="py-2 px-2 text-right">Win %</th>
                <th className="py-2 px-2 text-right">Max DD</th>
                <th className="py-2 px-2 text-right">Trades</th>
                <th className="py-2 px-2 text-right">PF</th>
                <th className="py-2 px-2">Conf / Agree / SL / TP</th>
              </tr>
            </thead>
            <tbody>
              {board.length === 0 && (
                <tr><td colSpan="10" className="px-2 py-8 text-center kbd-label">No results yet. Click RUN SWEEP (takes ~30–60s).</td></tr>
              )}
              {board.map((r, idx) => (
                <tr key={idx} className={`border-b border-white/[0.05] ${idx === 0 ? "bg-[#FFC107]/5" : "hover:bg-white/[0.02]"}`} data-testid={`lb-row-${idx}`}>
                  <td className="py-2 px-2 text-white/40">{idx + 1}</td>
                  <td className="py-2 px-2 font-medium">{r.symbol}</td>
                  <td className="py-2 px-2">{r.interval}</td>
                  <td className="py-2 px-2 font-bold text-[#FFC107]">{r.score}</td>
                  <td className={`py-2 px-2 text-right ${r.total_return_pct >= 0 ? "text-[#00E676]" : "text-[#FF3D00]"}`}>{fmtPct(r.total_return_pct)}</td>
                  <td className="py-2 px-2 text-right">{r.win_rate_pct.toFixed(1)}%</td>
                  <td className="py-2 px-2 text-right text-[#FF3D00]">{r.max_drawdown_pct.toFixed(1)}%</td>
                  <td className="py-2 px-2 text-right">{r.total_trades}</td>
                  <td className="py-2 px-2 text-right">{(r.profit_factor || 0).toFixed(2)}</td>
                  <td className="py-2 px-2 text-white/60">{r.min_confidence} · {r.min_strategies_agree} · {r.stop_loss_pct}% · {r.take_profit_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
