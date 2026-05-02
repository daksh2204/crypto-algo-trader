import { fmtInr, fmtPct, shortSym } from "@/lib/api";

export default function MarketStrip({ tickers, activeSymbol, onSelect }) {
  return (
    <div className="panel overflow-x-auto scrollbar-thin" data-testid="market-strip">
      <div className="flex min-w-max">
        {(tickers || []).map((t) => {
          const pos = t.change_pct >= 0;
          const active = t.symbol === activeSymbol;
          return (
            <button
              key={t.symbol}
              onClick={() => onSelect(t.symbol)}
              className={`flex flex-col items-start gap-1 px-4 md:px-5 py-3 border-r border-white/10 transition-colors min-w-[160px] text-left ${active ? "bg-white/5" : "hover:bg-white/[0.03]"}`}
              data-testid={`ticker-${t.symbol}`}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium tracking-tight">{shortSym(t.symbol)}</span>
                <span className="kbd-label">INR</span>
              </div>
              <span className="mono text-base font-medium">{fmtInr(t.price, t.price < 1 ? 4 : 2)}</span>
              <span className={`mono text-xs ${pos ? "text-[#00E676]" : "text-[#FF3D00]"}`}>{fmtPct(t.change_pct)}</span>
            </button>
          );
        })}
        {(!tickers || tickers.length === 0) && (
          <div className="px-4 py-3 kbd-label">Loading CoinDCX market data…</div>
        )}
      </div>
    </div>
  );
}
