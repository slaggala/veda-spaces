# Base image pinned by digest (python:3.13-slim multi-arch index, resolved 2026-09-29); dependencies installed
# only from the hash-locked requirements.txt, so the image is the tested set (IR-13, SEC-007).
# To update: resolve the new digest, rebuild, rerun CI, and record the change in the release notes.
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/api
COPY requirements.txt .
# pip is removed once the locked set is installed: the runtime never installs packages, and pip's vendored
# libraries (msgpack, setuptools' pkg_resources) carry advisories the image scan rejects.
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt \
 && python -m pip uninstall -y pip
COPY . .
RUN useradd --system --uid 10001 veda && chown -R veda /srv/api
USER veda
# The database lives on the dedicated encrypted volume mounted at /var/lib/veda (OPS-007).
ENV VEDA_DATABASE_URL=sqlite:////var/lib/veda/veda.db
EXPOSE 8000
CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "wsgi:app"]
