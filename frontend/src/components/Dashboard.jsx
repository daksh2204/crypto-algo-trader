import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import TopBar from "@/components/TopBar";
import MarketStrip from "@/components/MarketStrip";
import PriceChart from "@/components/PriceChart";
import BotControl from "@/components/BotControl";
import AIInsights from "@/components/AIInsights";
import LiveSignals from "@/components/LiveSignals";
import TradeHistory from "@/components/TradeHistory";
import PortfolioPanel from "@/components/PortfolioPanel";
import ManualTradePanel from "@/components/ManualTradePanel";

export default function Dashboard() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval_] = useState("1h");
  const [tickers, setTickers] = useState([]);
  const [portfolio, setPortfolio] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [botStatus, setBotStatus] = useState({ running: false, config: {} });
  const [signal, setSignal] = useState(null);
  const [signalLoading, setSignalLoading] = useState(false);

  const loadTickers = useCallback(async () => {
    try {
      const { data } = await api.get("/market/tickers");
      setTickers(data.tickers || []);
    } catch (e) { console.error(e); }
  }, []);

  const loadPortfolio = useCallback(async () => {
    try {
      const { data } = await api.get("/portfolio");
      setPortfolio(data);
    } catch (e) { console.error(e); }
  }, []);

  const loadMetrics = useCallback(async () => {
    try {
      const { data } = await api.get("/metrics");
      setMetrics(data);
    } catch (e) { console.error(e); }
  }, []);

  const loadBot = useCallback(async () => {
    try {
      const { data } = await api.get("/bot/status");
      setBotStatus(data);
    } catch (e) { console.error(e); }
  }, []);

  const loadSignal = useCallback(async (sym, iv, ai = true) => {
    setSignalLoading(true);
    try {
      const { data } = await api.get(`/signals/${sym}`, { params: { interval: iv, use_ai: ai } });
      setSignal(data);
    } catch (e) {
      console.error(e);
    } finally {
      setSignalLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTickers();
    loadPortfolio();
    loadMetrics();
    loadBot();
    const t = window.setInterval(() => {
      loadTickers();
      loadPortfolio();
      loadMetrics();
      loadBot();
    }, 10000);
    return () => window.clearInterval(t);
  }, [loadTickers, loadPortfolio, loadMetrics, loadBot]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-3 md:p-4" data-testid="dashboard-root">
      <TopBar
        portfolio={portfolio}
        metrics={metrics}
        botStatus={botStatus}
        onRefresh={() => { loadPortfolio(); loadMetrics(); loadBot(); }}
      />

      <MarketStrip
        tickers={tickers}
        activeSymbol={symbol}
        onSelect={(s) => setSymbol(s)}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 md:gap-4 mt-3 md:mt-4">
        <div className="lg:col-span-8 space-y-3 md:space-y-4">
          <PriceChart
            symbol={symbol}
            interval={interval}
            setInterval_={setInterval_}
            signal={signal}
            onLoadSignal={() => loadSignal(symbol, interval, true)}
            signalLoading={signalLoading}
          />
          <AIInsights signal={signal} />
          <TradeHistory onRefresh={() => { loadPortfolio(); loadMetrics(); }} />
        </div>

        <div className="lg:col-span-4 space-y-3 md:space-y-4">
          <PortfolioPanel portfolio={portfolio} onReset={async () => { await api.post("/portfolio/reset"); loadPortfolio(); loadMetrics(); }} />
          <BotControl status={botStatus} onChange={loadBot} />
          <ManualTradePanel symbol={symbol} onDone={() => { loadPortfolio(); loadMetrics(); }} />
          <LiveSignals />
        </div>
      </div>

      <div className="text-center kbd-label mt-6 py-4 opacity-60">
        ⚠ Paper trading mode · Market data via Binance public API · AI by Claude Sonnet 4.5 · Not financial advice
      </div>
    </div>
  );
}
