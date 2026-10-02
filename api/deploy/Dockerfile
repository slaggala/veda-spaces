# Base image pinned by digest (python:3.13-slim multi-arch index, resolved 2026-10-02); dependencies installed
# only from the hash-locked requirements.txt, so the image is the tested set (IR-13, SEC-007).
# To update: resolve the new digest, rebuild, rerun CI, and record the change in the release notes.
FROM python:3.13-slim@sha256:bb2988715db2cf7ace7b53f38f3cffbef7c7046a656bee66245eb0ed386e2e81
# CVE-2026-103111: the pinned base still ships libpcre2-8-0 10.46-1~deb13u2. Upgrade only that package from Debian
# security, and fail the build unless the fixed version is installed. Remove once the base digest includes it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade libpcre2-8-0 \
 && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libpcre2-8-0)" ge 10.46-1~deb13u3 \
 && rm -rf /var/lib/apt/lists/*
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
