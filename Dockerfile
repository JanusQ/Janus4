# Janus4 tutorial image.
#
# Qtenon needs the prebuilt RISC-V toolchain and Verilator simulator already
# packaged in janusq/qtenon:isca2026. The Janus4 image layers the numbered
# topic tree and the Choco-Q kernel on top so attendees use one container.

FROM janusq/qtenon:isca2026

ARG QTENON_NOTEBOOK_TIMEOUT=1200

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QTENON_SMOKE_CACHE_DIR=/opt/qtenon-smoke-cache \
    CHOCOQ_VENV=/opt/chocoq-venv \
    ADAPTDQC_VENV=/opt/adaptdqc-venv

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN rm -rf /workspace/code \
    && python -m venv "${CHOCOQ_VENV}"

COPY 2-qtenon/ /workspace/2-qtenon/
RUN cd /workspace/2-qtenon \
    && QTENON_NOTEBOOK_TIMEOUT="${QTENON_NOTEBOOK_TIMEOUT}" \
       bash tutorial/scripts/build_smoke_cache.sh

COPY 5-Choco-Q/requirements.txt /tmp/chocoq-requirements.txt
RUN "${CHOCOQ_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir -r /tmp/chocoq-requirements.txt

COPY 4-adaptDQC/requirements.txt /tmp/adaptdqc-requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel uv \
    && uv python install 3.10 \
    && uv venv --python 3.10 "${ADAPTDQC_VENV}" \
    && uv pip install --python "${ADAPTDQC_VENV}/bin/python" -r /tmp/adaptdqc-requirements.txt

COPY README.md LICENSE /workspace/
COPY 4-adaptDQC/ /workspace/4-adaptDQC/
COPY 5-Choco-Q/ /workspace/5-Choco-Q/

RUN "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir --no-deps -e /workspace/5-Choco-Q \
    && "${CHOCOQ_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name chocoq --display-name "Choco-Q"

RUN "${ADAPTDQC_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name adaptiveqc --display-name "AdaptDQC"

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.root_dir=/workspace", \
     "--no-browser", \
     "--allow-root"]
