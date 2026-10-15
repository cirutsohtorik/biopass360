"""RED II / RED III Lifecycle Greenhouse Gas (LCA) Calculation Engine for BioPass 360.

Directive (EU) 2018/2001 (RED II) Annex V & Directive (EU) 2023/2413 (RED III).
Standard formula:
    E = e_ec + e_l + e_p + e_td + e_u - e_sca - e_ccs - e_ccr
    SAVING = (E_F(t) - E) / E_F(t)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FeedstockCategory(str, Enum):
    UCO_ANNEX_IX_B = "UCO_ANNEX_IX_B"  # Used Cooking Oil (Waste & Residue)
    ANIMAL_FAT_CAT_1_2 = "ANIMAL_FAT_CAT_1_2"  # Category 1 & 2 Animal Fats
    VIRGIN_RAPESEED = "VIRGIN_RAPESEED"
    VIRGIN_PALM_OIL = "VIRGIN_PALM_OIL"


@dataclass(frozen=True)
class TransportLeg:
    """Represents a transport leg in the supply chain."""
    mode: str  # 'road_truck', 'sea_tanker', 'rail'
    distance_km: float
    payload_tonnes: float
    # Emission factor: gCO2eq / (tonne * km)
    # Default road truck (40t articulated): ~62 gCO2eq/(tonne*km) (GREET/BioGrace)
    emission_factor_gco2_tkm: float = 62.0


@dataclass(frozen=True)
class ProcessingInputs:
    """Physical inputs for transesterification per tonne of feedstock."""
    electricity_kwh_per_tonne: float = 35.0
    grid_emission_factor_gco2_kwh: float = 440.0  # Turkish national grid factor avg
    natural_gas_mj_per_tonne: float = 850.0
    gas_emission_factor_gco2_mj: float = 56.1  # Natural gas combustion
    methanol_kg_per_tonne: float = 105.0
    methanol_emission_factor_gco2_kg: float = 1540.0  # Fossil methanol
    catalyst_kg_per_tonne: float = 12.0  # Sodium methylate or KOH
    catalyst_emission_factor_gco2_kg: float = 2100.0


@dataclass(frozen=True)
class CoProductAllocation:
    """Energy-based co-product allocation (Annex V Part C)."""
    biodiesel_yield_tonnes: float = 0.95
    biodiesel_lhv_mj_per_kg: float = 37.2
    glycerin_yield_tonnes: float = 0.10
    glycerin_lhv_mj_per_kg: float = 16.0

    @property
    def biodiesel_allocation_factor(self) -> float:
        energy_biodiesel = self.biodiesel_yield_tonnes * self.biodiesel_lhv_mj_per_kg
        energy_glycerin = self.glycerin_yield_tonnes * self.glycerin_lhv_mj_per_kg
        total_energy = energy_biodiesel + energy_glycerin
        if total_energy == 0.0:
            return 1.0
        return energy_biodiesel / total_energy


@dataclass(frozen=True)
class LCACalculationResult:
    total_emission_gco2_per_mj: float
    e_ec: float
    e_l: float
    e_p: float
    e_td: float
    e_u: float
    e_sca: float
    e_ccs: float
    e_ccr: float
    fossil_comparator: float
    ghg_savings_ratio: float
    is_red_ii_compliant: bool  # >= 65% threshold (post-2021)
    is_red_iii_compliant: bool  # >= 70% threshold (RED III / 2026)


class LCACalculator:
    # Standard RED II / RED III Fossil Fuel Comparator (gCO2eq / MJ)
    FOSSIL_COMPARATOR_EF_T: float = 94.0

    # Regulatory thresholds
    RED_II_MIN_SAVINGS: float = 0.65  # 65%
    RED_III_MIN_SAVINGS: float = 0.70  # 70%

    # Default LHV for FAME (Biodiesel) in MJ/kg
    DEFAULT_BIODIESEL_LHV: float = 37.2

    @classmethod
    def compute_transport_emissions(
        cls,
        legs: list[TransportLeg],
        biodiesel_lhv_mj_per_kg: float = DEFAULT_BIODIESEL_LHV,
    ) -> float:
        """Calculates e_td in gCO2eq / MJ of biofuel produced.
        
        Formula:
            total_transport_gco2 = sum(distance_km * payload_tonnes * EF_tkm)
            total_energy_mj = sum(payload_tonnes * 1000 kg/t * LHV)
            e_td = total_transport_gco2 / total_energy_mj
        """
        if not legs:
            return 0.0

        total_emissions_gco2 = 0.0
        total_energy_mj = 0.0

        for leg in legs:
            leg_gco2 = leg.distance_km * leg.payload_tonnes * leg.emission_factor_gco2_tkm
            leg_energy_mj = leg.payload_tonnes * 1000.0 * biodiesel_lhv_mj_per_kg
            total_emissions_gco2 += leg_gco2
            total_energy_mj += leg_energy_mj

        if total_energy_mj <= 0:
            return 0.0

        return total_emissions_gco2 / total_energy_mj

    @classmethod
    def compute_processing_emissions(
        cls,
        inputs: ProcessingInputs,
        allocation: CoProductAllocation,
        biodiesel_lhv_mj_per_kg: float = DEFAULT_BIODIESEL_LHV,
    ) -> float:
        """Calculates e_p allocated to biodiesel in gCO2eq / MJ.
        
        Per tonne of feedstock processed:
        - Electricity: kWh * EF_el
        - Heat / NG: MJ * EF_gas
        - Methanol: kg * EF_methanol
        - Catalyst: kg * EF_cat
        Multiplied by co-product allocation factor (AF) and divided by (yield_kg * LHV).
        """
        gross_process_emissions_gco2 = (
            (inputs.electricity_kwh_per_tonne * inputs.grid_emission_factor_gco2_kwh)
            + (inputs.natural_gas_mj_per_tonne * inputs.gas_emission_factor_gco2_mj)
            + (inputs.methanol_kg_per_tonne * inputs.methanol_emission_factor_gco2_kg)
            + (inputs.catalyst_kg_per_tonne * inputs.catalyst_emission_factor_gco2_kg)
        )

        allocated_emissions_gco2 = gross_process_emissions_gco2 * allocation.biodiesel_allocation_factor
        biodiesel_energy_mj = allocation.biodiesel_yield_tonnes * 1000.0 * biodiesel_lhv_mj_per_kg

        if biodiesel_energy_mj <= 0:
            return 0.0

        return allocated_emissions_gco2 / biodiesel_energy_mj

    @classmethod
    def compute_lca(
        cls,
        feedstock: FeedstockCategory,
        e_p: float,
        e_td: float,
        e_ec: Optional[float] = None,
        e_l: Optional[float] = None,
        e_u: float = 0.0,
        e_sca: float = 0.0,
        e_ccs: float = 0.0,
        e_ccr: float = 0.0,
    ) -> LCACalculationResult:
        """Executes full RED II / RED III calculation.
        
        For waste/residues (UCO):
        Under RED II Annex V part C paragraph 18:
        'Emissions from the extraction or cultivation of raw materials, e_ec,
         shall be zero for wastes and residues.'
        'e_l shall be zero for wastes and residues.'
        """
        # Enforce waste zero-emission upstream rule
        if feedstock in (FeedstockCategory.UCO_ANNEX_IX_B, FeedstockCategory.ANIMAL_FAT_CAT_1_2):
            actual_e_ec = 0.0
            actual_e_l = 0.0
        else:
            actual_e_ec = e_ec if e_ec is not None else 35.0  # Virgin crop average default
            actual_e_l = e_l if e_l is not None else 12.0

        # Total emissions: E = e_ec + e_l + e_p + e_td + e_u - e_sca - e_ccs - e_ccr
        total_e = (
            actual_e_ec
            + actual_e_l
            + e_p
            + e_td
            + e_u
            - e_sca
            - e_ccs
            - e_ccr
        )

        # SAVING = (E_F(t) - E) / E_F(t)
        ef_t = cls.FOSSIL_COMPARATOR_EF_T
        saving_ratio = (ef_t - total_e) / ef_t

        is_red_ii = saving_ratio >= cls.RED_II_MIN_SAVINGS
        is_red_iii = saving_ratio >= cls.RED_III_MIN_SAVINGS

        return LCACalculationResult(
            total_emission_gco2_per_mj=round(total_e, 4),
            e_ec=round(actual_e_ec, 4),
            e_l=round(actual_e_l, 4),
            e_p=round(e_p, 4),
            e_td=round(e_td, 4),
            e_u=round(e_u, 4),
            e_sca=round(e_sca, 4),
            e_ccs=round(e_ccs, 4),
            e_ccr=round(e_ccr, 4),
            fossil_comparator=ef_t,
            ghg_savings_ratio=round(saving_ratio, 4),
            is_red_ii_compliant=is_red_ii,
            is_red_iii_compliant=is_red_iii,
        )
