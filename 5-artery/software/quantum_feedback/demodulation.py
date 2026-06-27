"""
Demodulation module for quantum signal processing
"""

import numpy as np


class Demodulator:
    """Demodulates quantum measurement signals"""

    def __init__(self, omegas=None):
        """
        Initialize demodulator with frequencies

        Args:
            omegas: Array of demodulation frequencies (default: standard qubit frequencies)
        """
        if omegas is None:
            self.omegas = 2 * np.pi * (np.array([6.881, 6.79525, 6.97284]) - 7)
        else:
            self.omegas = omegas

    def demodulate(self, read_i, read_q, omega_idx=0, phase=0):
        """
        Demodulate IQ data at specified frequency

        Args:
            read_i: I component data [shots x time_points]
            read_q: Q component data [shots x time_points]
            omega_idx: Index of frequency to use (default: 0)
            phase: Phase offset (default: 0)

        Returns:
            Tuple of (I_demod, Q_demod) arrays
        """
        assert read_i.shape == read_q.shape, "I and Q data must have same shape"

        omega = self.omegas[omega_idx]
        ts = np.arange(0, read_i.shape[1])
        cos_ = np.array([np.cos(omega * ts + phase)] * read_i.shape[0])
        sin_ = np.array([np.sin(omega * ts + phase)] * read_i.shape[0])

        sum_i = np.sum(read_i * cos_ + read_q * sin_, axis=1)
        sum_q = np.sum(read_q * cos_ - read_i * sin_, axis=1)

        return sum_i, sum_q

    def demodulate_window(self, read_i, read_q, window_start, window_len, omega_idx=0, phase=0):
        """
        Demodulate IQ data within a specific time window

        Args:
            read_i: I component data [shots x time_points]
            read_q: Q component data [shots x time_points]
            window_start: Start index of window
            window_len: Length of window
            omega_idx: Index of frequency to use
            phase: Phase offset

        Returns:
            Tuple of (I_demod, Q_demod) arrays
        """
        read_i_window = read_i[:, window_start:window_start + window_len]
        read_q_window = read_q[:, window_start:window_start + window_len]

        return self.demodulate(read_i_window, read_q_window, omega_idx, phase)

    def demodulate_trajectory(self, read_i, read_q, window_base, window_len, window_cnt, omega_idx=0):
        """
        Demodulate signal trajectory over multiple time windows

        Args:
            read_i: I component data [shots x time_points]
            read_q: Q component data [shots x time_points]
            window_base: Base starting position
            window_len: Length of each window step
            window_cnt: Number of windows
            omega_idx: Index of frequency to use

        Returns:
            List of demodulation results for each time step
        """
        shots = read_i.shape[0]
        trajectory = [[None for _ in range(window_cnt)] for _ in range(shots)]

        for shot in range(shots):
            for tstep in range(window_cnt):
                window_end = window_base + (tstep + 1) * window_len
                result = self.demodulate(
                    read_i[shot:shot+1, window_base:window_end],
                    read_q[shot:shot+1, window_base:window_end],
                    omega_idx
                )
                trajectory[shot][tstep] = (result[0][0], result[1][0])

        return trajectory
