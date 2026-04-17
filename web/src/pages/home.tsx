import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUsers } from "@/lib/api";
import type { User } from "@/lib/types";
import { getThemeStyle } from "@/lib/theme";

export default function HomePage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">Loading...</div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="text-5xl">📜</div>
        <h1 className="text-2xl font-semibold">No adventurers yet</h1>
        <p className="text-muted-foreground text-center max-w-md">
          Start the scraper on your gaming PC and sync your first save file.
          Users are created automatically when data is synced.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Choose your adventurer</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {users.map((user) => (
          <UserCard key={user.id} user={user} />
        ))}
      </div>
    </div>
  );
}

function UserCard({ user }: { user: User }) {
  // Card themed by the user's last-played game so the hover trace + avatar
  // ring pick up that game's colour. Falls back to default purple.
  const themeStyle = getThemeStyle(user.last_game_slug);

  return (
    <Link to={`/${user.username}`} style={themeStyle}>
      <div className="group relative overflow-hidden rounded-xl ring-1 ring-foreground/10 transition-all cursor-pointer">
        {/* Background art */}
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
          style={
            user.last_game_slug
              ? { backgroundImage: `url(/backgrounds/${user.last_game_slug}.jpg)` }
              : undefined
          }
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/65 to-black/30" />

        {/* Traced ring */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
          aria-hidden
        >
          <rect
            x="0" y="0"
            width="100%" height="100%"
            rx="12" ry="12"
            fill="none"
            stroke="var(--primary)"
            strokeWidth="2"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset="1"
            vectorEffect="non-scaling-stroke"
            className="transition-[stroke-dashoffset] duration-[800ms] ease-out group-hover:[stroke-dashoffset:0]"
          />
        </svg>

        <div className="relative flex items-end gap-4 p-6 min-h-[140px]">
          <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-xl font-bold text-white shrink-0 ring-1 ring-white/20 group-hover:ring-primary/70 group-hover:shadow-[0_0_18px_-2px_var(--primary)] transition-all duration-300" style={{ fontFamily: "'Orbitron', sans-serif" }}>
            {user.username[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-lg text-white truncate" style={{ fontFamily: "'Orbitron', sans-serif" }}>
              {user.username}
            </div>
            {user.last_game_name ? (
              <div className="text-sm text-white/70 truncate">
                Last played {user.last_game_name}
              </div>
            ) : (
              <div className="text-sm text-white/50">
                Joined {new Date(user.created_at).toLocaleDateString()}
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
