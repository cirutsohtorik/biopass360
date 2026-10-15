"""Mock NIR Spectrometer Hardware Emulator for BioPass 360 Gate Intake.

Simulates portable handheld NIR spectrometer (e.g., trinamiX / TI DLP NIRscan Nano).
Emits 900 - 1700 nm spectral sweeps across different quality scenarios:
- Authentic UCO
- Palm Oil Adulteration (20% blend)
- High Moisture Sludge
- High FFA Degradation
"""

import math
import random
from typing import Dict, List, Tuple


class MockNIRSensor:
    def __init__(self, device_serial: str = "NIR-NANO-TRINAMIX-089"):
        self.device_serial = device_serial
        self.wavelengths = [900.0 + i * 5.0 for i in range(161)]  # 900 to 1700 nm

    def scan_sample(self, scenario: str = "authentic_uco", noise_level: float = 0.005) -> Dict[str, Any]:
        """Simulates optical scan of an oil cuvette."""
        absorbance = []
        for wl in self.wavelengths:
            val = 0.45 + 0.0003 * (wl - 900.0)
            val += 0.35 * math.exp(-((wl - 1215.0) ** 2) / (2 * 15.0**2))

            if scenario == "palm_adulterated":
                val += 0.10 * math.exp(-((wl - 1205.0) ** 2) / (2 * 12.0**2))
                val += 0.05 * math.exp(-((wl - 1460.0) ** 2) / (2 * 20.0**2))
                val += 0.03 * math.exp(-((wl - 980.0) ** 2) / (2 * 20.0**2))
            else:
                val += 0.38 * math.exp(-((wl - 1205.0) ** 2) / (2 * 12.0**2))
                val += 0.55 * math.exp(-((wl - 1460.0) ** 2) / (2 * 20.0**2))
                val += 0.30 * math.exp(-((wl - 980.0) ** 2) / (2 * 20.0**2))

            if scenario == "high_moisture":
                val += 0.95 * math.exp(-((wl - 1435.0) ** 2) / (2 * 18.0**2))
            else:
                val += 0.15 * math.exp(-((wl - 1435.0) ** 2) / (2 * 18.0**2))

            if scenario == "high_ffa":
                val += 0.70 * math.exp(-((wl - 1720.0) ** 2) / (2 * 15.0**2))
                val += 0.50 * math.exp(-((wl - 1410.0) ** 2) / (2 * 15.0**2))
            else:
                val += 0.22 * math.exp(-((wl - 1720.0) ** 2) / (2 * 15.0**2))
                val += 0.12 * math.exp(-((wl - 1410.0) ** 2) / (2 * 15.0**2))

            # Add sensor Gaussian dark noise
            noise = random.gauss(0, noise_level)
            absorbance.append(round(val + noise, 5))

        return {
            "device_serial": self.device_serial,
            "scenario": scenario,
            "wavelengths_nm": self.wavelengths,
            "absorbance": absorbance,
        }
