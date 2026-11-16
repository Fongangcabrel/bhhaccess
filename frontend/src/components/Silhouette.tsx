/** Neutral placeholder shown when an employee has no photo ("Photo absente"). */
export function Silhouette() {
  return (
    <svg viewBox="0 0 60 80" aria-hidden="true">
      <circle cx="30" cy="28" r="14" />
      <path d="M4 80c0-17 11.6-28 26-28s26 11 26 28z" />
    </svg>
  );
}
