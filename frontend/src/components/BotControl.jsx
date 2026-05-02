import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Play, Square, Bot, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const STRATS = [
  { id: "MA_CROSSOVER", label: "MA Crossover" },
  { id: "RSI", label: "RSI" },
  { id: "MACD", label: "MACD" },
  { id: "BOLLINGER", label: "Bollinger" },
];

export default function BotControl({ status, onChange }) {
  const [cfg, setCfg] = useState({
    symbols: ["BTCINR", "ETHINR", "SOLINR"],
    interval: "15m",
    strategies: ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
    use_ai: true,
    use_news: true,
    min_confidence: 0.6,
    min_strategies_agree: 1,
    stop_loss_pct: 2,
    take_profit_pct: 5,
    trailing_stop: true,
    position_size_pct: 5,
    max_daily_loss_pct: 5,
    max_concurrent_positions: 3,
    allow_pyramiding: false,
    max_positions_per_symbol: 1,
    growth_target: 4000,
    auto_start: true,
    loop_seconds: 60,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (status?.config && Object.keys(status.config).length) {
      setCfg((c) => ({ ...c, ...status.config }));
    }
  }, [status]);

  const toggleStrat = (id) => {
    setCfg((c) => ({ ...c, strategies: c.strategies.includes(id) ? c.strategies.filter((x) => x !== id) : [...c.strategies, id] }));
  };

  const start = async () => {
    setSaving(true);
    try {
      await api.post("/bot/start", cfg);
      toast.success("Bot running in safe mode");
      onChange?.();
    } catch { toast.error("Failed to start bot"); }
    finally { setSaving(false); }
  };

  const stop = async () => {
    setSaving(true);
    try { await api.post("/bot/stop"); toast.info("Bot stopped"); onChange?.(); }
    catch { toast.error("Failed to stop bot"); }
    finally { setSaving(false); }
  };

  const running = status?.running;

  return (
    <div className="panel" data-testid="bot-control">
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Bot className="w-4 h-4 text-[#007AFF]" />
        <span className="text-sm font-medium">Trading Bot</span>
        <span className="ml-auto inline-flex items-center gap-1 kbd-label text-[#00E676]">
          <ShieldCheck className="w-3 h-3" /> SAFE
        </span>
      </div>
      <div className="p-4 space-y-4">
        <div>
          <div className="kbd-label mb-2">Strategies</div>
          <div className="grid grid-cols-2 gap-2">
            {STRATS.map((s) => {
              const on = cfg.strategies.includes(s.id);
              return (
                <button
                  key={s.id}
                  onClick={() => toggleStrat(s.id)}
                  disabled={running}
                  className={`text-xs px-2.5 py-2 rounded-sm border transition-colors ${on ? "bg-[#007AFF]/10 border-[#007AFF] text-white" : "border-white/10 text-white/70 hover:bg-white/5"} ${running ? "opacity-60 cursor-not-allowed" : ""}`}
                  data-testid={`strategy-${s.id}`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        <label className="flex items-center justify-between text-sm" data-testid="use-ai-toggle">
          <span>AI signal (Claude 4.5)</span>
          <input type="checkbox" checked={cfg.use_ai} disabled={running} onChange={(e) => setCfg({ ...cfg, use_ai: e.target.checked })} className="accent-[#007AFF] w-4 h-4" />
        </label>

        <label className="flex items-center justify-between text-sm" data-testid="use-news-toggle">
          <span>News + sentiment layer</span>
          <input type="checkbox" checked={cfg.use_news} disabled={running || !cfg.use_ai} onChange={(e) => setCfg({ ...cfg, use_news: e.target.checked })} className="accent-[#007AFF] w-4 h-4" />
        </label>

        <label className="flex items-center justify-between text-sm" data-testid="trailing-stop-toggle">
          <span>Trailing stop-loss</span>
          <input type="checkbox" checked={cfg.trailing_stop} disabled={running} onChange={(e) => setCfg({ ...cfg, trailing_stop: e.target.checked })} className="accent-[#00E676] w-4 h-4" />
        </label>

        <label className="flex items-center justify-between text-sm" data-testid="autostart-toggle">
          <span>Auto-start on app boot</span>
          <input type="checkbox" checked={cfg.auto_start} disabled={running} onChange={(e) => setCfg({ ...cfg, auto_start: e.target.checked })} className="accent-[#00E676] w-4 h-4" />
        </label>

        <label className="flex items-center justify-between text-sm" data-testid="pyramid-toggle">
          <span>Allow pyramiding (same symbol)</span>
          <input type="checkbox" checked={cfg.allow_pyramiding} disabled={running} onChange={(e) => setCfg({ ...cfg, allow_pyramiding: e.target.checked })} className="accent-[#FFC107] w-4 h-4" />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <NumField label="Stop Loss %" value={cfg.stop_loss_pct} onChange={(v) => setCfg({ ...cfg, stop_loss_pct: v })} testid="sl-input" disabled={running} />
          <NumField label="Take Profit %" value={cfg.take_profit_pct} onChange={(v) => setCfg({ ...cfg, take_profit_pct: v })} testid="tp-input" disabled={running} />
          <NumField label="Position Size %" value={cfg.position_size_pct} onChange={(v) => setCfg({ ...cfg, position_size_pct: v })} testid="size-input" disabled={running} />
          <NumField label="Min Confidence" value={cfg.min_confidence} step={0.05} onChange={(v) => setCfg({ ...cfg, min_confidence: v })} testid="conf-input" disabled={running} />
          <NumField label="Min Strategies ≥" value={cfg.min_strategies_agree} step={1} onChange={(v) => setCfg({ ...cfg, min_strategies_agree: Math.max(1, Math.min(4, Math.round(v))) })} testid="agree-input" disabled={running} />
          <NumField label="Daily Loss Stop %" value={cfg.max_daily_loss_pct} onChange={(v) => setCfg({ ...cfg, max_daily_loss_pct: v })} testid="dayloss-input" disabled={running} />
          <NumField label="Max Open Pos" value={cfg.max_concurrent_positions} step={1} onChange={(v) => setCfg({ ...cfg, max_concurrent_positions: Math.max(1, Math.min(8, Math.round(v))) })} testid="maxpos-input" disabled={running} />
          <NumField label="Per-Symbol Max" value={cfg.max_positions_per_symbol} step={1} onChange={(v) => setCfg({ ...cfg, max_positions_per_symbol: Math.max(1, Math.min(4, Math.round(v))) })} testid="persym-input" disabled={running || !cfg.allow_pyramiding} />
          <NumField label="Growth Target ₹" value={cfg.growth_target} step={500} onChange={(v) => setCfg({ ...cfg, growth_target: v })} testid="target-input" disabled={running} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="kbd-label mb-1">Interval</div>
            <select value={cfg.interval} disabled={running} onChange={(e) => setCfg({ ...cfg, interval: e.target.value })} className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-xs px-2 py-2 focus:border-[#007AFF] outline-none" data-testid="interval-select">
              {["5m", "15m", "1h", "4h"].map((iv) => <option key={iv} value={iv}>{iv}</option>)}
            </select>
          </div>
          <NumField label="Loop (s)" value={cfg.loop_seconds} onChange={(v) => setCfg({ ...cfg, loop_seconds: Math.max(20, v) })} testid="loop-input" disabled={running} />
        </div>

        {!running ? (
          <button onClick={start} disabled={saving || cfg.strategies.length === 0} className="w-full bg-[#00E676] hover:bg-[#00C853] text-black font-bold text-sm py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50" data-testid="start-bot-btn">
            <Play className="w-4 h-4" /> START BOT
          </button>
        ) : (
          <button onClick={stop} disabled={saving} className="w-full bg-[#FF3D00] hover:bg-[#D50000] text-white font-bold text-sm py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2" data-testid="stop-bot-btn">
            <Square className="w-4 h-4" /> STOP BOT
          </button>
        )}
        {status?.circuit_tripped && (
          <div className="text-[11px] text-[#FF3D00] bg-[#FF3D00]/10 border border-[#FF3D00]/30 p-2 rounded-sm">
            Daily loss circuit tripped. Reset portfolio or wait for next day to restart.
          </div>
        )}
      </div>
    </div>
  );
}

function NumField({ label, value, onChange, step = 0.5, testid, disabled }) {
  return (
    <div>
      <div className="kbd-label mb-1">{label}</div>
      <input
        type="number" step={step} value={value} disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value || "0"))}
        className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-xs px-2 py-2 focus:border-[#007AFF] outline-none disabled:opacity-60"
        data-testid={testid}
      />
    </div>
  );
}
