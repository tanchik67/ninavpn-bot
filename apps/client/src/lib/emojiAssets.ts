import type { ImageSourcePropType } from "react-native";

/** Local Apple-style PNGs (emoji-datasource-apple 64px). Keys = unified hex. */
export const EMOJI_ASSETS: Record<string, ImageSourcePropType> = {
  "1f60e": require("../../assets/emojis/1f60e.png"),
  "1f525": require("../../assets/emojis/1f525.png"),
  "2728": require("../../assets/emojis/2728.png"),
  "1f49c": require("../../assets/emojis/1f49c.png"),
  "1f680": require("../../assets/emojis/1f680.png"),
  "2b50": require("../../assets/emojis/2b50.png"),
  "1f48e": require("../../assets/emojis/1f48e.png"),
  "1f3af": require("../../assets/emojis/1f3af.png"),
  "1f98a": require("../../assets/emojis/1f98a.png"),
  "1f431": require("../../assets/emojis/1f431.png"),
  "1f43c": require("../../assets/emojis/1f43c.png"),
  "1f981": require("../../assets/emojis/1f981.png"),
  "1f30a": require("../../assets/emojis/1f30a.png"),
  "1f319": require("../../assets/emojis/1f319.png"),
  "2600-fe0f": require("../../assets/emojis/2600-fe0f.png"),
  "26a1": require("../../assets/emojis/26a1.png"),
  "26a1-fe0f": require("../../assets/emojis/26a1-fe0f.png"),
  "1f3ae": require("../../assets/emojis/1f3ae.png"),
  "1f3a7": require("../../assets/emojis/1f3a7.png"),
  "1f355": require("../../assets/emojis/1f355.png"),
  "1f369": require("../../assets/emojis/1f369.png"),
  "1f308": require("../../assets/emojis/1f308.png"),
  "1f340": require("../../assets/emojis/1f340.png"),
  "1f6e1-fe0f": require("../../assets/emojis/1f6e1-fe0f.png"),
  "1f451": require("../../assets/emojis/1f451.png"),
  "1f47b": require("../../assets/emojis/1f47b.png"),
  "1f916": require("../../assets/emojis/1f916.png"),
  "1f31f": require("../../assets/emojis/1f31f.png"),
  "1f4ab": require("../../assets/emojis/1f4ab.png"),
  "1f98b": require("../../assets/emojis/1f98b.png"),
  "1f984": require("../../assets/emojis/1f984.png"),
  "1f3e0": require("../../assets/emojis/1f3e0.png"),
  "1f464": require("../../assets/emojis/1f464.png"),
  "2699-fe0f": require("../../assets/emojis/2699-fe0f.png"),
  "270f-fe0f": require("../../assets/emojis/270f-fe0f.png"),
  "1f4ac": require("../../assets/emojis/1f4ac.png"),
};

export function emojiToUnified(emoji: string): string {
  return Array.from(emoji)
    .map((ch) => ch.codePointAt(0)!.toString(16))
    .join("-");
}

export function resolveEmojiAsset(emoji: string): ImageSourcePropType | null {
  if (!emoji) return null;
  const full = emojiToUnified(emoji);
  const noVs = full.replace(/-fe0f/g, "");
  return EMOJI_ASSETS[full] || EMOJI_ASSETS[noVs] || EMOJI_ASSETS[`${noVs}-fe0f`] || null;
}
