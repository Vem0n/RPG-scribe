import iconCyberpunk from "./assets/games/cyberpunk2077.png";
import iconDAO from "./assets/games/dragon_age_origins.png";
import iconFNV from "./assets/games/fallout_new_vegas.png";
import iconKOTOR from "./assets/games/kotor.png";

export interface GameConfig {
  id: string;
  name: string;
  slug: string;
  icon: string;
  defaultSavePaths: string[];
  /** How saves are organized */
  saveStructure: "folder-per-save" | "files-in-dir" | "folder-per-character";
  /** Which file extensions to watch */
  watchPatterns: string[];
  /** Script path relative to project root */
  scraperScript: string;
  /** How to detect playthroughs from the save directory */
  playthroughDetection: "save-folders" | "character-folders" | "single";
}

export const SUPPORTED_GAMES: GameConfig[] = [
  {
    id: "cyberpunk2077",
    name: "Cyberpunk 2077",
    slug: "cyberpunk2077",
    icon: iconCyberpunk,
    defaultSavePaths: [
      "%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077",
    ],
    saveStructure: "folder-per-save",
    watchPatterns: ["*.dat", "metadata.*.json"],
    scraperScript: "scraper/cp2077/extract.py",
    playthroughDetection: "save-folders",
  },
  {
    id: "dragon_age_origins",
    name: "Dragon Age: Origins",
    slug: "dragon_age_origins",
    icon: iconDAO,
    defaultSavePaths: [
      "%USERPROFILE%/Documents/BioWare/Dragon Age/Characters",
    ],
    saveStructure: "folder-per-character",
    watchPatterns: ["*.das"],
    scraperScript: "scraper/dao/extract.py",
    playthroughDetection: "character-folders",
  },
  {
    id: "fallout_new_vegas",
    name: "Fallout: New Vegas",
    slug: "fallout_new_vegas",
    icon: iconFNV,
    defaultSavePaths: [
      "%USERPROFILE%/Documents/my games/FalloutNV/Saves",
    ],
    saveStructure: "files-in-dir",
    watchPatterns: ["*.fos"],
    scraperScript: "scraper/fnv/extract.py",
    playthroughDetection: "save-folders",
  },
  {
    id: "kotor",
    name: "Star Wars: KOTOR",
    slug: "kotor",
    icon: iconKOTOR,
    defaultSavePaths: [
      "C:/Program Files (x86)/Steam/steamapps/common/swkotor/Saves",
    ],
    saveStructure: "folder-per-save",
    watchPatterns: ["GLOBALVARS.res", "PARTYTABLE.res"],
    scraperScript: "scraper/kotor/extract.py",
    playthroughDetection: "save-folders",
  },
];

export async function expandPath(path: string): Promise<string> {
  try {
    const { homeDir } = await import("@tauri-apps/api/path");
    const home = (await homeDir()).replace(/\\/g, "/").replace(/\/$/, "");
    return path.replace("%USERPROFILE%", home);
  } catch {
    return path;
  }
}
