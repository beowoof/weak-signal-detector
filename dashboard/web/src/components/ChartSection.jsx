export default function ChartSection({ title, note, children }) {
  return (
    <section className="chart-block">
      <div className="chart-header">
        <h2>{title}</h2>
        {note ? <p>{note}</p> : null}
      </div>
      {children}
    </section>
  );
}
