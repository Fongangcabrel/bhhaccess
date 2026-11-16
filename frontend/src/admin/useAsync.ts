import { tx } from "../i18n";
import { useCallback, useEffect, useRef, useState } from "react";

/** Load data on mount / when deps change; `reload()` refetches after a mutation. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(() => {
    setLoading(true);
    return loadRef
      .current()
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => void reload(), deps);

  return { data, error, loading, reload };
}

/** Run a mutation, surface its error, then refresh. */
export function useAction(onError: (message: string) => void) {
  return useCallback(
    async (run: () => Promise<unknown>, after?: () => void) => {
      try {
        await run();
        after?.();
      } catch (e) {
        onError(e instanceof Error ? e.message : tx("Erreur inconnue"));
      }
    },
    [onError],
  );
}
