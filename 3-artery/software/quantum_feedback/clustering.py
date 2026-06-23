"""
Clustering module for quantum state classification
"""

import numpy as np
from sklearn.cluster import KMeans
from sklearn import metrics


class StateClassifier:
    """Classifies quantum states using clustering algorithms"""

    def __init__(self, n_clusters=2):
        """
        Initialize classifier

        Args:
            n_clusters: Number of clusters (default: 2 for |0⟩ and |1⟩)
        """
        self.n_clusters = n_clusters
        self.kmeans = None
        self.centers = None

    def fit(self, data_zero, data_one):
        """
        Fit classifier on labeled training data

        Args:
            data_zero: Demodulated data for |0⟩ state [N x 2]
            data_one: Demodulated data for |1⟩ state [M x 2]

        Returns:
            Dictionary with fit results
        """
        # Combine data
        data = np.vstack([data_zero, data_one])
        labels = np.array([0] * len(data_zero) + [1] * len(data_one))

        # Fit K-means
        self.kmeans = KMeans(n_clusters=self.n_clusters, random_state=0)
        self.kmeans.fit(data)
        self.centers = self.kmeans.cluster_centers_

        # Calculate metrics
        score = metrics.calinski_harabasz_score(data, self.kmeans.labels_)
        accuracy = metrics.accuracy_score(labels, self.kmeans.labels_)

        return {
            'calinski_harabasz_score': float(score),
            'accuracy': float(accuracy),
            'centers': self.centers.tolist(),
            'labels': self.kmeans.labels_.tolist()
        }

    def predict(self, data):
        """
        Predict quantum state labels

        Args:
            data: Demodulated data [N x 2]

        Returns:
            Array of predicted labels
        """
        if self.kmeans is None:
            raise ValueError("Classifier must be fitted before prediction")

        return self.kmeans.predict(data)

    def predict_with_centers(self, data, center_zero, center_one):
        """
        Predict using pre-computed cluster centers (distance-based)

        Args:
            data: Demodulated data [N x 2]
            center_zero: Center for |0⟩ state
            center_one: Center for |1⟩ state

        Returns:
            Array of predicted labels
        """
        predictions = np.zeros(len(data))

        for i, point in enumerate(data):
            dist_zero = np.linalg.norm(point - center_zero)
            dist_one = np.linalg.norm(point - center_one)
            predictions[i] = 0 if dist_zero < dist_one else 1

        return predictions

    def evaluate(self, data, true_labels):
        """
        Evaluate classifier performance

        Args:
            data: Demodulated data [N x 2]
            true_labels: Ground truth labels

        Returns:
            Dictionary with evaluation metrics
        """
        predictions = self.predict(data)
        accuracy = metrics.accuracy_score(true_labels, predictions)

        return {
            'accuracy': float(accuracy),
            'predictions': predictions.tolist(),
            'true_labels': true_labels.tolist()
        }

    def compute_centers(self, data_zero, data_one):
        """
        Compute cluster centers from labeled data

        Args:
            data_zero: Data for |0⟩ state
            data_one: Data for |1⟩ state

        Returns:
            Tuple of (center_zero, center_one)
        """
        center_zero = np.mean(data_zero, axis=0)
        center_one = np.mean(data_one, axis=0)

        return center_zero, center_one
