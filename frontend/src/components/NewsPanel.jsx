import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Newspaper, Flame, Gauge } from "lucide-react";

export default function NewsPanel() {
  const [news, setNews] = useState({ headlines: [], trending: [], fear_greed: null });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await api.get("/news");
        if (alive) setNews(data);
      } catch {}
    };
    load();
    const t = window.setInterval(load, 120000);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  const fng = news.fear_greed;
  const fngColor = !fng ? "text-white/60" : fng.value < 25 ? "text-[#FF3D00]" : fng.value < 50 ? "text-[#FFC107]" : fng.value < 75 ? "text-[#00E676]" : "text-[#00E676]";

  return (
    <div className="panel" data-testid="news-panel">
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Newspaper className="w-4 h-4 text-[#007AFF]" />
        <span className="text-sm font-medium">Market Intel</span>
      </div>
      <div className="p-4 space-y-4">
        {fng && (
          <div className="flex items-center justify-between bg-white/[0.03] border border-white/10 rounded-sm p-3" data-testid="fear-greed">
            <div className="flex items-center gap-2">
              <Gauge className={`w-4 h-4 ${fngColor}`} />
              <div>
                <div className="kbd-label">Fear & Greed</div>
                <div className={`mono text-sm font-bold ${fngColor}`}>{fng.value} · {fng.classification}</div>
              </div>
            </div>
            <div className="w-24 h-2 bg-white/10 rounded">
              <div className={`h-2 rounded ${fng.value < 25 ? "bg-[#FF3D00]" : fng.value < 50 ? "bg-[#FFC107]" : "bg-[#00E676]"}`} style={{ width: `${fng.value}%` }}></div>
            </div>
          </div>
        )}

        {news.trending?.length > 0 && (
          <div>
            <div className="kbd-label mb-1.5 flex items-center gap-1"><Flame className="w-3 h-3 text-[#FF3D00]" /> Trending on CoinGecko</div>
            <div className="flex flex-wrap gap-1.5">
              {news.trending.slice(0, 8).map((t) => (
                <span key={t.symbol} className="mono text-xs px-2 py-0.5 bg-[#FF3D00]/10 text-[#FF3D00] border border-[#FF3D00]/20 rounded-sm" data-testid={`trending-${t.symbol}`}>
                  {t.symbol}
                </span>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="kbd-label mb-2">Headlines · CoinDesk</div>
          <div className="space-y-2 max-h-[280px] overflow-y-auto scrollbar-thin">
            {news.headlines?.slice(0, 6).map((h, i) => (
              <a key={i} href={h.url} target="_blank" rel="noreferrer" className="block border-l-2 border-[#007AFF]/40 pl-2 hover:border-[#007AFF] transition-colors" data-testid={`headline-${i}`}>
                <div className="text-xs font-medium leading-snug line-clamp-2">{h.title}</div>
                <div className="kbd-label mt-0.5">{h.published ? new Date(h.published).toLocaleString() : ""}</div>
              </a>
            ))}
            {(!news.headlines || news.headlines.length === 0) && <div className="kbd-label">Loading news…</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
