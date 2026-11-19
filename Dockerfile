# Imagen única para la nube (Render): compila el frontend y lo sirve junto con la API de Django.
# Para desarrollo local sigue usándose docker-compose.yml (backend/ y frontend/ por separado).

# ---- 1) Compilar el frontend (Vite) ----
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 2) Django (gunicorn) + frontend compilado ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist ./frontend_dist

RUN addgroup --system app && adduser --system --ingroup app appuser \
    && chown -R appuser:app /app
USER appuser

# Render indica el puerto en la variable PORT (por defecto 10000).
ENV PORT=10000
EXPOSE 10000
CMD gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 --access-logfile - --error-logfile -
