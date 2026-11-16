import { useCallback, useState } from "react";
import { safeStorage } from "../../lib/storage";

const KEY = "bhh.checkpoint";

/** The gate the agent covers. Chosen once per shift, remembered across reloads. */
export function useSelectedCheckpoint() {
  const [id, setId] = useState<number | null>(() => {
    const stored = safeStorage.get(KEY);
    return stored ? Number(stored) : null;
  });

  const select = useCallback((value: number) => {
    safeStorage.set(KEY, String(value));
    setId(value);
  }, []);

  const clear = useCallback(() => {
    safeStorage.remove(KEY);
    setId(null);
  }, []);

  return { checkpointId: id, select, clear };
}
