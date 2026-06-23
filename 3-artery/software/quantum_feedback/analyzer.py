"""
Main analyzer module that integrates all components
"""

import numpy as np
from scipy.io import loadmat
import os

from .demodulation import Demodulator
from .clustering import StateClassifier
from .prediction import MeasurementPredictor


class QuantumFeedbackAnalyzer:
    """
    Main class for quantum feedback analysis
    Integrates demodulation, clustering, and prediction
    """

    def __init__(self, data_path='./s21_data.mat'):
        """
        Initialize analyzer

        Args:
            data_path: Path to MATLAB data file
        """
        self.data_path = data_path
        self.read_data = None
        self.read_zero_i = None
        self.read_zero_q = None
        self.read_one_i = None
        self.read_one_q = None

        # Initialize components
        self.demodulator = Demodulator()
        self.classifier = StateClassifier()
        self.predictor = MeasurementPredictor()

    def load_data(self):
        """
        Load quantum measurement data from MAT file

        Returns:
            Dictionary with data information
        """
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        self.read_data = loadmat(self.data_path)
        read_zero = self.read_data['data'][0][:][:][:]
        read_one = self.read_data['data'][1][:][:][:]
        self.read_zero_i, self.read_zero_q = read_zero[:, :, 0], read_zero[:, :, 1]
        self.read_one_i, self.read_one_q = read_one[:, :, 0], read_one[:, :, 1]

        return {
            'status': 'success',
            'data_shape': self.read_zero_i.shape,
            'qubits': self.read_data.get('qubits', []).tolist() if 'qubits' in self.read_data else [],
            'message': 'Data loaded successfully'
        }

    def analyze_clustering(self, idx1=1, idx2=2000, omega_idx=2):
        """
        Perform K-means clustering analysis

        Args:
            idx1: Start index for data slice
            idx2: End index for data slice
            omega_idx: Frequency index to use

        Returns:
            Dictionary with clustering results
        """
        if self.read_zero_i is None:
            self.load_data()

        # Demodulate
        result_zero = self.demodulator.demodulate(
            self.read_zero_i[idx1:idx2],
            self.read_zero_q[idx1:idx2],
            omega_idx
        )
        result_one = self.demodulator.demodulate(
            self.read_one_i[idx1:idx2],
            self.read_one_q[idx1:idx2],
            omega_idx
        )

        # Convert to 2D arrays
        data_zero = np.array(result_zero).T
        data_one = np.array(result_one).T

        # Fit classifier
        result = self.classifier.fit(data_zero, data_one)

        return result

    def optimize_window(self, train_idx1=0, train_idx2=1000, test_idx1=1000, test_idx2=2000):
        """
        Optimize demodulation window parameters

        Args:
            train_idx1: Training data start index
            train_idx2: Training data end index
            test_idx1: Test data start index
            test_idx2: Test data end index

        Returns:
            Dictionary with optimization results
        """
        if self.read_zero_i is None:
            self.load_data()

        best_selection = []

        for omega_idx, omega in enumerate(self.demodulator.omegas):
            acc = []

            for window_start in range(0, 100, 50):
                for window_len in range(100, 200, 25):
                    if window_start + window_len > 4096:
                        break

                    # Train
                    result_zero = self.demodulator.demodulate_window(
                        self.read_zero_i[train_idx1:train_idx2],
                        self.read_zero_q[train_idx1:train_idx2],
                        window_start, window_len, omega_idx
                    )
                    result_one = self.demodulator.demodulate_window(
                        self.read_one_i[train_idx1:train_idx2],
                        self.read_one_q[train_idx1:train_idx2],
                        window_start, window_len, omega_idx
                    )

                    data_zero = np.array(result_zero).T
                    data_one = np.array(result_one).T
                    center_zero, center_one = self.classifier.compute_centers(data_zero, data_one)

                    # Test
                    test_zero = self.demodulator.demodulate_window(
                        self.read_zero_i[test_idx1:test_idx2],
                        self.read_zero_q[test_idx1:test_idx2],
                        window_start, window_len, omega_idx
                    )
                    test_one = self.demodulator.demodulate_window(
                        self.read_one_i[test_idx1:test_idx2],
                        self.read_one_q[test_idx1:test_idx2],
                        window_start, window_len, omega_idx
                    )

                    test_data = np.vstack([np.array(test_zero).T, np.array(test_one).T])
                    test_labels = np.array([0] * len(test_zero[0]) + [1] * len(test_one[0]))

                    predictions = self.classifier.predict_with_centers(test_data, center_zero, center_one)
                    accuracy = np.sum(predictions == test_labels) / len(test_labels)

                    acc.append([window_start, window_len, float(accuracy)])

            acc_sorted = sorted(acc, key=lambda x: x[2], reverse=True)
            best_selection.append({
                'omega': float(omega),
                'omega_idx': omega_idx,
                'best_params': acc_sorted[:5]
            })

        return {
            'status': 'success',
            'optimization_results': best_selection
        }

    def predict_measurements(self, window_start=850, window_len=1800, omega_idx=2,
                           train_idx1=0, train_idx2=1000, test_idx1=1000, test_idx2=2000):
        """
        Predict quantum measurement outcomes

        Args:
            window_start: Window start position
            window_len: Window length
            omega_idx: Frequency index
            train_idx1: Training data start
            train_idx2: Training data end
            test_idx1: Test data start
            test_idx2: Test data end

        Returns:
            Dictionary with prediction results
        """
        if self.read_zero_i is None:
            self.load_data()

        # Train
        result_zero = self.demodulator.demodulate_window(
            self.read_zero_i[train_idx1:train_idx2],
            self.read_zero_q[train_idx1:train_idx2],
            window_start, window_len, omega_idx
        )
        result_one = self.demodulator.demodulate_window(
            self.read_one_i[train_idx1:train_idx2],
            self.read_one_q[train_idx1:train_idx2],
            window_start, window_len, omega_idx
        )

        data_zero = np.array(result_zero).T
        data_one = np.array(result_one).T
        center_zero, center_one = self.classifier.compute_centers(data_zero, data_one)

        # Test
        test_zero = self.demodulator.demodulate_window(
            self.read_zero_i[test_idx1:test_idx2],
            self.read_zero_q[test_idx1:test_idx2],
            window_start, window_len, omega_idx
        )
        test_one = self.demodulator.demodulate_window(
            self.read_one_i[test_idx1:test_idx2],
            self.read_one_q[test_idx1:test_idx2],
            window_start, window_len, omega_idx
        )

        test_data = np.vstack([np.array(test_zero).T, np.array(test_one).T])
        test_labels = np.array([0] * len(test_zero[0]) + [1] * len(test_one[0]))

        predictions = self.classifier.predict_with_centers(test_data, center_zero, center_one)
        accuracy = np.sum(predictions == test_labels) / len(test_labels)

        return {
            'status': 'success',
            'accuracy': float(accuracy),
            'center_zero': center_zero.tolist(),
            'center_one': center_one.tolist(),
            'predictions': predictions.tolist(),
            'true_labels': test_labels.tolist()
        }

    def get_demodulator(self):
        """Get the demodulator instance"""
        return self.demodulator

    def get_classifier(self):
        """Get the classifier instance"""
        return self.classifier

    def get_predictor(self):
        """Get the predictor instance"""
        return self.predictor
