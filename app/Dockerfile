# Tag fixa na série 3.12-slim (e não um digest) para receber os patches da imagem
# oficial; cada build passa pelo Trivy no pipeline.
# nosemgrep: dockerfile.audit.dockerfile-source-not-pinned
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 DATABASE_PATH=/dados/app.sqlite3
WORKDIR /app
COPY requirements.txt .
# Atualiza os pacotes do sistema da imagem base para fechar CVEs já corrigidas
# (o Trivy barra a imagem se houver HIGH/CRITICAL com correção disponível).
# O setuptools não é usado pelo app e tinha a CVE-2025-47273: é removido da imagem.
# nosemgrep: dockerfile.best-practice.avoid-apt-get-upgrade
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y setuptools wheel \
 && find / -xdev -path /proc -prune -o \( -name "setuptools*" -o -name "_distutils_hack" -o -name "distutils-precedence.pth" \) -print0 | xargs -0 rm -rf
COPY src/ ./src/
RUN useradd --create-home --uid 10001 app && mkdir -p /dados && chown app /dados
USER app
WORKDIR /app/src/app_alertas
EXPOSE 8000
HEALTHCHECK CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/saude', timeout=5)"]
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
