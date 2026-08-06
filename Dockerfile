# Yedek dağıtım yolu — render.yaml'daki native (Docker'sız) Python
# runtime derlemesi bir sebeple çalışmazsa (ör. build image'da npm yoksa),
# Render'da servisi "Docker" runtime'a çevirip bu dosyayı kullan. Bkz.
# README.md "Deploy (Render)" → "Docker'a geçiş (yedek plan)".

# --- Aşama 1: Vue SPA'yı derle ------------------------------------------
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Aşama 2: Django + gunicorn -----------------------------------------
FROM python:3.13-slim AS backend
WORKDIR /app

# collectstatic import zamanında SECRET_KEY/DEBUG okur (settings.py) — bunlar
# yalnızca BUILD anında, derlenmiş statik dosyalara hiçbir şekilde sızmayan
# geçici birer yer tutucudur. Render'ın GERÇEK ortam değişkenleri (asıl
# DJANGO_SECRET_KEY, DJANGO_DEBUG=false vb.) konteyner ÇALIŞMA zamanında
# bunların üzerine yazar — bkz. render.yaml envVars.
ENV DJANGO_SECRET_KEY=build-time-placeholder-overridden-at-runtime
ENV DJANGO_DEBUG=true

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN python backend/manage.py collectstatic --noinput

EXPOSE 8000
CMD python backend/manage.py migrate --noinput && \
    gunicorn backend.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 120
