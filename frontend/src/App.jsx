import { useCallback, useEffect, useState } from "react";

const REFRESH_MS = 15000;

const fmt = (value, suffix = "") =>
  value === null || value === undefined ? "—" : `${value}${suffix}`;

function Card({ label, value, hint }) {
  return (
    <div className="card">
      <span className="card-label">{label}</span>
      <strong className="card-value">{value}</strong>
      {hint && <span className="card-hint">{hint}</span>}
    </div>
  );
}

function Bars({ rows, labelKey, valueKey, max, suffix = "", wide = false, badge }) {
  const top = max ?? Math.max(1, ...rows.map(r => r[valueKey] ?? 0));
  return (
    <div className={`bars ${wide ? "wide-labels" : ""}`}>
      {rows.map(row => {
        const value = row[valueKey];
        const width = value === null || value === undefined ? 0 : (value / top) * 100;
        return (
          <div className="bar-row" key={row[labelKey]}>
            <span className="bar-label">
              {row[labelKey]}
              {badge && badge(row)}
            </span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${width}%` }} />
            </div>
            <span className="bar-value">{fmt(value, suffix)}</span>
          </div>
        );
      })}
    </div>
  );
}

function RelevanceBadge({ relevant }) {
  if (relevant === null || relevant === undefined) return null;
  return relevant
    ? <span className="badge ok">relevante</span>
    : <span className="badge no">no relevante</span>;
}

function RelevancePie({ relevant, notRelevant }) {
  const total = relevant + notRelevant;
  if (total === 0) return null;
  const relPct = (relevant / total) * 100;
  const notPct = 100 - relPct;
  return (
    <div className="pie-wrap">
      <div
        className="pie"
        role="img"
        aria-label={`${relevant} decisiones relevantes y ${notRelevant} no relevantes`}
        style={{
          background: `conic-gradient(#22c55e 0 ${relPct}%, #ef4444 ${relPct}% 100%)`,
        }}
      />
      <ul className="pie-legend">
        <li>
          <span className="swatch ok" />
          Relevantes: <strong>{relevant}</strong> ({relPct.toFixed(1)}%)
        </li>
        <li>
          <span className="swatch no" />
          No relevantes: <strong>{notRelevant}</strong> ({notPct.toFixed(1)}%)
        </li>
      </ul>
    </div>
  );
}

function PlayerDetail({ name, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    fetch(`/api/players/${encodeURIComponent(name)}/`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error("No se pudo cargar el jugador"))))
      .then(setData)
      .catch(e => setError(e.message));
  }, [name]);

  const relevantSet = data?.relevantDecisionsMade ? new Set(data.relevantDecisionsMade) : null;
  const relevantCount = relevantSet
    ? data.decisionsMade.filter(d => relevantSet.has(d)).length
    : 0;
  const notRelevantCount = relevantSet ? data.decisionsMade.length - relevantCount : 0;

  return (
    <section className="panel">
      <div className="list-heading">
        <h2>Detalle de {name}</h2>
        <button className="secondary" onClick={onClose}>Cerrar</button>
      </div>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p className="muted">Caso actual: {data.actualCase || "—"}</p>
          {!relevantSet && (
            <p className="muted">
              Esta partida aún no incluye relevantDecisionsMade, por eso no se
              marca qué decisiones fueron relevantes.
            </p>
          )}
          {relevantSet && data.decisionsMade.length > 0 && (
            <RelevancePie relevant={relevantCount} notRelevant={notRelevantCount} />
          )}
          {data.decisionsMade.length === 0 ? (
            <p className="muted">Este jugador todavía no ha tomado decisiones.</p>
          ) : (
            <ol className="decision-list">
              {data.decisionsMade.map((d, i) => (
                <li key={i}>
                  <span>{d}</span>
                  {relevantSet && <RelevanceBadge relevant={relevantSet.has(d)} />}
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/dashboard/");
      if (!response.ok) throw new Error("No fue posible cargar el dashboard");
      setData(await response.json());
      setLastUpdate(new Date());
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const totals = data?.totals;
  const noRelevance = totals && totals.precision === null;

  return (
    <main className="container wide">
      <header>
        <span className="eyebrow">DASHBOARD · RENDIMIENTO DEL JUGADOR</span>
        <h1>Panel del juego</h1>
        <div className="status">
          <span className={`dot ${error ? "off" : ""}`} />
          {error
            ? error
            : `Actualizado ${lastUpdate ? lastUpdate.toLocaleTimeString() : "..."}`}
          <button className="secondary small" onClick={load}>Actualizar</button>
        </div>
      </header>

      {!data && !error && <p className="muted">Cargando...</p>}

      {data && totals.players === 0 && (
        <section className="panel">
          <p className="muted">
            Todavía no hay partidas guardadas. Cuando el juego envíe su
            saveFile.json aparecerá aquí.
          </p>
        </section>
      )}

      {data && totals.players > 0 && (
        <>
          <div className="cards">
            <Card label="Jugadores" value={totals.players} />
            <Card label="Decisiones totales" value={totals.decisions} />
            <Card label="Decisiones por jugador" value={totals.avg_decisions_per_player} />
            <Card label="Decisiones relevantes" value={fmt(totals.relevant_decisions)}
                  hint={noRelevance ? "Sin datos: falta relevantDecisionsMade" : null} />
            <Card label="Precisión" value={fmt(totals.precision, "%")}
                  hint={noRelevance ? null : "Relevantes ÷ decisiones tomadas"} />
          </div>

          <div className="grid-2">
            <section className="panel">
              <h2>Jugadores por caso actual</h2>
              <Bars rows={data.players_per_case} labelKey="case" valueKey="players" />
            </section>

            <section className="panel">
              <h2>Decisiones más frecuentes</h2>
              {data.top_decisions.length === 0 ? (
                <p className="muted">Aún no hay decisiones registradas.</p>
              ) : (
                <Bars rows={data.top_decisions} labelKey="decision" valueKey="percent"
                      max={100} suffix="%" wide
                      badge={row => <RelevanceBadge relevant={row.relevant} />} />
              )}
              <p className="muted small-note">Porcentaje de jugadores que tomó cada decisión.</p>
            </section>
          </div>

          <section className="panel">
            <h2>Jugadores</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Jugador</th><th>Caso actual</th><th>Decisiones</th>
                    <th>Relevantes</th><th>Precisión</th><th>Última partida</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.players.map(p => (
                    <tr key={p.playerName}>
                      <td><strong>{p.playerName}</strong></td>
                      <td>{p.actualCase}</td>
                      <td>{p.decisions}</td>
                      <td>{fmt(p.relevant)}</td>
                      <td>{fmt(p.precision, "%")}</td>
                      <td>{p.updated_at ? new Date(p.updated_at).toLocaleString() : "—"}</td>
                      <td>
                        <button className="secondary small"
                                onClick={() => setSelected(p.playerName)}>Ver</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {selected && <PlayerDetail name={selected} onClose={() => setSelected(null)} />}
        </>
      )}

      <footer>Se actualiza automáticamente cada {REFRESH_MS / 1000} s</footer>
    </main>
  );
}
