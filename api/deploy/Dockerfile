FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --system --uid 10001 veda && chown -R veda /srv/api
USER veda
# The database lives on the dedicated encrypted volume mounted at /var/lib/veda (OPS-007).
ENV VEDA_DATABASE_URL=sqlite:////var/lib/veda/veda.db
EXPOSE 8000
CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "wsgi:app"]
