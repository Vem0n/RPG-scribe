import { useEffect, useState } from "react";
import { loadConfig, type AppConfig } from "./store";
import Wizard from "./pages/Wizard";
import Dashboard from "./pages/Dashboard";

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConfig().then((cfg) => {
      setConfig(cfg);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--bg)]">
        <div className="text-[var(--text-muted)] text-sm">Loading...</div>
      </div>
    );
  }

  if (!config?.wizardCompleted) {
    return <Wizard onComplete={(cfg) => setConfig(cfg)} />;
  }

  return <Dashboard config={config} setConfig={setConfig} />;
}
