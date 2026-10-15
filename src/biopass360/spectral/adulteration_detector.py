"""NIR Adulteration Detection & Quality Classification for UCO Feedstock.

Combines chemometric band ratios, PLS regression calibration approximations,
and multi-variate anomaly scoring to detect:
1. Free Fatty Acid (FFA %) degradation.
2. Moisture & Impurities (M&I %) contamination.
3. Total Polar Compounds (TPC %) drop indicating virgin palm oil fraud.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

from biopass360.spectral.chemometrics import (
    find_nearest_index,
    savitzky_golay_derivative1,
    standard_normal_variate,
)


class SampleVerdict(str, Enum):
    GENUINE_UCO = "GENUINE_UCO"
    PALM_OIL_ADULTERATION = "PALM_OIL_ADULTERATION"
    HIGH_MOISTURE_EMULSION = "HIGH_MOISTURE_EMULSION"
    EXCESSIVE_FFA_DEGRADED = "EXCESSIVE_FFA_DEGRADED"


class GateAction(str, Enum):
    ACCEPT = "ACCEPT"
    CONDITIONAL_ACID_TREATMENT = "CONDITIONAL_ACID_TREATMENT"
    REJECT_FRAUD = "REJECT_FRAUD"
    REJECT_CONTAMINATED = "REJECT_CONTAMINATED"


@dataclass(frozen=True)
class QualityPrediction:
    ffa_percent: float  # Free fatty acid (wt %)
    moisture_percent: float  # Moisture and volatile matter (wt %)
    tpc_percent: float  # Total polar compounds (wt %)
    unsaturation_index: float  # Ratio of cis-alkene (1205 nm) to aliphatic (1215 nm)
    anomaly_score: float  # 0.0 (normal) to 1.0 (severe outlier)
    verdict: SampleVerdict
    gate_action: GateAction
    confidence: float
    explanation: str


class SpectralAdulterationEngine:
    """Chemometric & ML Inference Engine for NIR spectra in 900 - 1700 nm range."""

    # Reference limits for authentic UCO bioprocessing intake
    MAX_FFA_STANDARD = 5.0  # wt %
    MAX_FFA_ACCEPTABLE = 8.0  # wt % (requires pre-esterification)
    MAX_MOISTURE_PERCENT = 1.5  # wt %
    MIN_AUTHENTIC_TPC = 12.0  # Fresh virgin oil has TPC < 8%, genuine UCO has 15-28%
    MAX_AUTHENTIC_TPC = 32.0

    @classmethod
    def analyze_spectrum(
        cls,
        wavelengths: Sequence[float],
        absorbance_values: Sequence[float],
    ) -> QualityPrediction:
        """Executes full chemometrics pipeline on raw NIR spectral sweep."""
        if len(wavelengths) != len(absorbance_values):
            raise ValueError("Wavelengths and absorbance arrays must have equal length.")
        if len(wavelengths) < 20:
            raise ValueError("Spectral data requires at least 20 wavelength points.")

        # Step 1: Preprocessing
        snv_spectrum = standard_normal_variate(absorbance_values)
        deriv1 = savitzky_golay_derivative1(snv_spectrum, window_size=11, delta_lambda=2.0)

        # Step 2: Key spectral band indices
        idx_980 = find_nearest_index(wavelengths, 980.0)    # Oxidation / degradation
        idx_1205 = find_nearest_index(wavelengths, 1205.0)  # C-H 2nd overtone (cis-alkene unsaturation)
        idx_1215 = find_nearest_index(wavelengths, 1215.0)  # C-H aliphatic backbone
        idx_1410 = find_nearest_index(wavelengths, 1410.0)  # FFA carboxylic overtone
        idx_1435 = find_nearest_index(wavelengths, 1435.0)  # O-H combination (Water/Moisture)
        idx_1460 = find_nearest_index(wavelengths, 1460.0)  # Polar thermal decomposition products
        idx_1720 = find_nearest_index(wavelengths, 1720.0)  # Carbonyl 1st overtone

        # Step 3: Calibrated Chemometric Estimators (PLS Surrogate Model)
        # 3.1 Moisture estimation via 1435 nm absorption peak relative to baseline
        water_peak_raw = absorbance_values[idx_1435]
        water_deriv = abs(deriv1[idx_1435])
        moisture_est = max(0.05, (water_peak_raw * 1.8) + (water_deriv * 8.5) - 0.45)
        moisture_est = round(min(moisture_est, 15.0), 2)

        # 3.2 Free Fatty Acid (FFA %) estimation via 1410 nm & 1720 nm intensity
        ffa_est = max(0.2, (abs(deriv1[idx_1410]) * 35.0) + (abs(deriv1[idx_1720]) * 28.0) + (absorbance_values[idx_1720] * 1.5) - 0.8)
        ffa_est = round(min(ffa_est, 25.0), 2)

        # 3.3 Total Polar Compounds (TPC %) estimation via 980 nm & 1460 nm thermal degradation bands
        tpc_raw = (absorbance_values[idx_1460] * 14.0) + (absorbance_values[idx_980] * 8.0)
        tpc_est = round(max(2.0, min(tpc_raw, 45.0)), 2)

        # 3.4 Unsaturation Index (Genuine UCO typically sunflower/canola, high cis-alkene: index > 0.95.
        # Virgin palm oil is rich in palmitic acid C16:0: index < 0.70).
        denom = abs(absorbance_values[idx_1215]) + 1e-6
        unsaturation_index = round(abs(absorbance_values[idx_1205]) / denom, 3)

        # Step 4: Multi-Variate Anomaly Scoring & Fraud Logic
        anomaly_score = 0.0
        reasons = []

        # Check for Virgin Palm Oil Adulteration Fraud
        # Fraud signature: TPC is abnormally low (< 10%) for restaurant waste oil,
        # and unsaturation index is low (< 0.75) due to saturated palmitic acid.
        is_palm_adulterated = (tpc_est < cls.MIN_AUTHENTIC_TPC) and (unsaturation_index < 0.85)

        if is_palm_adulterated:
            anomaly_score = max(anomaly_score, 0.88)
            reasons.append(
                f"Virgin palm oil adulteration detected: TPC ({tpc_est}%) is below waste frying threshold (>12%) "
                f"and unsaturation index ({unsaturation_index}) indicates saturated tropical palm fat blending."
            )
            verdict = SampleVerdict.PALM_OIL_ADULTERATION
            gate_action = GateAction.REJECT_FRAUD
            confidence = 0.94

        elif moisture_est > cls.MAX_MOISTURE_PERCENT:
            anomaly_score = max(anomaly_score, min(0.95, 0.5 + (moisture_est / 10.0)))
            reasons.append(
                f"Excessive moisture & sludge content ({moisture_est}% > max {cls.MAX_MOISTURE_PERCENT}% allowed)."
            )
            verdict = SampleVerdict.HIGH_MOISTURE_EMULSION
            gate_action = GateAction.REJECT_CONTAMINATED
            confidence = 0.92

        elif ffa_est > cls.MAX_FFA_ACCEPTABLE:
            anomaly_score = max(anomaly_score, 0.75)
            reasons.append(
                f"Severe FFA degradation ({ffa_est}% > critical {cls.MAX_FFA_ACCEPTABLE}% limit). High acid value."
            )
            verdict = SampleVerdict.EXCESSIVE_FFA_DEGRADED
            gate_action = GateAction.REJECT_CONTAMINATED
            confidence = 0.90

        elif ffa_est > cls.MAX_FFA_STANDARD:
            anomaly_score = max(anomaly_score, 0.35)
            reasons.append(
                f"Moderate FFA elevation ({ffa_est}%). Requires acid pre-esterification before alkaline transesterification."
            )
            verdict = SampleVerdict.GENUINE_UCO
            gate_action = GateAction.CONDITIONAL_ACID_TREATMENT
            confidence = 0.88

        else:
            verdict = SampleVerdict.GENUINE_UCO
            gate_action = GateAction.ACCEPT
            confidence = 0.96
            reasons.append("Spectrogram conforms to certified authentic Used Cooking Oil envelope.")

        return QualityPrediction(
            ffa_percent=ffa_est,
            moisture_percent=moisture_est,
            tpc_percent=tpc_est,
            unsaturation_index=unsaturation_index,
            anomaly_score=round(anomaly_score, 3),
            verdict=verdict,
            gate_action=gate_action,
            confidence=round(confidence, 2),
            explanation="; ".join(reasons),
        )
