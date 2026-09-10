# 1. Сборка статики Create React App
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY public ./public
COPY src ./src
# Пустой адрес API: браузер ходит на тот же origin, а nginx проксирует /api на бэкенд.
ENV REACT_APP_API_URL=""
RUN npm run build

# 2. Раздача собранной статики nginx'ом
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
