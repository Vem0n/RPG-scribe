import { useState, useEffect } from "react";
import type { GameConfig } from "../games";
import type { AppConfig, GameState } from "../store";

interface GameSetupProps {
  game: GameConfig;
  config: AppConfig;
  onComplete: (state: GameState) => void;
  onCancel: () => void;
}

export default function GameSetup({ game, config, onComplete, onCancel }: GameSetupProps) {
  const [step, setStep] = useState(0);
  const [savePath, setSavePath] = useState("");
  const [playthroughs, setPlaythroughs] = useState<string[]>([]);
  const [selectedPlaythrough, setSelectedPlaythrough] = useState<string>("");
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    async function resolveDefault() {
      const raw = game.defaultSavePaths[0] || "";
      try {
        const { homeDir } = await import("@tauri-apps/api/path");
        const home = (await homeDir()).replace(/\\/g, "/").replace(/\/$/, "");
        setSavePath(raw.replace("%USERPROFILE%", home));
      } catch {
        setSavePath(raw);
      }
    }
    resolveDefault();
  }, [game]);

  async function browsePath() {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, title: `Select ${game.name} save folder` });
      if (selected) setSavePath(selected as string);
    } catch {}
  }

  async function scanPlaythroughs() {
    setScanning(true);
    try {
      const { readDir } = await import("@tauri-apps/plugin-fs");
      const entries = await readDir(savePath);
      const dirs = entries.filter((e) => e.isDirectory).map((e) => e.name).filter((n): n is string => !!n && !n.startsWith(".")).sort();
      setPlaythroughs(dirs);
    } catch { setPlaythroughs([]); }
    setScanning(false);
  }

  function finish() {
    onComplete({ enabled: true, savePath, selectedPlaythrough: selectedPlaythrough || undefined });
  }

  const needsPlaythroughSelection = game.playthroughDetection === "character-folders" || game.playthroughDetection === "save-folders";

  const inputStyle: React.CSSProperties = { background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", color: "var(--text-primary)", borderRadius: 8, padding: "10px 14px", fontSize: 13, flex: 1 };
  const btnPrimary: React.CSSProperties = { background: "var(--accent)", color: "#fff", borderRadius: 8, padding: "12px 0", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", width: "100%", boxShadow: "0 4px 16px rgba(124,92,252,0.3)" };
  const btnOutline: React.CSSProperties = { background: "transparent", color: "var(--text-secondary)", borderRadius: 8, padding: "12px 0", fontWeight: 500, fontSize: 14, border: "1px solid var(--border-color)", cursor: "pointer", width: "100%" };

  return (
    <div className="flex flex-col h-screen" style={{ background: "var(--bg-primary)" }}>
      <div data-tauri-drag-region className="shrink-0 flex items-center gap-3 px-5 h-12" style={{ background: "var(--bg-secondary)", borderBottom: "1px solid var(--border-subtle)" }}>
        <button onClick={onCancel} className="text-sm" style={{ color: "var(--text-muted)" }}>← Back</button>
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Set up {game.name}</span>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {step === 0 && (
          <div className="flex flex-col gap-5" style={{ maxWidth: 420 }}>
            <div>
              <img src={game.icon} alt={game.name} className="w-10 h-10 mb-2 rounded-lg object-contain" />
              <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>{game.name}</h2>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Point to where your save files are stored.</p>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Save Directory</label>
              <div className="flex gap-2">
                <input type="text" value={savePath} onChange={(e) => setSavePath(e.target.value)} style={inputStyle} />
                <button onClick={browsePath} className="shrink-0 px-3 rounded-lg text-xs" style={{ ...btnOutline, width: "auto", padding: "0 14px" }}>Browse</button>
              </div>
            </div>
            {needsPlaythroughSelection ? (
              <button onClick={async () => { await scanPlaythroughs(); setStep(1); }} disabled={!savePath} style={{ ...btnPrimary, opacity: !savePath ? 0.5 : 1 }}>Scan for Playthroughs</button>
            ) : (
              <button onClick={finish} disabled={!savePath} style={{ ...btnPrimary, opacity: !savePath ? 0.5 : 1 }}>Enable Watching</button>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="flex flex-col gap-5" style={{ maxWidth: 420 }}>
            <div>
              <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>Select Playthrough</h2>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Choose which playthrough to track.</p>
            </div>

            {scanning ? (
              <div className="text-sm" style={{ color: "var(--text-muted)" }}>Scanning...</div>
            ) : playthroughs.length > 0 ? (
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => setSelectedPlaythrough("")}
                  className="w-full text-left px-4 py-3 rounded-lg"
                  style={{ background: selectedPlaythrough === "" ? "var(--accent-dim)" : "var(--bg-secondary)", border: `1px solid ${selectedPlaythrough === "" ? "var(--accent)" : "var(--border-color)"}`, borderColor: selectedPlaythrough === "" ? "rgba(124,92,252,0.3)" : "var(--border-color)" }}
                >
                  <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>All playthroughs</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>Track most recently modified save</div>
                </button>
                {playthroughs.map((pt) => (
                  <button
                    key={pt}
                    onClick={() => setSelectedPlaythrough(pt)}
                    className="w-full text-left px-4 py-3 rounded-lg"
                    style={{ background: selectedPlaythrough === pt ? "var(--accent-dim)" : "var(--bg-secondary)", border: `1px solid ${selectedPlaythrough === pt ? "var(--accent)" : "var(--border-color)"}`, borderColor: selectedPlaythrough === pt ? "rgba(124,92,252,0.3)" : "var(--border-color)" }}
                  >
                    <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{pt}</div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-sm" style={{ color: "var(--text-muted)" }}>No playthroughs found. Directory will be watched for new saves.</div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setStep(0)} style={btnOutline}>Back</button>
              <button onClick={finish} style={btnPrimary}>Enable Watching</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
