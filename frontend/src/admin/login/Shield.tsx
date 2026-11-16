/** Decorative glass shield for the login page (original artwork, bordeaux tones). */
export function Shield() {
  const outline = "M150 8 L282 54 V172 C282 250 222 310 150 352 C78 310 18 250 18 172 V54 Z";
  const inner = "M150 36 L256 72 V170 C256 232 208 282 150 316 C92 282 44 232 44 170 V72 Z";
  return (
    <svg viewBox="0 0 300 420" role="presentation" focusable="false">
      <defs>
        <linearGradient id="sh-left" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f3c3cf" stopOpacity=".95" />
          <stop offset="1" stopColor="#b3566f" stopOpacity=".75" />
        </linearGradient>
        <linearGradient id="sh-right" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#b3566f" stopOpacity=".7" />
          <stop offset="1" stopColor="#5a1428" stopOpacity=".85" />
        </linearGradient>
        <linearGradient id="sh-rim" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffe3ea" />
          <stop offset="1" stopColor="#8b2c47" />
        </linearGradient>
        <linearGradient id="sh-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity=".28" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <mask id="sh-mask"><rect x="0" y="0" width="300" height="420" fill="url(#sh-fade)" /></mask>
        <clipPath id="sh-clip-l"><rect x="0" y="0" width="150" height="360" /></clipPath>
        <clipPath id="sh-clip-r"><rect x="150" y="0" width="150" height="360" /></clipPath>
      </defs>

      <g>
        <path d={outline} fill="url(#sh-rim)" />
        <path d={inner} fill="url(#sh-left)" clipPath="url(#sh-clip-l)" />
        <path d={inner} fill="url(#sh-right)" clipPath="url(#sh-clip-r)" />
        <path d="M150 36 L256 72 V120 C220 96 190 70 150 36 Z" fill="#fff" opacity=".18" />
        <path d={inner} fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="2" />
        <line x1="150" y1="36" x2="150" y2="316" stroke="#fff" strokeOpacity=".35" strokeWidth="1.5" />
      </g>
      {/* soft reflection under the shield */}
      <g transform="translate(0 712) scale(1 -1)" mask="url(#sh-mask)" opacity=".9">
        <path d={outline} fill="url(#sh-rim)" />
        <path d={inner} fill="url(#sh-right)" />
      </g>
    </svg>
  );
}
