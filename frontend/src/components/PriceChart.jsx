import { useEffect, useState } from "react";
import { api, fmtInr, shortSym } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Loader2 } from "lucide-react";

const INTERVALS = ["5m", "15m", "1h", "4h", "1d"];

export default function PriceChart({ symbol, interval, setInterval_, signal, onLoadSignal, signalLoading }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    const fetchData = async () => {
      try {
        const { data: r } = await api.get(`/market/klines/${symbol}`, { params: { interval, limit: 200 } });
        if (alive) setData(r.klines || []);
      } catch (e) { console.error("klines", e); }
    };
    (async () => { setLoading(true); await fetchData(); if (alive) setLoading(false); })();
    const t = window.setInterval(fetchData, 20000);
    return () => { alive = false; window.clearInterval(t); };
  }, [symbol, interval]);

  const last = data[data.length - 1];
  const first = data[0];
  const change = last && first ? ((last.close - first.close) / first.close) * 100 : 0;
  const pos = change >= 0;
  const stroke = pos ? "#00E676" : "#FF3D00";

  return (
    <div className="panel" data-testid="price-chart">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 md:px-6 py-3 border-b border-white/10">
        <div>
          <div className="flex items-baseline gap-3">
            <span className="text-xl font-medium tracking-tight" data-testid="chart-symbol">{shortSym(symbol)}/INR</span>
            <span className="mono text-2xl">{last ? fmtInr(last.close, last.close < 1 ? 4 : 2) : "—"}</span>
            <span className={`mono text-sm ${pos ? "text-[#00E676]" : "text-[#FF3D00]"}`}>
              {pos ? "+" : ""}{change.toFixed(2)}% · {interval}
            </span>
          </div>
          <div className="kbd-label mt-1">CoinDCX · {data.length} candles</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex border border-white/10 rounded-sm overflow-hidden">
            {INTERVALS.map((iv) => (
              <button
                key={iv}
                onClick={() => setInterval_(iv)}
                className={`mono text-xs px-3 py-1.5 transition-colors ${interval === iv ? "bg-[#007AFF] text-white" : "hover:bg-white/5 text-white/70"}`}
                data-testid={`interval-${iv}`}
              >
                {iv}
              </button>
            ))}
          </div>
          <button
            className="mono text-xs px-3 py-1.5 bg-[#007AFF] hover:bg-[#0056b3] rounded-sm transition-colors flex items-center gap-1.5 disabled:opacity-60"
            onClick={onLoadSignal}
            disabled={signalLoading}
            data-testid="generate-signal-btn"
          >
            {signalLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
            {signalLoading ? "Analyzing…" : "Get AI Signal"}
          </button>
        </div>
      </div>

      <div className="h-[340px] md:h-[400px] grid-bg">
        {loading && data.length === 0 ? (
          <div className="h-full flex items-center justify-center kbd-label">Loading chart…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                tick={{ fill: "#a0a0a0", fontSize: 11, fontFamily: "JetBrains Mono" }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
                minTickGap={60}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#a0a0a0", fontSize: 11, fontFamily: "JetBrains Mono" }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
                tickFormatter={(v) => v.toFixed(v < 1 ? 4 : 0)}
                width={80}
              />
              <Tooltip
                contentStyle={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, fontFamily: "JetBrains Mono", fontSize: 12 }}
                labelFormatter={(t) => new Date(t).toLocaleString()}
                formatter={(v) => [fmtInr(v, v < 1 ? 4 : 2), "Close"]}
              />
              {signal?.indicators?.bb_upper ? (
                <>
                  <ReferenceLine y={signal.indicators.bb_upper} stroke="#FFC107" strokeDasharray="4 4" strokeOpacity={0.5} label={{ value: "BB↑", fill: "#FFC107", fontSize: 10 }} />
                  <ReferenceLine y={signal.indicators.bb_lower} stroke="#FFC107" strokeDasharray="4 4" strokeOpacity={0.5} label={{ value: "BB↓", fill: "#FFC107", fontSize: 10 }} />
                </>
              ) : null}
              <Area type="monotone" dataKey="close" stroke={stroke} strokeWidth={2} fill="url(#priceGradient)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
