"""Unit tests for RED II / RED III LCA Engine (Kent Beck TDD Discipline)."""

import unittest
from biopass360.mrv.lca_engine import (
    CoProductAllocation,
    FeedstockCategory,
    LCACalculator,
    ProcessingInputs,
    TransportLeg,
)


class TestLCACalculator(unittest.TestCase):
    def test_uco_waste_zero_upstream_emissions(self):
        """RED II Annex V Part C Para 18: e_ec and e_l must be 0 for UCO."""
        result = LCACalculator.compute_lca(
            feedstock=FeedstockCategory.UCO_ANNEX_IX_B,
            e_p=12.5,
            e_td=2.5,
            e_ec=45.0,  # Should be overridden to 0.0
            e_l=15.0,   # Should be overridden to 0.0
        )
        self.assertEqual(result.e_ec, 0.0)
        self.assertEqual(result.e_l, 0.0)
        self.assertEqual(result.total_emission_gco2_per_mj, 15.0)

    def test_ghg_savings_ratio_and_compliance(self):
        """Calculates SAVING = (94.0 - E) / 94.0 and checks RED II (65%) & RED III (70%) thresholds."""
        # Case A: Typical efficient UCO biodiesel (E = 14.1 gCO2eq/MJ -> 85.0% saving)
        res_compliant = LCACalculator.compute_lca(
            feedstock=FeedstockCategory.UCO_ANNEX_IX_B,
            e_p=11.5,
            e_td=2.6,
        )
        expected_saving = (94.0 - 14.1) / 94.0  # 0.85
        self.assertAlmostEqual(res_compliant.ghg_savings_ratio, round(expected_saving, 4), places=3)
        self.assertTrue(res_compliant.is_red_ii_compliant)
        self.assertTrue(res_compliant.is_red_iii_compliant)

        # Case B: High-emission process (E = 35.0 gCO2eq/MJ -> 62.7% saving - Fails RED II & III)
        res_non_compliant = LCACalculator.compute_lca(
            feedstock=FeedstockCategory.UCO_ANNEX_IX_B,
            e_p=30.0,
            e_td=5.0,
        )
        self.assertFalse(res_non_compliant.is_red_ii_compliant)
        self.assertFalse(res_non_compliant.is_red_iii_compliant)

    def test_transport_emissions_formula(self):
        """Tests e_td calculation for multi-leg logistics."""
        legs = [
            TransportLeg(mode="road_truck", distance_km=200.0, payload_tonnes=25.0, emission_factor_gco2_tkm=62.0)
        ]
        # Total emissions = 200 * 25 * 62 = 310,000 gCO2
        # Total energy = 25 * 1000 kg * 37.2 MJ/kg = 930,000 MJ
        # e_td = 310,000 / 930,000 = 0.3333 gCO2eq/MJ
        e_td = LCACalculator.compute_transport_emissions(legs)
        self.assertAlmostEqual(e_td, 0.3333, places=3)

    def test_coproduct_allocation_factor(self):
        """Verifies energy allocation factor between FAME and glycerin."""
        alloc = CoProductAllocation(
            biodiesel_yield_tonnes=0.95,
            biodiesel_lhv_mj_per_kg=37.2,
            glycerin_yield_tonnes=0.10,
            glycerin_lhv_mj_per_kg=16.0,
        )
        # FAME energy = 0.95 * 37.2 = 35.34 MJ
        # Glycerin energy = 0.10 * 16.0 = 1.60 MJ
        # Total = 36.94 MJ
        # AF = 35.34 / 36.94 = 0.95668
        self.assertAlmostEqual(alloc.biodiesel_allocation_factor, 0.9567, places=3)


if __name__ == "__main__":
    unittest.main()
