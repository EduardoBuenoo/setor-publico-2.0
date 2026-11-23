FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG DOCUMENTOS=0
WORKDIR /app
COPY . /app/
RUN --mount=type=secret,id=pip_cert \
    if [ -r /run/secrets/pip_cert ]; then export PIP_CERT=/run/secrets/pip_cert; fi; \
    pip install --no-cache-dir -r backend/requirements.txt \
    && if [ "$DOCUMENTOS" = "1" ]; then pip install --no-cache-dir -r backend/requirements-documentos.txt; fi \
    && groupadd -r sigdei && useradd -r -g sigdei sigdei \
    && mkdir -p /app/backend/staticfiles /var/lib/sigdei \
    && chmod -R a+rX /app/backend /app/docs /app/documentos /app/scripts /app/README.md \
    && chown sigdei:sigdei /app/backend/staticfiles /var/lib/sigdei

ENV SIGDEI_INDEX_DIR=/var/lib/sigdei/index
WORKDIR /app/backend
USER sigdei
EXPOSE 8000
CMD ["sh", "/app/scripts/start-backend.sh"]
