FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e .
COPY . .
# G1: real Swiss Ephemeris data baked in; ephemeral host disks would otherwise trip
# ASTRO_REQUIRE_SWISS_FILES on every redeploy. Digests pinned; the build fails closed.
ENV ASTRO_EPHE_PATH=/ephe
RUN mkdir -p /ephe && cd /ephe \
 && for f in sepl_18.se1 semo_18.se1 seas_18.se1; do \
      curl -fsSL --retry 3 -o "$f" "https://raw.githubusercontent.com/aloistr/swisseph/cae9ecd4b201544d85e411aced17660932514d43/ephe/$f"; \
    done \
 && printf '%s\n' \
      'ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66  sepl_18.se1' \
      '1ca07bd67c24374d77226180c20a4f9996cba013697894810518e7eb582ca4f7  semo_18.se1' \
      'a2cd8fc33807c78ca9a700c91c2e042258b12fc4796519e00781440b5ad8b2e2  seas_18.se1' \
      > /tmp/ephe.sha256 \
 && sha256sum -c /tmp/ephe.sha256
ENV ASTRO_PLACES_DB=/srv/data/places.sqlite
RUN python scripts/extract_places.py --dataset cities500 --output /srv/data/places.sqlite
RUN chmod +x /srv/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/srv/docker-entrypoint.sh"]
