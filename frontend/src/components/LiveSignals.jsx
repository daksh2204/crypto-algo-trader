import { useEffect, useState } from "react";
import { api, fmtUsd } from "@/lib/api";
import { Radio } from "lucide-react";

const COLOR = { BUY: "text-[#00E676]", SELL: "text-[#FF3D00]", HOLD: "text-[#FFC107]" };

export default function LiveSignals() {
  const [signals, setSignals] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get("/signals", { params: { limit: 20 } });
        if (alive) setSignals(data.signals || []);
      } catch {}
    };
    load();
    const t = window.setInterval(load, 8000);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  return (
    <div className="panel" data-testid="live-signals">
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Radio className="w-4 h-4 text-[#00E676]" />
        <span className="text-sm font-medium">Live Signals</span>
        <span className="pulse-dot ml-auto"></span>
      </div>
      <div className="max-h-[320px] overflow-y-auto scrollbar-thin">
        {signals.length === 0 && <div className="px-4 py-8 kbd-label text-center">Waiting for signals…</div>}
        {signals.map((s) => (
          <div key={s.id} className="px-4 py-2.5 border-b border-white/[0.07] hover:bg-white/[0.02] transition-colors" data-testid={`signal-${s.id}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`mono text-xs font-bold ${COLOR[s.action]}`}>{s.action}</span>
                <span className="text-sm">{s.symbol}</span>
              </div>
              <span className="mono text-xs">{fmtUsd(s.price, s.price < 1 ? 4 : 2)}</span>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="kbd-label">{(s.source || "").toUpperCase()} · conf {(s.confidence * 100).toFixed(0)}%</span>
              <span className="kbd-label">{new Date(s.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
