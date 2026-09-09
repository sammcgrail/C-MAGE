# syntax=docker/dockerfile:1.7
#
# C-MAGE web app: the pipeline image plus a small FastAPI front end.
#
# Build from the REPOSITORY ROOT so the pipeline and its UI ship together:
#
#     docker build -t cmage:allinone -f Dockerfile.allinone .        # the pipeline
#     docker build -t cmage-webapp   -f webapp/Dockerfile .          # this image
#
# or, with compose:  docker compose -f webapp/docker-compose.yml up --build -d
#
# The base image already carries the three stage environments under
# /opt/cmage/.venvs and the model weights, so this layer only adds the web
# server's own (pure-Python) dependencies and the app itself. Point BASE_IMAGE
# at any image built from Dockerfile.allinone.
ARG BASE_IMAGE=cmage:allinone
FROM ${BASE_IMAGE}

ENV CMAGE_ROOT=/opt/cmage \
    CMAGE_DATA=/data \
    CMAGE_PORT=8080 \
    DECIMER_CACHE=/opt/cmage/models/decimer/mask_rcnn_molecule.h5 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# uv comes from its official image; the base image deliberately does not ship it.
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv

WORKDIR /opt/cmage

# The web layer gets its own interpreter + venv so nothing is added to the
# stage environments (their pins are load-bearing).
COPY webapp/requirements.txt /opt/cmage/webapp/requirements.txt
RUN --mount=type=cache,target=/var/cache/uv \
    UV_CACHE_DIR=/var/cache/uv uv venv /opt/cmage/webapp/.venv --python 3.12 \
    && UV_CACHE_DIR=/var/cache/uv VIRTUAL_ENV=/opt/cmage/webapp/.venv uv pip install -r /opt/cmage/webapp/requirements.txt \
    && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Stage 3 cannot run alone: it reads stage 2's workbook to learn which crops to
# translate. This harness writes that workbook from raw images instead, which is
# how a single-structure image upload skips segmentation. One script, not the
# whole benchmarks tree -- that carries ~21 MB of corpus PDFs the app never uses.
COPY benchmarks/run_stage3_only.sh /opt/cmage/benchmarks/run_stage3_only.sh

COPY webapp/ /opt/cmage/webapp/
RUN chmod +x /opt/cmage/webapp/entrypoint.sh && mkdir -p /data

ENV PATH=/opt/cmage/webapp/.venv/bin:$PATH
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl -sf http://localhost:8080/api/health || exit 1
ENTRYPOINT ["/opt/cmage/webapp/entrypoint.sh"]
