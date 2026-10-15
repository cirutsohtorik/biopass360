"""Chemometrics Preprocessing Engine for BioPass 360 NIR Spectra.

Implements:
1. Standard Normal Variate (SNV) transformation (removes optical scatter/path length differences).
2. Savitzky-Golay 1st derivative filtering (removes baseline shift, enhances overlapping absorption peaks).
3. Critical spectral feature extraction at key hydrocarbon, moisture, and carbonyl absorption bands.
"""

import math
from typing import Sequence


def standard_normal_variate(spectrum: Sequence[float]) -> list[float]:
    """Applies Standard Normal Variate (SNV) normalization.
    
    x_snv = (x - mean) / std_dev
    """
    n = len(spectrum)
    if n == 0:
        return []
    mean_val = sum(spectrum) / n
    variance = sum((x - mean_val) ** 2 for x in spectrum) / (n - 1 if n > 1 else 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0.0:
        return [0.0] * n

    return [(x - mean_val) / std_dev for x in spectrum]


def savitzky_golay_derivative1(
    spectrum: Sequence[float],
    window_size: int = 11,
    delta_lambda: float = 2.0,
) -> list[float]:
    """Computes Savitzky-Golay 1st derivative for smoothing and baseline correction.
    
    Uses fixed precomputed convolution weights for window_size=11, polynomial degree 2.
    Weights for 1st derivative (unnormalized):
    [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    Normalization divisor = sum(i^2) * delta_lambda = 110 * delta_lambda.
    """
    if len(spectrum) < window_size:
        raise ValueError(f"Spectrum length {len(spectrum)} is shorter than window {window_size}")

    weights = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    norm_factor = 110.0 * delta_lambda
    half_w = window_size // 2

    smoothed_deriv = [0.0] * len(spectrum)

    # Edge reflection handling
    padded = (
        [spectrum[0]] * half_w
        + list(spectrum)
        + [spectrum[-1]] * half_w
    )

    for i in range(len(spectrum)):
        window = padded[i : i + window_size]
        conv_sum = sum(w * val for w, val in zip(weights, window))
        smoothed_deriv[i] = conv_sum / norm_factor

    return smoothed_deriv


def find_nearest_index(wavelengths: Sequence[float], target_wavelength: float) -> int:
    """Finds index of closest wavelength in nanometers."""
    best_idx = 0
    best_diff = abs(wavelengths[0] - target_wavelength)
    for idx, wl in enumerate(wavelengths):
        diff = abs(wl - target_wavelength)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx
    return best_idx
