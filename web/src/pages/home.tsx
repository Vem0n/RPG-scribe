import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUsers } from "@/lib/api";
import type { User } from "@/lib/types";

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
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading...</div>
      </div>
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
          <Link key={user.id} to={`/${user.username}`}>
            <div className="group relative overflow-hidden rounded-xl ring-1 ring-foreground/10 hover:ring-foreground/20 transition-all cursor-pointer">
              {/* Background art */}
              <div
                className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
                style={
                  user.last_game_slug
                    ? { backgroundImage: `url(/backgrounds/${user.last_game_slug}.jpg)` }
                    : undefined
                }
              />
              {/* Dark gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/60 to-black/30" />

              {/* Content */}
              <div className="relative flex items-end gap-4 p-6 min-h-[140px]">
                <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-xl font-bold text-white shrink-0 ring-1 ring-white/20">
                  {user.username[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-lg text-white truncate">
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
        ))}
      </div>
    </div>
  );
}
