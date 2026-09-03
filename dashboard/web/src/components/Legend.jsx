export default function Legend({ items, interactive = false, visible, onToggle }) {
  return (
    <div className="legend">
      {items.map((item) => {
        const pressed = !interactive || visible?.has(item.id);
        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={String(pressed)}
            onClick={interactive ? () => onToggle?.(item.id) : undefined}
          >
            <span className="swatch" style={{ "--swatch": item.color }} />
            {item.id}
          </button>
        );
      })}
    </div>
  );
}
