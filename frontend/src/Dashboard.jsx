import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import RadarChart from "./RadarChart";

const REFRESH_MS = 15000;

const fmt = (value, suffix = "") =>
  value === null || value === undefined ? "—" : `${value}${suffix}`;

const STATUS = {
  correct: { label: "Diagnóstico correcto", cls: "ok" },
  incorrect: { label: "Diagnóstico incorrecto", cls: "no" },
  abandoned: { label: "Abandonado", cls: "warn" },
  in_progress: { label: "En curso", cls: "info" },
};

function attemptStatus(attempt) {
  if (attempt.isAbandoned) return "abandoned";
  if (!attempt.isFinished) return "in_progress";
  return attempt.diagnosedCorrectly ? "correct" : "incorrect";
}

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

function StatusBadge({ status }) {
  const { label, cls } = STATUS[status];
  return <span className={`badge ${cls}`}>{label}</span>;
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

const WEEK_AXES = [
  { key: "success_rate", label: "% de éxito" },
  { key: "precision", label: "Precisión" },
  { key: "completion_rate", label: "Finalización" },
  { key: "participation", label: "Participación" },
];

const WEEK_ROWS = [
  { key: "attempts", label: "Intentos", suffix: "" },
  { key: "completed", label: "Terminados", suffix: "" },
  { key: "abandoned", label: "Abandonados", suffix: "" },
  { key: "correct", label: "Diagnósticos correctos", suffix: "" },
  { key: "active_players", label: "Jugadores activos", suffix: "" },
  ...WEEK_AXES.map(a => ({ key: a.key, label: a.label, suffix: "%" })),
];

const day = iso => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

function change(current, previous, suffix) {
  if (current === null || current === undefined || previous === null || previous === undefined) return "—";
  const diff = Math.round((current - previous) * 10) / 10;
  const unit = suffix === "%" ? " pts" : "";
  return `${diff > 0 ? "+" : ""}${diff}${unit}`;
}

function WeeklyComparison({ weekly }) {
  const { current, previous } = weekly;
  const currentName = `Últimos 7 días (${day(current.from)} – ${day(current.to)})`;
  const previousName = `7 días anteriores (${day(previous.from)} – ${day(previous.to)})`;
  const series = [
    { name: currentName, color: "#60a5fa", values: WEEK_AXES.map(a => current[a.key]) },
    { name: previousName, color: "#f59e0b", values: WEEK_AXES.map(a => previous[a.key]) },
  ];

  return (
    <section className="panel">
      <h2>Comparación semanal</h2>
      {current.attempts === 0 && previous.attempts === 0 ? (
        <p className="muted">Aún no hay intentos en las últimas dos semanas.</p>
      ) : (
        <div className="weekly">
          <div className="weekly-chart">
            <RadarChart axes={WEEK_AXES} series={series} />
            <div className="radar-legend">
              {series.map(s => (
                <span key={s.name}>
                  <i className="swatch" style={{ background: s.color }} />{s.name}
                </span>
              ))}
            </div>
          </div>
          <div className="table-wrap weekly-table">
            <table>
              <thead>
                <tr><th>Métrica</th><th>Últimos 7 d.</th><th>7 d. previos</th><th>Cambio</th></tr>
              </thead>
              <tbody>
                {WEEK_ROWS.map(row => (
                  <tr key={row.key}>
                    <td>{row.label}</td>
                    <td>{fmt(current[row.key], row.suffix)}</td>
                    <td>{fmt(previous[row.key], row.suffix)}</td>
                    <td>{change(current[row.key], previous[row.key], row.suffix)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="muted small-note">
        Éxito: correctos ÷ terminados. Finalización: terminados ÷ (terminados + abandonados).
        Participación: jugadores con actividad ÷ jugadores totales. Cada intento se ubica en la
        semana en que el servidor lo recibió terminado (o, si sigue en curso, cuando lo vio por primera vez).
      </p>
    </section>
  );
}

function PlayerDetail({ name, isAdmin, onClose, onDeleted }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api(`/players/${encodeURIComponent(name)}/`)
      .then(setData)
      .catch(e => setError(e.message));
  }, [name]);

  async function removePlayer() {
    if (!window.confirm(`¿Eliminar todos los datos de ${name}? Esta acción no se puede deshacer.`)) return;
    try {
      await api(`/players/${encodeURIComponent(name)}/`, { method: "DELETE" });
      onDeleted();
    } catch (e) {
      setError(e.message);
    }
  }

  const history = data?.caseHistory ?? [];
  const allDecisions = history.flatMap(c => c.attempts.flatMap(a => a.decisions));
  const rated = allDecisions.filter(d => d.isRelevant !== null && d.isRelevant !== undefined);
  const relevantCount = rated.filter(d => d.isRelevant).length;

  return (
    <section className="panel">
      <div className="list-heading">
        <h2>Detalle de {name}</h2>
        <div className="row-actions">
          {isAdmin && <button className="danger" onClick={removePlayer}>Eliminar jugador</button>}
          <button className="secondary" onClick={onClose}>Cerrar</button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p className="muted">Caso actual: {data.actualCase || "—"}</p>

          {rated.length > 0 && (
            <RelevancePie relevant={relevantCount} notRelevant={rated.length - relevantCount} />
          )}

          {history.length === 0 && (
            <p className="muted">Este jugador todavía no tiene intentos registrados.</p>
          )}

          {history.map(c => (
            <div className="case-block" key={c.caseId}>
              <h3>{c.caseId}</h3>
              {c.attempts.length === 0 && <p className="muted">Sin intentos.</p>}
              {c.attempts.map((a, i) => {
                const rel = a.decisions.filter(d => d.isRelevant === true).length;
                const hasRating = a.decisions.some(
                  d => d.isRelevant !== null && d.isRelevant !== undefined
                );
                return (
                  <details className="attempt" key={a.attemptNumber ?? i}
                           open={i === c.attempts.length - 1}>
                    <summary>
                      <strong>Intento {a.attemptNumber ?? i + 1}</strong>
                      <StatusBadge status={attemptStatus(a)} />
                      <span className="muted">
                        {a.decisions.length} decisiones
                        {hasRating ? ` · ${rel} relevantes` : ""}
                      </span>
                    </summary>
                    {a.decisions.length === 0 ? (
                      <p className="muted">No se registraron decisiones en este intento.</p>
                    ) : (
                      <ol className="decision-list">
                        {a.decisions.map((d, j) => (
                          <li key={j}>
                            <span>{d.decision}</span>
                            <RelevanceBadge relevant={d.isRelevant} />
                          </li>
                        ))}
                      </ol>
                    )}
                  </details>
                );
              })}
            </div>
          ))}
        </>
      )}
    </section>
  );
}

export default function Dashboard({ user }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await api("/dashboard/"));
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
            <Card label="Intentos" value={totals.attempts} />
            <Card label="Diagnóstico correcto" value={fmt(totals.success_rate, "%")}
                  hint="Sobre intentos terminados sin abandonar" />
            <Card label="Abandono" value={fmt(totals.abandon_rate, "%")}
                  hint="Sobre el total de intentos" />
            <Card label="Intentos hasta acertar" value={fmt(totals.avg_attempts_to_success)}
                  hint="Promedio por jugador y caso" />
            <Card label="Precisión de decisiones" value={fmt(totals.precision, "%")}
                  hint={totals.precision === null ? "Sin decisiones evaluadas" : "Relevantes ÷ tomadas"} />
          </div>

          <WeeklyComparison weekly={data.weekly} />

          <div className="grid-2">
            <section className="panel">
              <h2>Resultado de los intentos</h2>
              <Bars rows={data.outcomes} labelKey="label" valueKey="count" wide />
            </section>

            <section className="panel">
              <h2>Jugadores por caso actual</h2>
              <Bars rows={data.players_per_case} labelKey="case" valueKey="players" />
            </section>
          </div>

          <section className="panel">
            <h2>Rendimiento por caso</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Caso</th><th>Jugadores</th><th>Intentos</th><th>Abandonos</th>
                    <th>Dx correctos</th><th>% éxito</th><th>Intentos hasta acertar</th>
                    <th>Precisión</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cases.map(c => (
                    <tr key={c.case}>
                      <td><strong>{c.case}</strong></td>
                      <td>{c.players}</td>
                      <td>{c.attempts}</td>
                      <td>{c.abandoned}</td>
                      <td>{c.correct}</td>
                      <td>{fmt(c.success_rate, "%")}</td>
                      <td>{fmt(c.avg_attempts_to_success)}</td>
                      <td>{fmt(c.precision, "%")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

          <section className="panel">
            <h2>Jugadores</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Jugador</th><th>Caso actual</th><th>Intentos</th><th>Abandonos</th>
                    <th>Dx correctos</th><th>% éxito</th><th>Decisiones</th>
                    <th>Precisión</th><th>Última partida</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.players.map(p => (
                    <tr key={p.playerName}>
                      <td><strong>{p.playerName}</strong></td>
                      <td>{p.actualCase}</td>
                      <td>{p.attempts}</td>
                      <td>{p.abandoned}</td>
                      <td>{p.correct}</td>
                      <td>{fmt(p.success_rate, "%")}</td>
                      <td>{p.decisions}</td>
                      <td>{fmt(p.precision, "%")}</td>
                      <td>{p.updated_at ? new Date(p.updated_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "—"}</td>
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

          {selected && (
            <PlayerDetail
              name={selected}
              isAdmin={user.role === "admin"}
              onClose={() => setSelected(null)}
              onDeleted={() => { setSelected(null); load(); }}
            />
          )}
        </>
      )}

      <footer>Se actualiza automáticamente cada {REFRESH_MS / 1000} s</footer>
    </main>
  );
}
