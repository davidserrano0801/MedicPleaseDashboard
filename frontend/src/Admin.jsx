import { useCallback, useEffect, useState } from "react";
import { api, downloadFile, ROLE_LABELS } from "./api";

const when = iso => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "—");

export default function Admin({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ username: "", password: "", role: "teacher" });
  const [editing, setEditing] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  const load = useCallback(async () => {
    try {
      setUsers(await api("/users/"));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function run(action, success) {
    setError("");
    setNotice("");
    try {
      await action();
      if (success) setNotice(success);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const create = event => {
    event.preventDefault();
    run(async () => {
      await api("/users/", { method: "POST", body: form });
      setForm({ username: "", password: "", role: "teacher" });
    }, "Usuario creado");
  };

  const patch = (username, body, success) =>
    run(() => api(`/users/${encodeURIComponent(username)}/`, { method: "PATCH", body }), success);

  const remove = username => {
    if (!window.confirm(`¿Eliminar al usuario ${username}? Esta acción no se puede deshacer.`)) return;
    run(() => api(`/users/${encodeURIComponent(username)}/`, { method: "DELETE" }), "Usuario eliminado");
  };

  const savePassword = username =>
    run(async () => {
      await api(`/users/${encodeURIComponent(username)}/`, {
        method: "PATCH", body: { password: newPassword },
      });
      setEditing(null);
      setNewPassword("");
    }, "Contraseña actualizada");

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      <section className="panel">
        <h2>Crear usuario</h2>
        <form className="inline-form" onSubmit={create}>
          <div>
            <label htmlFor="new-username">Usuario</label>
            <input id="new-username" value={form.username} autoComplete="off"
                   onChange={e => setForm({ ...form, username: e.target.value })} />
          </div>
          <div>
            <label htmlFor="new-password">Contraseña (mín. 8)</label>
            <input id="new-password" type="password" value={form.password} autoComplete="new-password"
                   onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>
          <div>
            <label htmlFor="new-role">Rol</label>
            <select id="new-role" value={form.role}
                    onChange={e => setForm({ ...form, role: e.target.value })}>
              <option value="teacher">Profesor (solo dashboard)</option>
              <option value="admin">Administrador (acceso total)</option>
            </select>
          </div>
          <button type="submit" disabled={!form.username || !form.password}>Crear</button>
        </form>
      </section>

      <section className="panel">
        <h2>Usuarios</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Usuario</th><th>Rol</th><th>Estado</th><th>Creado</th>
                <th>Último acceso</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const self = u.username === currentUser.username;
                return (
                  <tr key={u.username}>
                    <td><strong>{u.username}</strong>{self && <span className="badge info">tú</span>}</td>
                    <td>{ROLE_LABELS[u.role] ?? u.role}</td>
                    <td>{u.active
                      ? <span className="badge ok">activo</span>
                      : <span className="badge no">desactivado</span>}</td>
                    <td>{when(u.created_at)}</td>
                    <td>{when(u.last_login)}</td>
                    <td className="row-actions">
                      {editing === u.username ? (
                        <>
                          <input type="password" className="mini-input" placeholder="Nueva contraseña"
                                 autoComplete="new-password" value={newPassword}
                                 onChange={e => setNewPassword(e.target.value)} />
                          <button className="small" disabled={newPassword.length < 8}
                                  onClick={() => savePassword(u.username)}>Guardar</button>
                          <button className="secondary small"
                                  onClick={() => { setEditing(null); setNewPassword(""); }}>Cancelar</button>
                        </>
                      ) : (
                        <>
                          <button className="secondary small"
                                  onClick={() => { setEditing(u.username); setNewPassword(""); }}>
                            Cambiar contraseña
                          </button>
                          {!self && (
                            <button className="secondary small"
                                    onClick={() => patch(u.username, { active: !u.active },
                                      u.active ? "Usuario desactivado" : "Usuario activado")}>
                              {u.active ? "Desactivar" : "Activar"}
                            </button>
                          )}
                          {!self && (
                            <button className="danger small" onClick={() => remove(u.username)}>
                              Eliminar
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small-note">
          Siempre debe quedar al menos un administrador activo. Al cambiar la contraseña
          de un usuario se cierra su sesión.
        </p>
      </section>

      <section className="panel">
        <h2>Datos</h2>
        <p className="muted">
          Descarga una copia completa: las partidas de todos los jugadores y la lista de
          usuarios (sin contraseñas). Para eliminar a un jugador usa el botón
          «Eliminar jugador» en su detalle del dashboard.
        </p>
        <button className="secondary"
                onClick={() => downloadFile("/admin/export/", "plataforma-datos.json").catch(e => setError(e.message))}>
          Exportar todos los datos (JSON)
        </button>
      </section>
    </>
  );
}
