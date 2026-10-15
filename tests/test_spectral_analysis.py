"""Unit tests for Chemometrics & NIR Adulteration Classification."""

import math
import unittest
from biopass360.spectral.chemometrics import (
    savitzky_golay_derivative1,
    standard_normal_variate,
)
from biopass360.spectral.adulteration_detector import (
    GateAction,
    SampleVerdict,
    SpectralAdulterationEngine,
)


def generate_synthetic_spectrum(
    profile: str = "authentic_uco",
) -> tuple[list[float], list[float]]:
    """Generates synthetic NIR spectrum from 900 nm to 1700 nm in 5 nm increments (161 points)."""
    wavelengths = [900.0 + i * 5.0 for i in range(161)]
    absorbance = []

    for wl in wavelengths:
        # Base oil baseline absorption
        val = 0.45 + 0.0003 * (wl - 900.0)

        # Baseline C-H aliphatic backbone (1215 nm)
        val += 0.35 * math.exp(-((wl - 1215.0) ** 2) / (2 * 15.0**2))

        # Peak 1: cis-alkene unsaturation (1205 nm)
        if profile == "palm_adulterated":
            # Palm oil is highly saturated palmitic acid (low cis-alkene absorption)
            val += 0.10 * math.exp(-((wl - 1205.0) ** 2) / (2 * 12.0**2))
        else:
            val += 0.38 * math.exp(-((wl - 1205.0) ** 2) / (2 * 12.0**2))

        # Peak 2: Moisture / Water band (1435 nm)
        if profile == "high_moisture":
            val += 0.95 * math.exp(-((wl - 1435.0) ** 2) / (2 * 18.0**2))
        else:
            val += 0.15 * math.exp(-((wl - 1435.0) ** 2) / (2 * 18.0**2))

        # Peak 3: Polar thermal decomposition products (980 nm & 1460 nm)
        if profile == "palm_adulterated":
            # Virgin oil has very low polar compounds (<5%)
            val += 0.05 * math.exp(-((wl - 1460.0) ** 2) / (2 * 20.0**2))
            val += 0.03 * math.exp(-((wl - 980.0) ** 2) / (2 * 20.0**2))
        else:
            # Genuine fried UCO has high polar compounds (15-25%)
            val += 0.55 * math.exp(-((wl - 1460.0) ** 2) / (2 * 20.0**2))
            val += 0.30 * math.exp(-((wl - 980.0) ** 2) / (2 * 20.0**2))

        # Peak 4: Free Fatty Acid carbonyl / carboxylic (1410 nm & 1720 nm)
        if profile == "high_ffa":
            val += 0.70 * math.exp(-((wl - 1720.0) ** 2) / (2 * 15.0**2))
            val += 0.50 * math.exp(-((wl - 1410.0) ** 2) / (2 * 15.0**2))
        else:
            val += 0.22 * math.exp(-((wl - 1720.0) ** 2) / (2 * 15.0**2))
            val += 0.12 * math.exp(-((wl - 1410.0) ** 2) / (2 * 15.0**2))

        absorbance.append(val)

    return wavelengths, absorbance


class TestSpectralAnalysis(unittest.TestCase):
    def test_snv_normalization_properties(self):
        """SNV normalized data must have zero mean and unit standard deviation."""
        raw = [1.2, 1.5, 1.8, 2.1, 1.9, 1.4, 1.1]
        snv = standard_normal_variate(raw)
        self.assertAlmostEqual(sum(snv) / len(snv), 0.0, places=6)
        variance = sum(x**2 for x in snv) / (len(snv) - 1)
        self.assertAlmostEqual(variance, 1.0, places=5)

    def test_savitzky_golay_derivative_length(self):
        """Derivative output length matches input length."""
        wls, raw = generate_synthetic_spectrum("authentic_uco")
        deriv = savitzky_golay_derivative1(raw, window_size=11, delta_lambda=5.0)
        self.assertEqual(len(deriv), len(raw))

    def test_authentic_uco_passes_gate(self):
        """Authentic UCO sample must yield ACCEPT gate action."""
        wls, abs_vals = generate_synthetic_spectrum("authentic_uco")
        pred = SpectralAdulterationEngine.analyze_spectrum(wls, abs_vals)
        self.assertEqual(pred.verdict, SampleVerdict.GENUINE_UCO)
        self.assertEqual(pred.gate_action, GateAction.ACCEPT)
        self.assertLess(pred.anomaly_score, 0.40)

    def test_palm_oil_adulteration_flagged(self):
        """Sample disguised with virgin palm oil must be flagged as fraud."""
        wls, abs_vals = generate_synthetic_spectrum("palm_adulterated")
        pred = SpectralAdulterationEngine.analyze_spectrum(wls, abs_vals)
        self.assertEqual(pred.verdict, SampleVerdict.PALM_OIL_ADULTERATION)
        self.assertEqual(pred.gate_action, GateAction.REJECT_FRAUD)
        self.assertGreater(pred.anomaly_score, 0.80)

    def test_high_moisture_sludge_flagged(self):
        """Water/sludge diluted sample must be flagged as contaminated."""
        wls, abs_vals = generate_synthetic_spectrum("high_moisture")
        pred = SpectralAdulterationEngine.analyze_spectrum(wls, abs_vals)
        self.assertEqual(pred.verdict, SampleVerdict.HIGH_MOISTURE_EMULSION)
        self.assertEqual(pred.gate_action, GateAction.REJECT_CONTAMINATED)


if __name__ == "__main__":
    unittest.main()
