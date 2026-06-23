# Janus4 tutorial image.
#
# Qtenon needs the prebuilt RISC-V toolchain and Verilator simulator already
# packaged in janusq/qtenon:isca2026. The Janus4 image layers the numbered
# topic tree and the Choco-Q kernel on top so attendees use one container.

FROM janusq/qtenon:isca2026

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARTERY_VENV=/opt/artery-venv \
    CHOCOQ_VENV=/opt/chocoq-venv

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN rm -rf /workspace/code \
    && python -m venv "${ARTERY_VENV}" \
    && python -m venv "${CHOCOQ_VENV}"

COPY 3-artery/software/requirements.txt /tmp/artery-requirements.txt
COPY 5-Choco-Q/requirements.txt /tmp/chocoq-requirements.txt
RUN "${ARTERY_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "${ARTERY_VENV}/bin/python" -m pip install --no-cache-dir -r /tmp/artery-requirements.txt \
    && "${CHOCOQ_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel \
    && "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir -r /tmp/chocoq-requirements.txt

COPY README.md LICENSE /workspace/
COPY 2-qtenon/ /workspace/2-qtenon/
COPY 3-artery/ /workspace/3-artery/
COPY 5-Choco-Q/ /workspace/5-Choco-Q/

RUN "${ARTERY_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name artery --display-name "ARTERY" \
    && "${CHOCOQ_VENV}/bin/python" -m pip install --no-cache-dir --no-deps -e /workspace/5-Choco-Q \
    && "${CHOCOQ_VENV}/bin/python" -m ipykernel install --prefix=/usr/local --name chocoq --display-name "Choco-Q"

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.root_dir=/workspace", \
     "--no-browser", \
     "--allow-root"]
