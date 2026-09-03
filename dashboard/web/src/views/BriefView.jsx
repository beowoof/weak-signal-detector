import { number } from "../lib/format.js";

function daysBetween(start, end) {
  if (!start || !end) return [];
  const days = [];
  const cursor = new Date(`${start}T00:00:00Z`);
  const last = new Date(`${end}T00:00:00Z`);
  while (cursor <= last) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

function parseCell(item) {
  const text = item?.text || "";
  const quality = /quality=(\w+)/.exec(text)?.[1] || (item?.kind === "coverage_hole" ? "missing" : "ok");
  const raw = /raw=([^;]+)/.exec(text)?.[1];
  const z = /z=([^;]+)/.exec(text)?.[1];
  return { quality, raw, z };
}

function Status({ value }) {
  const label = value || "unknown";
  return <span className={`brief-status brief-status-${label}`}>{label.replaceAll("_", " ")}</span>;
}

function Cell({ cell }) {
  if (!cell) return <td className="brief-cell-empty">—</td>;
  return (
    <td className={`brief-cell brief-cell-${cell.quality}`}>
      <span className="brief-cell-value">{cell.raw ?? "—"}</span>
      {cell.z ? <span className="brief-cell-z">z {Number.parseFloat(cell.z).toFixed(2)}</span> : null}
      <Status value={cell.quality} />
    </td>
  );
}

function SimpleTable({ columns, rows, rowClass }) {
  return (
    <div className="brief-table-wrap">
      <table className="brief-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.key || index} className={rowClass?.(row, index)}>
              {row.cells.map((cell, cellIndex) =>
                cell?.td ? (
                  cell.td
                ) : (
                  <td key={cellIndex} className={cell.className}>
                    {cell.node ?? cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const COLLECT_FOR = [
  { prefix: "Physical", kind: "refresh_physical", ready: true },
  { prefix: "Official", kind: "official_pack", ready: true },
  { prefix: "Financial", kind: null, ready: false },
  { prefix: "Information", kind: null, ready: false },
];

export default function BriefView({ packet, notice, onCollect, collectBusy }) {
  if (!packet) {
    return (
      <section className="brief-layers">
        <h3>Brief</h3>
        <p className="notice-timing">No brief yet. Use Build brief on this alert.</p>
      </section>
    );
  }

  const trigger = notice?.trigger || packet.measurement_snapshot || {};
  const start = trigger.start;
  const end = trigger.end;
  const days = daysBetween(start, end);
  const contributing = new Set(trigger.contributing_series || []);
  const bySeries = {};
  for (const item of packet.collected_evidence || []) {
    const day = (item.evidence_time || "").slice(0, 10);
    if (!item.series_id || !day) continue;
    bySeries[item.series_id] ||= {};
    bySeries[item.series_id][day] = parseCell(item);
  }
  const seriesIds = [
    ...[...contributing],
    ...Object.keys(bySeries)
      .filter((id) => !contributing.has(id))
      .sort(),
  ];
  const wikiDim = (packet.information_environment?.dimensions || []).find(
    (dim) => dim.id === "geographic_focus",
  );
  const volumeDim = (packet.information_environment?.dimensions || []).find(
    (dim) => dim.id === "reporting_volume",
  );
  const missingDims = (packet.information_environment?.dimensions || []).filter(
    (dim) => dim.status === "missing",
  );
  const wikiTitles = [
    ...new Set(
      (wikiDim?.values || []).flatMap((row) => Object.keys(row.titles || {})),
    ),
  ];
  const nav = (packet.geopolitical_context?.items || []).find(
    (item) => item.series_id === "nav.spatial_warnings",
  );
  const quiet = (packet.brief || []).find((section) => section.id === "quiet_or_unavailable");
  const cannot = (packet.brief || []).find((section) => section.id === "cannot_support");
  const holes = (packet.brief || []).find((section) => section.id === "unknowns");
  const holeLines = (holes?.body || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const holeRows = [];
  const holeNotes = [];
  for (const line of holeLines) {
    const match = /^(\S+)\s+(\d{4}-\d{2}-\d{2})\s+quality=(\w+)/.exec(line);
    if (!match) {
      holeNotes.push(line);
      continue;
    }
    holeRows.push({
      key: line,
      cells: [match[1], match[2], { node: <Status value={match[3]} /> }],
    });
  }

  const product = packet.product;
  if (!product) {
    return (
      <section className="brief-layers">
        <p className="notice-timing">Rebuild the brief to get the intelligence product view.</p>
      </section>
    );
  }

  return (
    <section className="brief-layers">
      <header className="product-hero">
        <p className="eyebrow">{product.analytic_state_label}</p>
        <h3>{product.headline}</h3>
        <p className="product-meta">
          {product.period} · available by {product.available_by}
        </p>
        <div className="brief-pills">
          <span className={`brief-pill brief-pill-state brief-pill-${product.analytic_state}`}>
            {product.analytic_state_label}
          </span>
          <span className="brief-pill">AnCR: {product.confidence}</span>
          <span className="brief-pill brief-pill-proxy">{product.change}</span>
        </div>
        {(product.keys || []).length ? (
          <div className="brief-pills">
            {product.keys.map((key) => (
              <span key={key} className="brief-pill">
                {key}
              </span>
            ))}
          </div>
        ) : null}
      </header>

      {(product.availability_warnings || []).map((warning) => (
        <div key={warning} className="brief-callout brief-callout-warn">
          <strong>{warning}</strong>
        </div>
      ))}

      <div className="brief-card">
        <h3>Assessment</h3>
        {(product.assessment || []).map((para) => (
          <p key={para}>{para}</p>
        ))}
        <dl className="product-meta-list">
          <div>
            <dt>Analytic state</dt>
            <dd>{product.analytic_state_label}</dd>
          </div>
          <div>
            <dt>Analytical confidence (AnCR)</dt>
            <dd>{product.confidence}</dd>
          </div>
          <div>
            <dt>Change since previous period</dt>
            <dd>{product.change}</dd>
          </div>
        </dl>
        {product.confidence_rationale ? (
          <p className="notice-timing">{product.confidence_rationale}</p>
        ) : null}
      </div>

      <div className="brief-card">
        <h3>Why this is on the watchlist</h3>
        <div className="brief-table-wrap">
          <table className="brief-table">
            <thead>
              <tr>
                <th>Indicator</th>
                <th>Observation</th>
                <th>Analytic significance</th>
              </tr>
            </thead>
            <tbody>
              {(product.watchlist || []).map((row) => (
                <tr key={row.indicator}>
                  <th>{row.indicator}</th>
                  <td>{row.observation}</td>
                  <td>{row.implication}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="notice-timing">
          The important feature is co-movement across otherwise distinct domains, rather than any
          single decisive indicator.
        </p>
        {(product.caveats || []).map((caveat) => (
          <p key={caveat} className="notice-timing">
            {caveat}
          </p>
        ))}
      </div>

      <div className="brief-card">
        <h3>Competing explanations</h3>
        <p className="notice-timing">
          Likelihoods use the PHIA Probability Yardstick. What would discriminate is the collection
          requirement.
        </p>
        <div className="brief-table-wrap">
          <table className="brief-table">
            <thead>
              <tr>
                <th>Hypothesis</th>
                <th>Likelihood</th>
                <th>What would discriminate</th>
              </tr>
            </thead>
            <tbody>
              {(product.hypotheses || []).map((row) => (
                <tr key={row.hypothesis}>
                  <td>{row.hypothesis}</td>
                  <td>
                    <span
                      className={`fit-chip fit-${row.fit.toLowerCase().replaceAll("/", "-").replaceAll(" ", "-")}`}
                    >
                      {row.fit}
                    </span>
                  </td>
                  <td>{row.discriminate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="brief-card">
        <h3>Collection requirements</h3>
        <ol className="product-collection">
          {(product.collection || []).map((row) => {
            const match = COLLECT_FOR.find((item) => row.title.startsWith(item.prefix));
            const ready = Boolean(onCollect && match?.ready && match.kind);
            return (
              <li key={row.title}>
                <strong>{row.title}.</strong> {row.why}{" "}
                {match ? (
                  <button
                    type="button"
                    className="collect-inline"
                    disabled={!ready || collectBusy}
                    title={
                      ready
                        ? "Run this collection job"
                        : "Not wired yet — no collection job for this requirement"
                    }
                    onClick={() => {
                      if (ready) onCollect(match.kind);
                    }}
                  >
                    {match.ready ? "Run" : "Not wired"}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ol>
      </div>

      <div className="brief-card">
        <h3>Analyst note</h3>
        <p>{product.analyst_note}</p>
      </div>

      <details className="brief-audit">
        <summary>Evidence and provenance</summary>
        <p className="notice-timing">
          Series values, reconstructed latency, missingness, and shared-substrate notes.
        </p>

      {quiet?.body ? (
        <div className="brief-callout brief-callout-warn">
          <strong>Not yet knowable / quiet</strong>
          <ul>
            {quiet.body
              .split(/(?<=\.)\s+/)
              .filter(Boolean)
              .map((line) => (
                <li key={line}>{line}</li>
              ))}
          </ul>
        </div>
      ) : null}

      <div className="brief-card">
      <h3>What moved</h3>
      <p className="notice-timing">Knowable at cutoff. Green edge = chorus series.</p>
      <div className="brief-table-wrap">
        <table className="brief-table">
          <thead>
            <tr>
              <th>Series</th>
              {days.map((day) => (
                <th key={day}>{day.slice(5)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {seriesIds.map((id) => (
              <tr key={id} className={contributing.has(id) ? "brief-row-chorus" : undefined}>
                <th>
                  {id}
                  {contributing.has(id) ? <Status value="chorus" /> : null}
                </th>
                {days.map((day) => (
                  <Cell key={day} cell={bySeries[id]?.[day]} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      <div className="brief-card">
      <h3>Information environment</h3>
      <p className="notice-timing">
        {(packet.information_environment?.notes || [])[0] || "Information environment."}
      </p>
      {volumeDim?.values?.length ? (
        <>
          <h4>
            Reporting volume <Status value={volumeDim.status} />
          </h4>
          <p className="notice-timing">{volumeDim.summary}</p>
          <div className="brief-table-wrap">
            <table className="brief-table">
              <thead>
                <tr>
                  <th>Day</th>
                  <th>GDELT count</th>
                  <th>ICEWS count</th>
                </tr>
              </thead>
              <tbody>
                {days.map((day) => (
                  <tr key={day}>
                    <td>{day}</td>
                    <td>{number(volumeDim.values.find((row) => row.day === day)?.count)}</td>
                    <td>{bySeries["talk.icews_cameo"]?.[day]?.raw ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="notice-timing">
            ICEWS and GDELT share the public-reporting substrate. Divergence is not independent
            corroboration.
          </p>
        </>
      ) : null}
      {wikiDim?.values?.length ? (
        <>
          <h4>
            Geographic focus <Status value={wikiDim.status} />
          </h4>
          <p className="notice-timing">{wikiDim.summary}</p>
          <div className="brief-table-wrap">
            <table className="brief-table">
              <thead>
                <tr>
                  <th>Day</th>
                  {wikiTitles.map((title) => (
                    <th key={title}>{title}</th>
                  ))}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {wikiDim.values.map((row) => (
                  <tr key={row.day}>
                    <td>{row.day}</td>
                    {wikiTitles.map((title) => (
                      <td key={title}>{number(row.titles?.[title]?.views)}</td>
                    ))}
                    <td>{number(row.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      <div className="brief-table-wrap">
        <table className="brief-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Status</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {missingDims.map((dim) => (
              <tr key={dim.id} className="brief-row-missing">
                <td>{dim.id.replaceAll("_", " ")}</td>
                <td>
                  <Status value={dim.status} />
                </td>
                <td>{dim.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      <div className="brief-card">
      <h3>Geopolitical / official context</h3>
      {(packet.geopolitical_context?.notes || []).map((note) => (
        <p key={note} className="notice-timing">
          {note}
        </p>
      ))}
      {nav?.values?.length ? (
        <div className="brief-table-wrap">
          <table className="brief-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>NAVAREA warnings</th>
              </tr>
            </thead>
            <tbody>
              {nav.values.map((row) => (
                <tr key={row.day}>
                  <td>{row.day}</td>
                  <td>{number(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="brief-callout">No official-statement or RIMA harvest in this collection.</div>
      )}
      </div>

      <div className="brief-card">
      <h3>Dependencies</h3>
      <div className="brief-pills">
        {(packet.dependencies || []).map((dep) => (
          <span key={dep.shared_information_substrate} className="brief-pill brief-pill-proxy">
            {(dep.series || []).join(" + ")} → {dep.shared_information_substrate}
          </span>
        ))}
      </div>
      {(packet.dependencies || []).map((dep) => (
        <p key={`${dep.shared_information_substrate}-note`} className="notice-timing">
          {dep.caution}
        </p>
      ))}
      </div>

      <div className="brief-card">
      <h3>Unknowns and holes</h3>
      {holeRows.length ? (
        <SimpleTable columns={["Series", "Day", "Quality"]} rows={holeRows} />
      ) : (
        <p className="notice-timing">No coverage holes among knowable days.</p>
      )}
      {holeNotes.map((note) => (
        <p key={note} className="notice-timing">
          {note}
        </p>
      ))}
      </div>

      <div className="brief-card">
      <h3>Hypotheses (unassessed)</h3>
      <div className="brief-pills">
        {(packet.hypotheses || []).map((item) => (
          <span key={item.hypothesis} className="brief-pill">
            {item.hypothesis.replaceAll("_", " ")}
          </span>
        ))}
      </div>
      </div>

      {cannot?.body ? (
        <div className="brief-callout">
          <strong>{cannot.title || "Methodological limits"}</strong>
          <p>{cannot.body}</p>
        </div>
      ) : null}
      </details>
    </section>
  );
}
