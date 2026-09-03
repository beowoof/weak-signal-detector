export default function ChartSection({ title, note, children, focused = false }) {
  return (
    <section className={`chart-block${focused ? " chart-block-focus" : ""}`}>
      <div className="chart-header">
        <h2>{title}</h2>
        {note ? <p>{note}</p> : null}
      </div>
      {children}
    </section>
  );
}
