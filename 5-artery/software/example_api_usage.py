"""
Example usage of the Quantum Feedback Analysis API
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_api():
    """Test all API endpoints"""

    print("=" * 60)
    print("Quantum Feedback Analysis API - Example Usage")
    print("=" * 60)

    # 1. Load data
    print("\n1. Loading quantum measurement data...")
    response = requests.post(f"{BASE_URL}/api/load",
                            json={"data_path": "./s21_data.mat"})
    result = response.json()
    if result['status'] == 'success':
        print(f"   ✓ Data loaded successfully")
        print(f"   Data shape: {result['data_shape']}")
        print(f"   Qubits: {result['qubits']}")
    else:
        print(f"   ✗ Error: {result['message']}")
        return

    # 2. K-means clustering
    print("\n2. Performing K-means clustering...")
    response = requests.post(f"{BASE_URL}/api/cluster",
                            json={"idx1": 1, "idx2": 2000, "omega_idx": 2})
    result = response.json()
    if result['status'] == 'success':
        print(f"   ✓ Clustering completed")
        print(f"   Calinski-Harabasz score: {result['calinski_harabasz_score']:.2f}")
        print(f"   Accuracy: {result['accuracy']:.4f}")
        print(f"   Cluster centers:")
        for i, center in enumerate(result['cluster_centers']):
            print(f"     Center {i}: [{center[0]:.2f}, {center[1]:.2f}]")
    else:
        print(f"   ✗ Error: {result['message']}")

    # 3. Window optimization
    print("\n3. Optimizing demodulation window parameters...")
    print("   (This may take a few seconds...)")
    response = requests.post(f"{BASE_URL}/api/optimize",
                            json={
                                "train_idx1": 0,
                                "train_idx2": 1000,
                                "test_idx1": 1000,
                                "test_idx2": 2000
                            })
    result = response.json()
    if result['status'] == 'success':
        print(f"   ✓ Optimization completed")
        for i, omega_result in enumerate(result['optimization_results']):
            print(f"\n   Omega {i} (ω = {omega_result['omega']:.4f}):")
            print(f"   Top 3 parameter combinations:")
            for j, params in enumerate(omega_result['best_params'][:3]):
                print(f"     {j+1}. Window start: {params[0]}, Length: {params[1]}, Accuracy: {params[2]:.4f}")
    else:
        print(f"   ✗ Error: {result['message']}")

    # 4. Prediction
    print("\n4. Predicting measurement outcomes...")
    response = requests.post(f"{BASE_URL}/api/predict",
                            json={
                                "window_start": 850,
                                "window_len": 1800,
                                "omega_idx": 2,
                                "train_idx1": 0,
                                "train_idx2": 1000,
                                "test_idx1": 1000,
                                "test_idx2": 2000
                            })
    result = response.json()
    if result['status'] == 'success':
        print(f"   ✓ Prediction completed")
        print(f"   Prediction accuracy: {result['accuracy']:.4f} ({result['accuracy']*100:.2f}%)")
        print(f"   Center |0⟩: [{result['center_zero'][0]:.2f}, {result['center_zero'][1]:.2f}]")
        print(f"   Center |1⟩: [{result['center_one'][0]:.2f}, {result['center_one'][1]:.2f}]")
        print(f"   Total predictions: {len(result['predictions'])}")
    else:
        print(f"   ✗ Error: {result['message']}")

    print("\n" + "=" * 60)
    print("API testing completed!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        # Check if API is running
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            test_api()
        else:
            print("Error: API returned unexpected status code")
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to API server")
        print("Please start the API server first:")
        print("  python3 api_server.py")
