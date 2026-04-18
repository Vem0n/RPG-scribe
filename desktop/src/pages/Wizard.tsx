import { useState } from "react";
import { saveConfig, setApiKey, type AppConfig } from "../store";

interface WizardProps {
  onComplete: (config: AppConfig) => void;
}

export default function Wizard({ onComplete }: WizardProps) {
  const [step, setStep] = useState(0);
  const [serverUrl, setServerUrl] = useState("http://localhost:8081");
  const [username, setUsername] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${serverUrl}/api/v1/health`);
      setTestResult(res.ok ? "ok" : "error");
    } catch { setTestResult("error"); }
    setTesting(false);
  }

  async function finish() {
    const config: AppConfig = {
      serverUrl,
      wizardCompleted: true,
      activeUser: username,
      users: {
        [username]: { username, enabledGames: {} },
      },
    };
    // Order matters: write the secret to the keyring first so a crash
    // between these two writes leaves us with "key set, no config" rather
    // than "config saved, no key" — the user can re-run the wizard either
    // way, but the latter looks like a successful setup with broken auth.
    await setApiKey(apiKey);
    await saveConfig(config);
    onComplete(config);
  }

  const inputStyle: React.CSSProperties = {
    background: "var(--bg-tertiary)",
    border: "1px solid var(--border-color)",
    color: "var(--text-primary)",
    borderRadius: 8,
    padding: "10px 14px",
    width: "100%",
    fontSize: 14,
  };

  const btnPrimary: React.CSSProperties = {
    background: "var(--accent)",
    color: "#fff",
    borderRadius: 8,
    padding: "12px 0",
    fontWeight: 600,
    fontSize: 14,
    border: "none",
    cursor: "pointer",
    width: "100%",
    boxShadow: "0 4px 16px rgba(124,92,252,0.3)",
  };

  const btnOutline: React.CSSProperties = {
    background: "transparent",
    color: "var(--text-secondary)",
    borderRadius: 8,
    padding: "12px 0",
    fontWeight: 500,
    fontSize: 14,
    border: "1px solid var(--border-color)",
    cursor: "pointer",
    width: "100%",
  };

  return (
    <div className="flex items-center justify-center h-screen" style={{ background: "var(--bg-primary)" }}>
      <div style={{ width: 380, padding: 32 }}>
        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-2 h-2 rounded-full" style={{ background: i === step ? "var(--accent)" : "var(--border-color)" }} />
          ))}
        </div>

        {step === 0 && (
          <div className="flex flex-col items-center gap-5 text-center">
            <div className="text-5xl">📜</div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Welcome to RPG Scribe</h1>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Track your quest progress across your favorite RPGs. Let's get you set up.
            </p>
            <button onClick={() => setStep(1)} style={btnPrimary}>Get Started</button>
          </div>
        )}

        {step === 1 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>Connect to Server</h2>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Enter the URL of your RPG Scribe server.</p>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Server URL</label>
                <input type="url" value={serverUrl} onChange={(e) => { setServerUrl(e.target.value); setTestResult(null); }} placeholder="http://localhost:8081" style={inputStyle} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>API Key</label>
                <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter your API key" style={inputStyle} />
              </div>
              <button onClick={testConnection} disabled={testing || !serverUrl} style={{ ...btnOutline, opacity: testing || !serverUrl ? 0.5 : 1 }}>
                {testing ? "Testing..." : "Test Connection"}
              </button>
              {testResult === "ok" && <div className="text-xs flex items-center gap-1.5" style={{ color: "var(--success)" }}>✓ Connected</div>}
              {testResult === "error" && <div className="text-xs flex items-center gap-1.5" style={{ color: "var(--danger)" }}>✗ Could not connect</div>}
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(0)} style={btnOutline}>Back</button>
              <button onClick={() => setStep(2)} disabled={!serverUrl} style={{ ...btnPrimary, opacity: !serverUrl ? 0.5 : 1 }}>Next</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>Your Identity</h2>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Choose a username to identify your playthroughs.</p>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Username</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="BigBoss" style={inputStyle} onKeyDown={(e) => e.key === "Enter" && username && finish()} />
            </div>
            <div className="flex gap-3">
              <button onClick={() => setStep(1)} style={btnOutline}>Back</button>
              <button onClick={finish} disabled={!username} style={{ ...btnPrimary, opacity: !username ? 0.5 : 1 }}>Finish Setup</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
