import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import HomePage from "./pages/home";
import UserPage from "./pages/user";
import PlaythroughPage from "./pages/playthrough";
import { useQuestEvents } from "./lib/useQuestEvents";

function useWindowFocused() {
  const [focused, setFocused] = useState(document.hasFocus());
  useEffect(() => {
    const onFocus = () => setFocused(true);
    const onBlur = () => setFocused(false);
    window.addEventListener("focus", onFocus);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("blur", onBlur);
    };
  }, []);
  return focused;
}

function FocusAwareToaster() {
  const focused = useWindowFocused();
  return <Toaster theme="dark" position="bottom-right" richColors expand={!focused} visibleToasts={9} />;
}

function EventListener() {
  useQuestEvents();
  return null;
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col dark text-foreground">
      <header className="relative z-20 border-b border-white/5 bg-black/30 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-3">
          <a href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-6 h-6 text-primary"
            >
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
              <path d="M8 7h6" />
              <path d="M8 11h8" />
            </svg>
            <span className="text-lg font-semibold tracking-wider" style={{ fontFamily: "'Orbitron', sans-serif" }}>
              RPG Scribe
            </span>
          </a>
        </div>
      </header>
      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-4 py-8">{children}</div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <FocusAwareToaster />
      <EventListener />
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/:username" element={<UserPage />} />
          <Route
            path="/:username/:playthroughId"
            element={<PlaythroughPage />}
          />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
