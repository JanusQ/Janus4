"""
Flask REST API for Quantum Feedback Analysis
Uses the quantum_feedback library
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from quantum_feedback import QuantumFeedbackAnalyzer

app = Flask(__name__)
CORS(app)

# Initialize analyzer
analyzer = QuantumFeedbackAnalyzer()


@app.route('/')
def home():
    """API home endpoint"""
    return jsonify({
        'message': 'Quantum Feedback Analysis API',
        'version': '1.0.0',
        'library': 'quantum_feedback',
        'endpoints': {
            '/api/load': 'Load quantum measurement data',
            '/api/cluster': 'Perform K-means clustering',
            '/api/optimize': 'Optimize demodulation window',
            '/api/predict': 'Predict measurement outcomes'
        }
    })


@app.route('/api/load', methods=['POST'])
def load_data():
    """Load quantum measurement data"""
    try:
        data = request.get_json() or {}
        data_path = data.get('data_path', './s21_data.mat')
        analyzer.data_path = data_path
        result = analyzer.load_data()
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/cluster', methods=['POST'])
def cluster():
    """Perform K-means clustering"""
    try:
        data = request.get_json() or {}
        idx1 = data.get('idx1', 1)
        idx2 = data.get('idx2', 2000)
        omega_idx = data.get('omega_idx', 2)
        result = analyzer.analyze_clustering(idx1, idx2, omega_idx)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Optimize demodulation window parameters"""
    try:
        data = request.get_json() or {}
        train_idx1 = data.get('train_idx1', 0)
        train_idx2 = data.get('train_idx2', 1000)
        test_idx1 = data.get('test_idx1', 1000)
        test_idx2 = data.get('test_idx2', 2000)
        result = analyzer.optimize_window(train_idx1, train_idx2, test_idx1, test_idx2)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/predict', methods=['POST'])
def predict():
    """Predict quantum measurement outcomes"""
    try:
        data = request.get_json() or {}
        window_start = data.get('window_start', 850)
        window_len = data.get('window_len', 1800)
        omega_idx = data.get('omega_idx', 2)
        train_idx1 = data.get('train_idx1', 0)
        train_idx2 = data.get('train_idx2', 1000)
        test_idx1 = data.get('test_idx1', 1000)
        test_idx2 = data.get('test_idx2', 2000)
        result = analyzer.predict_measurements(
            window_start, window_len, omega_idx,
            train_idx1, train_idx2, test_idx1, test_idx2
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    print("Starting Quantum Feedback Analysis API...")
    print("API will be available at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
