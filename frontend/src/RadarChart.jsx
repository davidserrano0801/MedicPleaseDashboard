// Gráfico radial (radar) en SVG puro, sin librerías.
// axes:   [{ label }]
// series: [{ name, color, values: [número 0..max | null] }]
export default function RadarChart({ axes, series, max = 100 }) {
  const w = 480;
  const h = 360;
  const cx = w / 2;
  const cy = h / 2 + 4;
  const r = 120;
  const n = axes.length;

  const angle = i => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const point = (i, value) => {
    const radius = (r * Math.max(0, Math.min(value, max))) / max;
    return [cx + radius * Math.cos(angle(i)), cy + radius * Math.sin(angle(i))];
  };
  const polygon = values => values.map((v, i) => point(i, v ?? 0).join(",")).join(" ");
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <svg className="radar" viewBox={`0 0 ${w} ${h}`} role="img"
         aria-label={`Gráfico radial: ${axes.map(a => a.label).join(", ")}`}>
      {rings.map(f => (
        <polygon key={f} className="radar-ring"
                 points={polygon(axes.map(() => max * f))} />
      ))}
      {axes.map((a, i) => {
        const [x, y] = point(i, max);
        return <line key={a.label} className="radar-axis" x1={cx} y1={cy} x2={x} y2={y} />;
      })}
      {rings.map(f => (
        <text key={f} className="radar-scale" x={cx + 4} y={cy - r * f + 11}>
          {Math.round(max * f)}
        </text>
      ))}

      {series.map(s => (
        <g key={s.name}>
          <polygon points={polygon(s.values)} fill={s.color} fillOpacity="0.22"
                   stroke={s.color} strokeWidth="2" strokeLinejoin="round" />
          {s.values.map((v, i) => {
            const [x, y] = point(i, v ?? 0);
            return (
              <circle key={i} cx={x} cy={y} r="4" fill={s.color}>
                <title>{`${s.name} · ${axes[i].label}: ${v === null || v === undefined ? "sin datos" : v + "%"}`}</title>
              </circle>
            );
          })}
        </g>
      ))}

      {axes.map((a, i) => {
        const cos = Math.cos(angle(i));
        const sin = Math.sin(angle(i));
        const lx = cx + (r + 16) * cos;
        const ly = cy + (r + 16) * sin + (sin < -0.3 ? -4 : sin > 0.3 ? 12 : 4);
        const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
        return (
          <text key={a.label} className="radar-label" x={lx} y={ly} textAnchor={anchor}>
            {a.label}
          </text>
        );
      })}
    </svg>
  );
}
