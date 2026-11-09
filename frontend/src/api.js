// Cliente mínimo de la API. La sesión viaja en una cookie HttpOnly, así que
// el código del navegador nunca maneja la contraseña ni el token guardados.
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export async function api(path, { method = "GET", body } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data = null;
  if (response.status !== 204) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    // Sesión vencida o usuario desactivado: vuelve a la pantalla de login.
    if (response.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
    const error = new Error((data && (data.error || data.detail)) || `Error ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export async function downloadFile(path, filename) {
  const response = await fetch(`/api${path}`, { credentials: "same-origin" });
  if (!response.ok) {
    if (response.status === 401) onUnauthorized();
    throw new Error(`No se pudo descargar (${response.status})`);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const ROLE_LABELS = { admin: "Administrador", teacher: "Profesor" };
