import { type RefObject, useEffect } from "react";

/**
 * Phones: tables marked `className="cards"` are shown as one card per row (CSS), each value
 * preceded by its column title. This copies the <th> titles onto the cells (`data-label`) and
 * keeps them up to date when the table content changes (auto-refresh, filters, pages).
 */
export function useCardLabels(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const label = () => {
      element.querySelectorAll<HTMLTableElement>("table.cards").forEach((table) => {
        const titles = Array.from(table.tHead?.rows[0]?.cells ?? []).map((cell) => cell.textContent?.trim() ?? "");
        Array.from(table.tBodies).forEach((body) =>
          Array.from(body.rows).forEach((row) => {
            if (row.cells.length === 1 && row.cells[0].colSpan > 1) return; // detail row spanning the table
            Array.from(row.cells).forEach((cell, index) => {
              const title = titles[index] ?? "";
              if (cell.dataset.label !== title) cell.dataset.label = title;
            });
          }),
        );
      });
    };
    label();
    const observer = new MutationObserver(label);
    observer.observe(element, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [root]);
}
