# BHH Access web server: the compiled PWA served by Nginx, which also forwards /api to the API.
# The Nginx configuration and the certificate are mounted by docker-compose.yml (no rebuild to change them).
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
