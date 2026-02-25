FROM node:20-bookworm-slim AS web-build
WORKDIR /repo
COPY prototype-web/package.json prototype-web/package-lock.json ./prototype-web/
WORKDIR /repo/prototype-web
RUN npm ci
COPY prototype-web/ ./
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DIST_DIR=/app/dist

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/.env.example ./backend.env.example
COPY --from=web-build /repo/prototype-web/dist ./dist

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

