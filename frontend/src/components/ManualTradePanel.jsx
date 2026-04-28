import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export default function ManualTradePanel({ symbol, onDone }) {
  const [amount, setAmount] = useState(500);
  const [busy, setBusy] = useState(false);

  const submit = async (side) => {
    setBusy(true);
    try {
      await api.post("/trades/manual", { symbol, side, quantity_usd: amount });
      toast.success(`${side} ${symbol} executed`);
      onDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Trade failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" data-testid="manual-trade">
      <div className="px-4 py-3 border-b border-white/10 text-sm font-medium">Manual Paper Trade</div>
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="kbd-label">Symbol</span>
          <span className="mono text-sm">{symbol}</span>
        </div>
        <div>
          <div className="kbd-label mb-1">Amount (USD)</div>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(parseFloat(e.target.value || "0"))}
            className="w-full bg-[#0A0A0A] border border-white/15 rounded-sm mono text-sm px-3 py-2 focus:border-[#007AFF] outline-none"
            data-testid="manual-amount-input"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            disabled={busy}
            onClick={() => submit("BUY")}
            className="bg-[#00E676]/15 hover:bg-[#00E676]/25 text-[#00E676] border border-[#00E676]/30 py-2 rounded-sm flex items-center justify-center gap-1.5 text-sm font-bold transition-colors disabled:opacity-50"
            data-testid="manual-buy-btn"
          >
            <ArrowUpRight className="w-4 h-4" /> BUY
          </button>
          <button
            disabled={busy}
            onClick={() => submit("SELL")}
            className="bg-[#FF3D00]/15 hover:bg-[#FF3D00]/25 text-[#FF3D00] border border-[#FF3D00]/30 py-2 rounded-sm flex items-center justify-center gap-1.5 text-sm font-bold transition-colors disabled:opacity-50"
            data-testid="manual-sell-btn"
          >
            <ArrowDownRight className="w-4 h-4" /> SELL
          </button>
        </div>
      </div>
    </div>
  );
}
