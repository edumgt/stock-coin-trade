FROM nginx:alpine

COPY frontend/ /usr/share/nginx/html/
COPY docker/nginx-eks.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
