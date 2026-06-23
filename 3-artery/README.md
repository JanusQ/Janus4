# ARTERY Feedback Tutorial

This repository contains the reproduced ARTERY feedback demo used for the ISCA tutorial presentation.

This topic follows the tutorial topic layout:

```text
docs/       Notes and tutorial documentation
hw/         Hardware interface contract, not the full Vivado source tree
software/   Python analysis library, API server, and demo scripts
tools/      Host-side UDP test scripts and GUI demo
demo/       Numbered notebooks and result figures
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

## Software Quick Start

```bash
cd software
conda create -n qfeedback python=3.10
conda activate qfeedback
pip install -r requirements.txt
pip install -e .
```

Place `s21_data.mat` in `software/` before running the demo:

```bash
python example_library_usage.py
```

## API Demo

```bash
cd software
python3 api_server.py
```

The service runs at:

```text
http://localhost:5000
```

Main endpoints:

```text
POST /api/load
POST /api/cluster
POST /api/optimize
POST /api/predict
```

## GUI Demo

```bash
cd tools/gui_demo
python3 artery_remote_control.py
```

The GUI can configure the bitstream, network parameters, S21 input file, FPGA programming command, UDP test command, and feedback waveform visualization.

## Demo Notebooks

The numbered notebooks are under:

```text
demo/ipynb/
```

They are split and extended from the original software feedback analysis notebook. Each notebook keeps the runnable Python cells separate from the fixed result figures, then adds the ARTERY hardware/predictor interpretation.

Recommended order:

```text
1_1_artery_overview.ipynb
1_2_s21_data_loading.ipynb
2_1_iq_demodulation.ipynb
2_2_state_classification.ipynb
2_3_segmented_demodulation_and_prediction.ipynb
3_1_trajectory_and_window_search.ipynb
4_1_branch_history_and_hardware_interface.ipynb
```

Result figures used by the notebooks are under:

```text
demo/results/
```
