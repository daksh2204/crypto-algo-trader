import { useEffect, useState } from "react";
import { api, fmtUsd, fmtNum } from "@/lib/api";
import { History } from "lucide-react";

export default function TradeHistory({ onRefresh }) {
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get("/trades", { params: { limit: 50 } });
        if (alive) setTrades(data.trades || []);
      } catch {}
    };
    load();
    const t = window.setInterval(load, 10000);
    return () => { alive = false; window.clearInterval(t); };
  }, [onRefresh]);

  return (
    <div className="panel" data-testid="trade-history">
      <div className="px-4 md:px-6 py-3 border-b border-white/10 flex items-center gap-2">
        <History className="w-4 h-4 text-[#007AFF]" />
        <span className="text-sm font-medium">Trade History</span>
        <span className="kbd-label ml-auto">{trades.length} records</span>
      </div>
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-xs mono min-w-[700px]">
          <thead className="kbd-label text-left">
            <tr className="border-b border-white/10">
              <th className="py-2 px-4">Time</th>
              <th className="py-2 px-4">Symbol</th>
              <th className="py-2 px-4">Side</th>
              <th className="py-2 px-4">Type</th>
              <th className="py-2 px-4 text-right">Qty</th>
              <th className="py-2 px-4 text-right">Price</th>
              <th className="py-2 px-4 text-right">P&L</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr><td colSpan="7" className="px-4 py-8 text-center kbd-label">No trades yet. Start the bot or place a manual trade.</td></tr>
            )}
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-white/[0.05] hover:bg-white/[0.02]" data-testid={`trade-${t.id}`}>
                <td className="py-2 px-4 text-white/60">{new Date(t.timestamp).toLocaleString()}</td>
                <td className="py-2 px-4 font-medium">{t.symbol}</td>
                <td className={`py-2 px-4 font-bold ${t.side === "BUY" ? "text-[#00E676]" : "text-[#FF3D00]"}`}>{t.side}</td>
                <td className="py-2 px-4 text-white/60">{t.type}</td>
                <td className="py-2 px-4 text-right">{fmtNum(t.qty, 6)}</td>
                <td className="py-2 px-4 text-right">{fmtUsd(t.price, t.price < 1 ? 4 : 2)}</td>
                <td className={`py-2 px-4 text-right font-bold ${t.pnl > 0 ? "text-[#00E676]" : t.pnl < 0 ? "text-[#FF3D00]" : "text-white/40"}`}>
                  {t.type === "OPEN" || t.type === "MANUAL" && t.side === "BUY" ? "—" : fmtUsd(t.pnl || 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
