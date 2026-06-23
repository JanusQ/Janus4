# Janus4 tutorial image.
#
# Qtenon needs the prebuilt RISC-V toolchain and Verilator simulator already
# packaged in janusq/qtenon:isca2026. The Janus4 image layers the numbered
# topic tree and topic-specific kernels on top so attendees use one container.

FROM janusq/qtenon:isca2026

ARG QTENON_NOTEBOOK_TIMEOUT=1200

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QTENON_SMOKE_CACHE_DIR=/opt/qtenon-smoke-cache \
    ARTERY_VENV=/opt/artery-venv \
    CHOCOQ_VENV=/opt/chocoq-venv \
    ADAPTDQC_VENV=/opt/adaptdqc-venv \
    QRAM_VENV=/opt/qram-venv

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN rm -rf /workspace/code \
    && python -m venv "${ARTERY_VENV}" \
    && python -m venv "${CHOCOQ_VENV}"

COPY 2-qtenon/ /workspace/2-qtenon/
RUN python -m ipykernel install --prefix=/usr/local --name qtenon --display-name "Qtenon"
RUN cd /workspace/2-qtenon \
    && QTENON_NOTEBOOK_TIMEOUT="${QTENON_NOTEBOOK_TIMEOUT}" \
       bash tutorial/scripts/build_smoke_cache.sh

COPY 3-artery/software/requirements.txt /tmp/artery-requirements.txt
RUN "${ARTERY_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "${ARTERY_VENV}/bin/python" -m pip install --no-cache-dir -r /tmp/artery-requirements.txt ipykernel

COPY 5-Choco-Q/requirements.txt /tmp/chocoq-requirements.txt
RUN "${CHOCOQ_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir -r /tmp/chocoq-requirements.txt

COPY 4-adaptDQC/requirements.txt /tmp/adaptdqc-requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel uv \
    && uv python install 3.10 \
    && uv venv --python 3.10 "${ADAPTDQC_VENV}" \
    && uv pip install --python "${ADAPTDQC_VENV}/bin/python" -r /tmp/adaptdqc-requirements.txt

COPY 6-EXP-QRAM/requirements-docker.txt /tmp/qram-requirements.txt
RUN uv python install 3.9 \
    && uv venv --python 3.9 "${QRAM_VENV}" \
    && uv pip install --python "${QRAM_VENV}/bin/python" -r /tmp/qram-requirements.txt

COPY README.md LICENSE /workspace/
COPY 3-artery/ /workspace/3-artery/
COPY 4-adaptDQC/ /workspace/4-adaptDQC/
COPY 5-Choco-Q/ /workspace/5-Choco-Q/

RUN "${ARTERY_VENV}/bin/python" -m pip install --no-cache-dir --no-deps -e /workspace/3-artery/software \
    && "${ARTERY_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name artery --display-name "Artery"

RUN "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir --no-deps -e /workspace/5-Choco-Q \
    && "${CHOCOQ_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name chocoq --display-name "Choco-Q"

RUN "${ADAPTDQC_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name adaptiveqc --display-name "AdaptDQC"

COPY 6-EXP-QRAM/ /workspace/6-EXP-QRAM/

RUN uv pip install --python "${QRAM_VENV}/bin/python" --no-deps -e /workspace/6-EXP-QRAM \
    && "${QRAM_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name qram --display-name "QRAM"

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.root_dir=/workspace", \
     "--no-browser", \
     "--allow-root"]
