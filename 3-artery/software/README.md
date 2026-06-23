# Software: Quantum Feedback Analysis

This directory contains the Python software used to validate the ARTERY feedback algorithm before mapping it to FPGA hardware.

It provides S21 data loading, IQ demodulation, state clustering, readout-window optimization, measurement prediction, and an optional HTTP API.

## Tutorial Setup

```bash
conda create -n qfeedback python=3.10
conda activate qfeedback
pip install -r requirements.txt
pip install -e .
```

Place `s21_data.mat` in this directory before running the demo.

## Run Demo

```bash
python example_library_usage.py
```

## Run API Server

```bash
python3 api_server.py
```

API address:

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

## Main Modules

```text
quantum_feedback/analyzer.py       High-level workflow
quantum_feedback/demodulation.py   IQ demodulation
quantum_feedback/clustering.py     State classification
quantum_feedback/prediction.py     Measurement prediction
api_server.py                      HTTP API wrapper
example_library_usage.py           End-to-end software demo
example_api_usage.py               API client example
```

<!-- Original software README below. -->

A comprehensive Python library for analyzing quantum measurement feedback data using demodulation, clustering, and predictive modeling techniques.

## Overview

This project provides a modular library (`quantum_feedback`) for analyzing quantum measurement data from superconducting qubits. It implements:

- **Signal Demodulation**: Extract quantum state information from IQ measurement data
- **K-means Clustering**: Classify quantum states based on measurement outcomes
- **Window Optimization**: Find optimal readout windows for maximum classification accuracy
- **Predictive Modeling**: Predict measurement outcomes using pattern recognition and saturating counters

## Features

- 📦 **Modular Library**: Clean separation of concerns with dedicated modules
- 🔬 **Demodulation**: Multi-frequency demodulation for quantum signal processing
- 🎯 **Classification**: K-means clustering for quantum state discrimination
- 📈 **Optimization**: Grid search for optimal readout parameters
- 🔮 **Prediction**: Branch history table-based prediction with saturating counters
- 🌐 **REST API**: Optional Flask-based API for remote access
- 📓 **Jupyter Notebook**: Interactive analysis environment

## Installation

### Prerequisites

- Python 3.7+
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd quantum_feedback_analysis
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Place your data file (`s21_data.mat`) in the project directory

## Library Structure

```
quantum_feedback/
├── __init__.py           # Package initialization
├── analyzer.py           # Main analyzer class
├── demodulation.py       # Signal demodulation
├── clustering.py         # State classification
└── prediction.py         # Measurement prediction
```

## Usage

### 1. Using the Library Directly

```python
from quantum_feedback import QuantumFeedbackAnalyzer

# Initialize analyzer
analyzer = QuantumFeedbackAnalyzer(data_path='./s21_data.mat')

# Load data
result = analyzer.load_data()
print(f"Data shape: {result['data_shape']}")

# Perform clustering
cluster_result = analyzer.analyze_clustering(idx1=1, idx2=2000, omega_idx=2)
print(f"Clustering accuracy: {cluster_result['accuracy']:.4f}")

# Optimize window parameters
opt_result = analyzer.optimize_window()
print(f"Best accuracy: {opt_result['optimization_results'][0]['best_params'][0][2]}")

# Predict measurements
pred_result = analyzer.predict_measurements(window_start=850, window_len=1800)
print(f"Prediction accuracy: {pred_result['accuracy']:.4f}")
```

### 2. Using Individual Components

```python
from quantum_feedback import Demodulator, StateClassifier
import numpy as np
from scipy.io import loadmat

# Load data
read_data = loadmat('./s21_data.mat')
read_zero = read_data['data'][0][:][:][:]
read_one = read_data['data'][1][:][:][:]
read_zero_i, read_zero_q = read_zero[:, :, 0], read_zero[:, :, 1]
read_one_i, read_one_q = read_one[:, :, 0], read_one[:, :, 1]

# Demodulation
demod = Demodulator()
result_zero = demod.demodulate(read_zero_i[0:100], read_zero_q[0:100], omega_idx=2)
result_one = demod.demodulate(read_one_i[0:100], read_one_q[0:100], omega_idx=2)

# Classification
classifier = StateClassifier()
data_zero = np.array(result_zero).T
data_one = np.array(result_one).T
fit_result = classifier.fit(data_zero, data_one)
print(f"Classification accuracy: {fit_result['accuracy']:.4f}")

# Compute centers
center_zero, center_one = classifier.compute_centers(data_zero, data_one)
print(f"Center |0⟩: {center_zero}")
print(f"Center |1⟩: {center_one}")
```

### 3. Using the REST API

Start the API server:

```bash
python3 api_server.py
```

The API will be available at `http://localhost:5000`

#### API Endpoints

**Load Data**
```bash
curl -X POST http://localhost:5000/api/load \
  -H "Content-Type: application/json" \
  -d '{"data_path": "./s21_data.mat"}'
```

**K-means Clustering**
```bash
curl -X POST http://localhost:5000/api/cluster \
  -H "Content-Type: application/json" \
  -d '{"idx1": 1, "idx2": 2000, "omega_idx": 2}'
```

**Optimize Window**
```bash
curl -X POST http://localhost:5000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Predict Measurements**
```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"window_start": 850, "window_len": 1800, "omega_idx": 2}'
```

### 4. Using the Jupyter Notebook

```bash
jupyter notebook feedback.ipynb
```

**Note**: The first few cells require `remote_CNOT_data.mat` which is not included. These cells are commented out and can be skipped.

## Project Structure

```
quantum_feedback_analysis/
├── quantum_feedback/          # Main library package
│   ├── __init__.py           # Package initialization
│   ├── analyzer.py           # Main analyzer class
│   ├── demodulation.py       # Demodulation module
│   ├── clustering.py         # Clustering module
│   └── prediction.py         # Prediction module
├── api_server.py             # Flask REST API server
├── feedback.ipynb            # Jupyter notebook
├── example_library_usage.py  # Library usage examples
├── example_api_usage.py      # API usage examples
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── LICENSE                   # MIT License
├── .gitignore               # Git ignore rules
└── s21_data.mat             # Quantum measurement data (not included in repo)
```

## API Reference

### QuantumFeedbackAnalyzer

Main class that integrates all components.

**Methods:**
- `load_data()` - Load quantum measurement data from MAT file
- `analyze_clustering(idx1, idx2, omega_idx)` - Perform K-means clustering
- `optimize_window(train_idx1, train_idx2, test_idx1, test_idx2)` - Optimize window parameters
- `predict_measurements(window_start, window_len, omega_idx, ...)` - Predict measurements
- `get_demodulator()` - Get demodulator instance
- `get_classifier()` - Get classifier instance
- `get_predictor()` - Get predictor instance

### Demodulator

Signal demodulation for quantum measurements.

**Methods:**
- `demodulate(read_i, read_q, omega_idx, phase)` - Demodulate IQ data
- `demodulate_window(read_i, read_q, window_start, window_len, omega_idx)` - Demodulate within window
- `demodulate_trajectory(read_i, read_q, window_base, window_len, window_cnt, omega_idx)` - Trajectory demodulation

### StateClassifier

Quantum state classification using clustering.

**Methods:**
- `fit(data_zero, data_one)` - Fit classifier on labeled data
- `predict(data)` - Predict state labels
- `predict_with_centers(data, center_zero, center_one)` - Distance-based prediction
- `evaluate(data, true_labels)` - Evaluate performance
- `compute_centers(data_zero, data_one)` - Compute cluster centers

### MeasurementPredictor

Predict measurement outcomes using pattern recognition.

**Methods:**
- `train(location_traces, heading_traces, labels)` - Train predictor
- `predict(location_traces, heading_traces, prior_prob, set_start, set_len)` - Predict outcomes
- `predict_with_heading(...)` - Predict with location and heading
- `evaluate(predictions, true_labels)` - Evaluate accuracy

## Data Format

The project expects MATLAB `.mat` files with the following structure:

```
data: [2 x N x M x 2] array
  - data[0]: measurements for state |0⟩
  - data[1]: measurements for state |1⟩
  - N: number of shots
  - M: number of time points
  - 2: I and Q components
```

## Methodology

### 1. Signal Demodulation

The demodulation process extracts quantum state information from raw IQ data:

```
I_demod = Σ(I·cos(ωt) + Q·sin(ωt))
Q_demod = Σ(Q·cos(ωt) - I·sin(ωt))
```

Where ω represents the qubit frequency.

### 2. K-means Clustering

Two-cluster K-means algorithm separates |0⟩ and |1⟩ states in the IQ plane. The Calinski-Harabasz score evaluates cluster quality.

### 3. Window Optimization

Grid search over:
- Window start position: 0-100 (step 50)
- Window length: 100-200 (step 25)

Maximizes classification accuracy on test data.

### 4. Predictive Modeling

Uses branch history tables (BHT) and heading history tables (HHT) with saturating counters to predict measurement outcomes based on trajectory patterns.

## Examples

Run the example scripts:

```bash
# Library usage examples
python3 example_library_usage.py

# API usage examples (requires API server running)
python3 example_api_usage.py
```

## Results

Typical performance metrics:

- **Clustering accuracy**: 93-96% (depending on window parameters)
- **Optimal window**: 850-2650 time points
- **Best demodulation frequency**: ω₂ = 2π(6.97284 - 7) rad/sample

## Dependencies

- **numpy**: Numerical computing
- **scipy**: Scientific computing and MATLAB file I/O
- **matplotlib**: Plotting and visualization
- **scikit-learn**: Machine learning (K-means clustering)
- **flask**: Web framework for REST API (optional)
- **flask-cors**: Cross-origin resource sharing (optional)
- **jupyter**: Interactive notebook environment (optional)

## Troubleshooting

### Data file not found
Ensure `s21_data.mat` is in the project directory or provide the correct path.

### Import errors
Install all dependencies: `pip install -r requirements.txt`

### API connection refused
Check that the API server is running: `python3 api_server.py`

### Memory errors
Reduce the data range (idx1, idx2) or window size for large datasets.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Citation

If you use this code in your research, please cite:

```bibtex
@software{quantum_feedback_analysis,
  title={Quantum Feedback Analysis Toolkit},
  author={Your Name},
  year={2026},
  url={https://github.com/yourusername/quantum_feedback_analysis}
}
```

## Contact

For questions or issues, please open an issue on GitHub.

## Acknowledgments

- Quantum measurement data from superconducting qubit experiments
- Analysis techniques based on quantum state discrimination methods
- Predictive modeling inspired by branch prediction in computer architecture
