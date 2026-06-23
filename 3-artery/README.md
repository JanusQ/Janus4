# ARTERY Feedback Tutorial

Topic 3 of the Janus 4.0 tutorial provides an ARTERY-style low-latency quantum feedback demo with S21/IQ analysis, trajectory prediction, and hardware interface notes.

## Layout

- `tutorial/3_1_artery_feedback_tutorial.ipynb` is the attendee-facing notebook.
- `tutorial/s21_data.mat.gz` contains the compressed S21 readout dataset used by the notebook.
- `tutorial/original_notebook/` contains result figures exported from the original software feedback analysis notebook.
- `software/` contains the Python analysis package, examples, and API server.
- `hw/interface/` contains the packet format, datapath description, and Verilog interface boundary, not the full Vivado project.
- `tools/` contains host-side UDP test scripts and GUI utilities for the board demo.

## Docker

ARTERY runs inside the shared Janus4 tutorial image:

```bash
docker pull janusq/janus4:isca2026
docker run --rm --platform linux/amd64 -p 127.0.0.1:8888:8888 janusq/janus4:isca2026
```

Then open `3-artery/tutorial/3_1_artery_feedback_tutorial.ipynb`
and select the `ARTERY` kernel. The notebook automatically extracts
`tutorial/s21_data.mat.gz` to a temporary directory before loading the S21 data.

For a quick import and notebook execution check:

```bash
3-artery/scripts/smoke_docker.sh
```

## Hardware Interface

The complete Vivado project is intentionally not included here. The tutorial keeps the interface-level boundary used by the reproduced board demo:

```text
hw/interface/
├── artery_feedback_interface.v
├── feedback_datapath.md
└── udp_packet_format.md
```

This documents the UDP/DDR/readout stream, ARTERY feedback decision metadata, and feedback waveform output interface.
