# Se construye desde la raíz del repo:  docker build -f nginx/Dockerfile .
FROM nginx:1.29-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/nginx-health || exit 1
