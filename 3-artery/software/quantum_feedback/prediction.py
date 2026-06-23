"""
Prediction module for quantum measurement outcomes
"""

import numpy as np


class MeasurementPredictor:
    """Predicts quantum measurement outcomes using pattern recognition"""

    def __init__(self, st_counters=8):
        """
        Initialize predictor with saturating counters

        Args:
            st_counters: Number of bits in saturating counter (default: 8)
        """
        self.st_counters = st_counters
        self.BHT_count = {}  # Branch History Table
        self.HHT_count = {}  # Heading History Table
        self.BHT_prob = {}
        self.HHT_prob = {}

    def train(self, location_traces, heading_traces, labels):
        """
        Train predictor on trajectory data

        Args:
            location_traces: Location trajectory data [frequencies x shots x time_steps]
            heading_traces: Heading trajectory data [frequencies x shots x time_steps]
            labels: Ground truth labels for each shot

        Returns:
            Dictionary with training statistics
        """
        self.BHT_count = {}
        self.HHT_count = {}

        # Build location history table
        for i in range(location_traces.shape[1]):  # shots
            for j in range(location_traces.shape[2] - self.st_counters):  # time steps
                # Location pattern
                register_prob = location_traces[0, i, j:j + self.st_counters]
                register_key = ''.join('1' if x != 0.0 else '0' for x in register_prob)

                if register_key not in self.BHT_count:
                    self.BHT_count[register_key] = [0, 0]

                if int(labels[i]) == 0:
                    self.BHT_count[register_key][0] += 1
                else:
                    self.BHT_count[register_key][1] += 1

                # Heading pattern
                if j > 0:
                    register_heading = heading_traces[0, i, j - 1:j + self.st_counters - 1]
                    register_heading_key = ''.join('1' if x != 0.0 else '0' for x in register_heading)

                    if register_heading_key not in self.HHT_count:
                        self.HHT_count[register_heading_key] = [0, 0]

                    if int(labels[i]) == 0:
                        self.HHT_count[register_heading_key][0] += 1
                    else:
                        self.HHT_count[register_heading_key][1] += 1

        # Compute probabilities
        self.BHT_prob = {
            key: count[1] / (count[0] + count[1])
            for key, count in self.BHT_count.items()
        }
        self.HHT_prob = {
            key: count[1] / (count[0] + count[1])
            for key, count in self.HHT_count.items()
        }

        return {
            'bht_patterns': len(self.BHT_prob),
            'hht_patterns': len(self.HHT_prob),
            'status': 'trained'
        }

    def predict(self, location_traces, heading_traces, prior_prob=0.25, set_start=0, set_len=20):
        """
        Predict measurement outcomes

        Args:
            location_traces: Location trajectory data for test set
            heading_traces: Heading trajectory data for test set
            prior_prob: Prior probability of measuring |1⟩
            set_start: Starting time point
            set_len: Number of time points to use

        Returns:
            Array of predictions and probability traces
        """
        n_shots = location_traces.shape[1]
        predictions = np.zeros(n_shots)
        prob_traces = []

        for i in range(n_shots):
            prob_per_shot = np.zeros(set_start + set_len - self.st_counters)
            pred_prob = prior_prob

            for j in range(set_start, set_start + set_len - self.st_counters):
                # Location-based update
                register_prob = location_traces[0, i, j:j + self.st_counters]
                register_key = ''.join('1' if x != 0.0 else '0' for x in register_prob)

                if register_key in self.BHT_prob:
                    observed_prob = self.BHT_prob[register_key]
                    if observed_prob == 0.0 or observed_prob == 1.0:
                        pred_prob = observed_prob
                    else:
                        # Bayesian update
                        pred_prob = (observed_prob * pred_prob) / (
                            observed_prob * pred_prob + (1 - observed_prob) * (1 - pred_prob)
                        )

                prob_per_shot[j - set_start] = pred_prob

            predictions[i] = 0 if pred_prob < 0.5 else 1
            prob_traces.append(prob_per_shot)

        return predictions, prob_traces

    def predict_with_heading(self, location_traces, heading_traces, prior_prob=0.25, set_start=0, set_len=20):
        """
        Predict with both location and heading information

        Args:
            location_traces: Location trajectory data
            heading_traces: Heading trajectory data
            prior_prob: Prior probability
            set_start: Starting time point
            set_len: Number of time points

        Returns:
            Tuple of (predictions, location_probs, heading_probs)
        """
        n_shots = location_traces.shape[1]
        predictions = np.zeros(n_shots)
        location_probs = []
        heading_probs = []

        for i in range(n_shots):
            prob_per_shot = np.zeros(set_start + set_len - self.st_counters)
            heading_per_shot = np.zeros(set_start + set_len - self.st_counters)
            pred_prob = prior_prob
            pred_heading = prior_prob

            for j in range(set_start, set_start + set_len - self.st_counters):
                # Heading update
                if j > set_start:
                    register_heading = heading_traces[0, i, j - 1:j + self.st_counters - 1]
                    register_heading_key = ''.join('1' if x != 0.0 else '0' for x in register_heading)

                    if register_heading_key in self.HHT_prob:
                        observed_prob = self.HHT_prob[register_heading_key]
                        if observed_prob == 0.0 or observed_prob == 1.0:
                            pred_heading = observed_prob
                        else:
                            pred_heading = (observed_prob * pred_heading) / (
                                observed_prob * pred_heading + (1 - observed_prob) * (1 - pred_heading)
                            )

                    heading_per_shot[j - set_start - 1] = pred_heading

                # Location update
                register_prob = location_traces[0, i, j:j + self.st_counters]
                register_key = ''.join('1' if x != 0.0 else '0' for x in register_prob)

                if register_key in self.BHT_prob:
                    observed_prob = self.BHT_prob[register_key]
                    if observed_prob == 0.0 or observed_prob == 1.0:
                        pred_prob = observed_prob
                    else:
                        pred_prob = (observed_prob * pred_prob) / (
                            observed_prob * pred_prob + (1 - observed_prob) * (1 - pred_prob)
                        )

                prob_per_shot[j - set_start] = pred_prob

            # Combine location and heading predictions
            prob_avg = (pred_prob * pred_heading) / (
                pred_prob * pred_heading + (1 - pred_prob) * (1 - pred_heading)
            ) if pred_prob > 0 and pred_heading > 0 else max(pred_prob, pred_heading)

            predictions[i] = 0 if prob_avg < 0.5 else 1
            location_probs.append(prob_per_shot)
            heading_probs.append(heading_per_shot)

        return predictions, location_probs, heading_probs

    def evaluate(self, predictions, true_labels):
        """
        Evaluate prediction accuracy

        Args:
            predictions: Predicted labels
            true_labels: Ground truth labels

        Returns:
            Dictionary with accuracy metrics
        """
        accuracy = np.sum(predictions == true_labels) / len(true_labels)

        return {
            'accuracy': float(accuracy),
            'correct': int(np.sum(predictions == true_labels)),
            'total': len(true_labels)
        }
