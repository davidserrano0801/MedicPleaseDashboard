import { useEffect, useState } from "react";
import { api, setUnauthorizedHandler, ROLE_LABELS } from "./api";
import Login from "./Login";
import Dashboard from "./Dashboard";
import Admin from "./Admin";

function Shell({ user, onLogout }) {
  const [tab, setTab] = useState("dashboard");
  const isAdmin = user.role === "admin";

  return (
    <main className="container wide">
      <div className="topbar">
        <nav className="tabs">
          <button className={tab === "dashboard" ? "tab active" : "tab"}
                  onClick={() => setTab("dashboard")}>Dashboard</button>
          {isAdmin && (
            <button className={tab === "admin" ? "tab active" : "tab"}
                    onClick={() => setTab("admin")}>Administración</button>
          )}
        </nav>
        <div className="whoami">
          <span>{user.username} · {ROLE_LABELS[user.role] ?? user.role}</span>
          <button className="secondary small" onClick={onLogout}>Cerrar sesión</button>
        </div>
      </div>

      {tab === "admin" && isAdmin ? <Admin currentUser={user} /> : <Dashboard user={user} />}
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = comprobando sesión; null = sin sesión

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    api("/auth/me/").then(setUser).catch(() => setUser(null));
  }, []);

  const logout = async () => {
    try { await api("/auth/logout/", { method: "POST", body: {} }); } catch { /* sin conexión: igual salimos */ }
    setUser(null);
  };

  if (user === undefined) {
    return <main className="container"><p className="muted">Cargando...</p></main>;
  }
  if (user === null) return <Login onLogin={setUser} />;
  return <Shell user={user} onLogout={logout} />;
}
