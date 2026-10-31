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

## API del juego (Unity)
- `POST /api/saves/`: Unity envía el contenido de `saveFile.json`. Requiere la
  cabecera `X-API-Key` con el valor de `GAME_API_KEY`. Guarda un documento por
  `playerName` (si ya existe, lo actualiza).
- `GET /api/dashboard/`: métricas agregadas que consume el dashboard.
- `GET /api/players/<playerName>/`: partida completa de un jugador.

Prueba rápida sin Unity:
```bash
curl -X POST http://localhost/api/saves/ \
  -H "Content-Type: application/json" -H "X-API-Key: TU_CLAVE" \
  -d '{"playerName":"Sans","actualCase":"Situacion1","decisionsMade":["Observar el Rostro"],"relevantDecisionsMade":["Observar el Rostro"]}'
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
# MedicPleaseDashboard
