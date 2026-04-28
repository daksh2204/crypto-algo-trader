import { Brain, ShieldAlert } from "lucide-react";

const ACTION_COLOR = {
  BUY: "text-[#00E676] border-[#00E676]/30 bg-[#00E676]/10",
  SELL: "text-[#FF3D00] border-[#FF3D00]/30 bg-[#FF3D00]/10",
  HOLD: "text-[#FFC107] border-[#FFC107]/30 bg-[#FFC107]/10",
};

export default function AIInsights({ signal }) {
  const ai = signal?.ai;
  const classical = signal?.classical;
  return (
    <div
      className="panel relative overflow-hidden"
      data-testid="ai-insights"
      style={{
        backgroundImage:
          "linear-gradient(rgba(10,10,10,0.9), rgba(10,10,10,0.95)), url(https://images.pexels.com/photos/29611783/pexels-photo-29611783.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <div className="px-4 md:px-6 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-[#007AFF]" />
          <span className="text-sm font-medium tracking-tight">AI Market Analysis</span>
          <span className="kbd-label">Claude Sonnet 4.5</span>
        </div>
        {signal && (
          <div className="kbd-label">
            {signal.symbol} · {new Date(signal.timestamp).toLocaleTimeString()}
          </div>
        )}
      </div>

      {!signal && (
        <div className="p-6 kbd-label">
          Click <span className="text-[#007AFF]">Get AI Signal</span> on the chart to generate an analysis.
        </div>
      )}

      {signal && (
        <div className="p-4 md:p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-1 space-y-3">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-sm border ${ACTION_COLOR[ai?.action || "HOLD"]}`} data-testid="ai-action">
              <span className="kbd-label" style={{ color: "inherit" }}>Action</span>
              <span className="mono font-bold text-sm">{ai?.action || "—"}</span>
            </div>
            <div>
              <div className="kbd-label">Confidence</div>
              <div className="mono text-2xl font-medium">{((ai?.confidence ?? 0) * 100).toFixed(0)}%</div>
              <div className="w-full bg-white/5 h-1 mt-1 rounded">
                <div className="h-1 bg-[#007AFF] rounded" style={{ width: `${(ai?.confidence ?? 0) * 100}%` }}></div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-[#FFC107]" />
              <span className="kbd-label">Risk</span>
              <span className="mono text-xs">{ai?.risk_level || "—"}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-white/[0.03] rounded-sm p-2">
                <div className="kbd-label">Stop Loss</div>
                <div className="mono text-sm text-[#FF3D00]">-{ai?.stop_loss_pct ?? "—"}%</div>
              </div>
              <div className="bg-white/[0.03] rounded-sm p-2">
                <div className="kbd-label">Take Profit</div>
                <div className="mono text-sm text-[#00E676]">+{ai?.take_profit_pct ?? "—"}%</div>
              </div>
            </div>
          </div>

          <div className="md:col-span-2 space-y-3">
            <div>
              <div className="kbd-label mb-1">Reasoning</div>
              <p className="text-sm leading-relaxed text-white/85" data-testid="ai-reasoning">
                {ai?.reasoning || "—"}
              </p>
            </div>
            {ai?.key_factors?.length > 0 && (
              <div>
                <div className="kbd-label mb-1">Key Factors</div>
                <div className="flex flex-wrap gap-1.5">
                  {ai.key_factors.map((f, i) => (
                    <span key={i} className="mono text-xs px-2 py-0.5 bg-white/5 border border-white/10 rounded-sm">{f}</span>
                  ))}
                </div>
              </div>
            )}
            {classical?.per_strategy && (
              <div>
                <div className="kbd-label mb-1">Classical Strategies</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {Object.entries(classical.per_strategy).map(([k, v]) => (
                    <div key={k} className="bg-white/[0.03] border border-white/10 rounded-sm p-2">
                      <div className="flex items-center justify-between">
                        <span className="kbd-label">{k.replace("_", " ")}</span>
                        <span className={`mono text-xs font-bold ${ACTION_COLOR[v.action]?.split(" ")[0] || "text-white"}`}>{v.action}</span>
                      </div>
                      <div className="mono text-xs text-white/60 mt-1 line-clamp-2">{v.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
