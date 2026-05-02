import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bell, Trash2, AlertTriangle, CheckCircle2, Info, AlertOctagon } from "lucide-react";

const ICONS = {
  INFO: <Info className="w-3.5 h-3.5 text-[#007AFF]" />,
  SUCCESS: <CheckCircle2 className="w-3.5 h-3.5 text-[#00E676]" />,
  WARN: <AlertTriangle className="w-3.5 h-3.5 text-[#FFC107]" />,
  CRITICAL: <AlertOctagon className="w-3.5 h-3.5 text-[#FF3D00]" />,
};
const BORDER = {
  INFO: "border-[#007AFF]/20",
  SUCCESS: "border-[#00E676]/20",
  WARN: "border-[#FFC107]/30",
  CRITICAL: "border-[#FF3D00]/30",
};

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState([]);

  const load = async () => {
    try {
      const { data } = await api.get("/alerts", { params: { limit: 30 } });
      setAlerts(data.alerts || []);
    } catch {}
  };

  useEffect(() => {
    load();
    const t = window.setInterval(load, 5000);
    return () => window.clearInterval(t);
  }, []);

  const clearAll = async () => {
    await api.post("/alerts/clear");
    load();
  };

  return (
    <div className="panel" data-testid="alerts-panel">
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Bell className="w-4 h-4 text-[#FFC107]" />
        <span className="text-sm font-medium">Alerts</span>
        <span className="kbd-label ml-auto">{alerts.length}</span>
        <button onClick={clearAll} className="kbd-label hover:text-white inline-flex items-center gap-1" data-testid="clear-alerts-btn">
          <Trash2 className="w-3 h-3" /> Clear
        </button>
      </div>
      <div className="max-h-[260px] overflow-y-auto scrollbar-thin">
        {alerts.length === 0 && <div className="px-4 py-6 kbd-label text-center">No alerts yet.</div>}
        {alerts.map((a) => (
          <div key={a.id} className={`px-3 py-2.5 border-b border-white/[0.05] ${BORDER[a.level] || ""} hover:bg-white/[0.02]`} data-testid={`alert-${a.id}`}>
            <div className="flex items-start gap-2">
              <div className="mt-0.5">{ICONS[a.level] || ICONS.INFO}</div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate">{a.title}</div>
                <div className="text-[11px] text-white/60 break-words">{a.message}</div>
                <div className="kbd-label mt-0.5">{new Date(a.timestamp).toLocaleTimeString()}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
