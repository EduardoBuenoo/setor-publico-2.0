FROM nginx:alpine
COPY --chmod=644 nginx.conf /etc/nginx/conf.d/default.conf
COPY --chmod=644 *.html /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/
RUN chmod -R a+rX /usr/share/nginx/html
