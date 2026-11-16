import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { ADMIN_EN } from "../i18n/admin";

const SRC = join(__dirname, "..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "__tests__" ? [] : sources(path);
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

/** Every tx("…") of the code, read from the sources themselves. */
function usedKeys(): Set<string> {
  const keys = new Set<string>();
  for (const file of sources(SRC)) {
    for (const match of readFileSync(file, "utf8").matchAll(/\btx\(("(?:[^"\\]|\\.)*")/g)) {
      keys.add(JSON.parse(match[1]) as string);
    }
  }
  return keys;
}

describe("back-office in English", () => {
  it("has an English text for every French text shown", () => {
    const missing = [...usedKeys()].filter((key) => !(key in ADMIN_EN));
    expect(missing).toEqual([]);
  });

  it("keeps the placeholders of each text", () => {
    const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
    const broken = Object.entries(ADMIN_EN).filter(([fr, en]) => placeholders(fr) !== placeholders(en));
    expect(broken).toEqual([]);
  });
});
