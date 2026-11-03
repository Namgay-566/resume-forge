# Static build served by nginx. The live preview imports the resume CSS from the backend
# folder, so build from the repository root:
#   docker build -f frontend/Dockerfile --build-arg VITE_API_URL=https://api.example.com/api .

FROM node:22-alpine AS build
WORKDIR /repo/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
COPY backend/app/services/export/templates/css /repo/backend/app/services/export/templates/css
# Baked in at build time (Vite inlines import.meta.env).
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /repo/frontend/dist /usr/share/nginx/html
EXPOSE 80
