# Plataforma React + Django + MongoDB con Docker

## Requisitos
- Docker Engine y Docker Compose v2 (o Docker Desktop).
- Puertos 80 disponibles en el equipo.

## Primer arranque
1. Copia `.env.example` como `.env`.
2. Cambia todas las contraseñas y `DJANGO_SECRET_KEY`.
3. Ejecuta desde esta carpeta:

   ```bash
   docker compose up -d --build
   ```

4. Abre http://localhost
5. Comprueba la API en http://localhost/api/health/

## API incluida
- `GET /api/health/`: comprueba la conexión con MongoDB.
- `GET /api/items/`: lista los últimos 100 elementos.
- `POST /api/items/`: crea un elemento. JSON de ejemplo:
  `{"name":"Mi primer registro","description":"Prueba"}`
- `DELETE /api/items/<id>/`: elimina un elemento.

## Usar la plataforma desde otros equipos (red local)
1. En el equipo servidor: `docker compose up -d --build`.
2. Averigua su IP: en Windows `ipconfig` (IPv4 del Wi‑Fi o Ethernet), en Linux/macOS `ip a` / `ifconfig`.
3. Abre el puerto en el firewall del servidor (Windows, PowerShell como administrador):
   ```powershell
   New-NetFirewallRule -DisplayName "Plataforma web" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -Profile Private,Domain
   ```
   La red Wi‑Fi debe estar marcada como **Privada** (Configuración → Red e Internet).
4. Desde otro equipo de la misma red abre `http://IP-DEL-SERVIDOR/api/health/`;
   debe mostrar `{"status":"ok","database":"connected"}`. Luego entra a `http://IP-DEL-SERVIDOR/`.
5. En Unity usa como servidor `http://IP-DEL-SERVIDOR` y la `GAME_API_KEY` del `.env`.
   En Player Settings → Other Settings → *Allow downloads over HTTP* elige *Always allowed*.

Si cambias `HTTP_PORT`, añade `:PUERTO` a las URL y abre ese puerto en el firewall.
Mantén `AUTH_COOKIE_SECURE=0` mientras uses HTTP (con 1 el login no funciona sin HTTPS).

## Dirección pública con Tailscale Funnel (sin abrir puertos)
Publica la plataforma en `https://plataforma.<tu-tailnet>.ts.net` mediante una conexión
saliente de este equipo; no hay que tocar el router.

1. Crea una cuenta en Tailscale. En su consola de administración (DNS) activa
   **MagicDNS** y los **certificados HTTPS**, y permite **Funnel** para este equipo
   (Access controls; si falta, el contenedor lo indicará en sus registros).
2. En Settings → Keys genera una *auth key* (sin etiquetas).
3. En el `.env` agrega:
   ```
   COMPOSE_PROFILES=funnel
   TS_AUTHKEY=tskey-auth-...
   TS_HOSTNAME=plataforma
   ```
4. `docker compose up -d --build`
5. Comprueba la dirección: `docker compose exec tailscale tailscale funnel status`
   (o `docker compose logs tailscale`). La primera vez puede tardar unos minutos
   (certificado y DNS público).
6. En Unity usa esa dirección `https://...ts.net` como servidor.

Notas: no ejecutes `docker compose down -v` (borra la identidad del túnel y la dirección
cambiaría). En la consola de Tailscale desactiva la caducidad de clave de este equipo para
que no pida volver a iniciar sesión. La web sigue disponible también por la IP local.

## Usuarios y roles
Hay dos roles. Todo exige sesión salvo `/api/health/`, `/api/auth/login/` y la subida de Unity.

| | Administrador | Profesor |
|---|---|---|
| Dashboard y detalle de jugadores | Sí | Sí |
| Eliminar jugadores y exportar todos los datos | Sí | No |
| Crear, desactivar, eliminar usuarios y cambiar contraseñas | Sí | No |

El primer administrador se crea automáticamente con `ADMIN_USERNAME` y
`ADMIN_PASSWORD` del `.env` la primera vez que alguien inicia sesión y no existe
ningún administrador (cambiar luego esas variables no modifica una cuenta ya creada).
Desde la pestaña **Administración** se crean los demás usuarios, por ejemplo el
del profesor. Las contraseñas se guardan con PBKDF2 y la sesión viaja en una
cookie HttpOnly; con HTTPS pon `AUTH_COOKIE_SECURE=1`.

- `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`
- `GET|POST /api/users/`, `PATCH|DELETE /api/users/<usuario>/` (administrador)
- `DELETE /api/players/<jugador>/`, `GET /api/admin/export/` (administrador)

## API del juego (Unity)
- `POST /api/saves/`: Unity envía el contenido de `saveFile.json`. Requiere la
  cabecera `X-API-Key` con el valor de `GAME_API_KEY`. Guarda un documento por
  `playerName` (si ya existe, lo reemplaza). Formato: `caseHistory` → `attempts` →
  `decisions` (`decision` + `isRelevant`). El formato anterior (`decisionsMade`)
  todavía se acepta y se convierte automáticamente.
- `GET /api/dashboard/`: métricas agregadas (incluye la comparación semanal) que consume el dashboard.
- `GET /api/players/<playerName>/`: partida completa de un jugador.

Prueba rápida sin Unity:
```bash
curl -X POST http://localhost/api/saves/ \
  -H "Content-Type: application/json" -H "X-API-Key: TU_CLAVE" \
  -d '{"playerName":"Sans","actualCase":"Situacion1","caseHistory":[{"caseId":"Situacion1","attempts":[{"attemptNumber":1,"isFinished":true,"isAbandoned":false,"diagnosedCorrectly":true,"decisions":[{"decision":"Trigémino","isRelevant":true}]}]}]}'
```

## Comandos útiles
```bash
docker compose ps
docker compose logs -f
docker compose logs -f backend
docker compose down
docker compose up -d --build
```

Los datos de MongoDB se guardan en el volumen `plataforma_mongo_data`.
`docker compose down` conserva los datos. **No ejecutes `docker compose down -v`**
si deseas conservarlos.

## Arquitectura y notas
- El navegador accede al frontend por el puerto 80.
- Nginx sirve React y reenvía `/api/` a Django.
- Django se conecta a MongoDB por la red privada de Docker.
- MongoDB no publica el puerto 27017 en el host.
- Los documentos de la aplicación se guardan en MongoDB usando PyMongo.
- SQLite se reserva para mecanismos internos de Django si se habilitan después.
- El usuario Mongo de la aplicación solo tiene `readWrite` sobre la base `plataforma`.

## Importante antes de producción
Esta es una base funcional para desarrollo y despliegue inicial, no una configuración
de producción endurecida. Antes de exponerla públicamente:
- configura HTTPS (por ejemplo, con un proxy inverso y certificados TLS);
- usa contraseñas y `DJANGO_SECRET_KEY` fuertes y únicos;
- ajusta `DJANGO_ALLOWED_HOSTS` al dominio real;
- establece `DEBUG=0`;
- configura copias de seguridad probadas del volumen MongoDB;
- añade autenticación, autorización, límites de solicitudes y validación según tu negocio;
- fija y actualiza imágenes/dependencias con una política de mantenimiento;
- no publiques MongoDB directamente en Internet.

El script `mongo/init-mongo.js` se ejecuta únicamente cuando MongoDB inicializa
un volumen de datos vacío. Si cambias las credenciales después de crear el volumen,
debes actualizar el usuario dentro de MongoDB manualmente; recrear el contenedor no
vuelve a ejecutar el script.
