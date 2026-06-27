"""
Example: Using the quantum_feedback library directly
"""

from quantum_feedback import QuantumFeedbackAnalyzer, Demodulator, StateClassifier
import numpy as np

def example_basic_usage():
    """Basic usage example"""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)

    # Initialize analyzer
    analyzer = QuantumFeedbackAnalyzer(data_path='./s21_data.mat')

    # Load data
    print("\n1. Loading data...")
    result = analyzer.load_data()
    print(f"   Data shape: {result['data_shape']}")

    # Perform clustering
    print("\n2. Clustering analysis...")
    cluster_result = analyzer.analyze_clustering(idx1=1, idx2=2000, omega_idx=2)
    print(f"   Accuracy: {cluster_result['accuracy']:.4f}")
    print(f"   Score: {cluster_result['calinski_harabasz_score']:.2f}")

    # Predict measurements
    print("\n3. Predicting measurements...")
    pred_result = analyzer.predict_measurements(window_start=850, window_len=1800)
    print(f"   Prediction accuracy: {pred_result['accuracy']:.4f}")


def example_using_components():
    """Example using individual components"""
    print("\n" + "=" * 60)
    print("Example 2: Using Individual Components")
    print("=" * 60)

    # Load data
    from scipy.io import loadmat
    read_data = loadmat('./s21_data.mat')
    read_zero = read_data['data'][0][:][:][:]
    read_one = read_data['data'][1][:][:][:]
    read_zero_i, read_zero_q = read_zero[:, :, 0], read_zero[:, :, 1]
    read_one_i, read_one_q = read_one[:, :, 0], read_one[:, :, 1]

    # 1. Demodulation
    print("\n1. Using Demodulator...")
    demod = Demodulator()
    result_zero = demod.demodulate(read_zero_i[0:100], read_zero_q[0:100], omega_idx=2)
    result_one = demod.demodulate(read_one_i[0:100], read_one_q[0:100], omega_idx=2)
    print(f"   Demodulated {len(result_zero[0])} shots for each state")

    # 2. Classification
    print("\n2. Using StateClassifier...")
    classifier = StateClassifier()
    data_zero = np.array(result_zero).T
    data_one = np.array(result_one).T
    fit_result = classifier.fit(data_zero, data_one)
    print(f"   Classification accuracy: {fit_result['accuracy']:.4f}")

    # 3. Compute centers
    center_zero, center_one = classifier.compute_centers(data_zero, data_one)
    print(f"   Center |0⟩: [{center_zero[0]:.2f}, {center_zero[1]:.2f}]")
    print(f"   Center |1⟩: [{center_one[0]:.2f}, {center_one[1]:.2f}]")


def example_window_optimization():
    """Example of window optimization"""
    print("\n" + "=" * 60)
    print("Example 3: Window Optimization")
    print("=" * 60)

    analyzer = QuantumFeedbackAnalyzer(data_path='./s21_data.mat')
    analyzer.load_data()

    print("\nOptimizing window parameters...")
    print("(This may take a few seconds...)")

    result = analyzer.optimize_window(
        train_idx1=0, train_idx2=1000,
        test_idx1=1000, test_idx2=2000
    )

    print("\nTop 3 configurations for each frequency:")
    for omega_result in result['optimization_results']:
        print(f"\nOmega index {omega_result['omega_idx']}:")
        for i, params in enumerate(omega_result['best_params'][:3]):
            print(f"  {i+1}. start={params[0]}, len={params[1]}, acc={params[2]:.4f}")


def example_custom_demodulation():
    """Example with custom demodulation frequencies"""
    print("\n" + "=" * 60)
    print("Example 4: Custom Demodulation Frequencies")
    print("=" * 60)

    # Custom frequencies
    custom_omegas = 2 * np.pi * np.array([0.1, 0.2, 0.3])
    demod = Demodulator(omegas=custom_omegas)

    print(f"\nUsing custom frequencies: {custom_omegas}")
    print("Demodulator initialized with custom omegas")


if __name__ == "__main__":
    try:
        # Run examples
        example_basic_usage()
        example_using_components()
        example_window_optimization()
        example_custom_demodulation()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except FileNotFoundError:
        print("\nError: s21_data.mat not found")
        print("Please place the data file in the current directory")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
