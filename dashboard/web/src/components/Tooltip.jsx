export default function Tooltip({ tooltip }) {
  if (!tooltip) return null;
  return (
    <div className="tooltip" style={{ left: Math.max(8, tooltip.x), top: Math.max(8, tooltip.y) }}>
      <strong>{tooltip.title}</strong>
      {(tooltip.rows || []).map(([left, right]) => (
        <div className="tooltip-row" key={`${left}-${right}`}>
          <span>{left}</span>
          <span>{right}</span>
        </div>
      ))}
    </div>
  );
}
