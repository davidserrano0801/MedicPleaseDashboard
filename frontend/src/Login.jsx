import { useState } from "react";
import { api } from "./api";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api("/auth/login/", { method: "POST", body: { username, password } }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="container login-container">
      <div className="panel login-card">
        <span className="eyebrow">PLATAFORMA DEL JUEGO</span>
        <h2 className="login-title">Iniciar sesión</h2>
        <form onSubmit={submit}>
          <label htmlFor="username">Usuario</label>
          <input id="username" autoComplete="username" autoFocus value={username}
                 onChange={e => setUsername(e.target.value)} />
          <label htmlFor="password">Contraseña</label>
          <input id="password" type="password" autoComplete="current-password"
                 value={password} onChange={e => setPassword(e.target.value)} />
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy || !username || !password}>
            {busy ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
