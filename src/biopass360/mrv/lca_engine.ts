/**
 * RED II / RED III Lifecycle GHG (LCA) Calculation Engine - TypeScript Implementation
 * Directive (EU) 2018/2001 & Directive (EU) 2023/2413
 */

export enum FeedstockCategory {
  UCO_ANNEX_IX_B = 'UCO_ANNEX_IX_B',
  ANIMAL_FAT_CAT_1_2 = 'ANIMAL_FAT_CAT_1_2',
  VIRGIN_RAPESEED = 'VIRGIN_RAPESEED',
  VIRGIN_PALM_OIL = 'VIRGIN_PALM_OIL',
}

export interface TransportLeg {
  readonly mode: 'road_truck' | 'sea_tanker' | 'rail';
  readonly distanceKm: number;
  readonly payloadTonnes: number;
  readonly emissionFactorGco2Tkm?: number; // default: 62.0 gCO2eq/(tonne*km)
}

export interface ProcessingInputs {
  readonly electricityKwhPerTonne: number;
  readonly gridEmissionFactorGco2Kwh: number;
  readonly naturalGasMjPerTonne: number;
  readonly gasEmissionFactorGco2Mj: number;
  readonly methanolKgPerTonne: number;
  readonly methanolEmissionFactorGco2Kg: number;
  readonly catalystKgPerTonne: number;
  readonly catalystEmissionFactorGco2Kg: number;
}

export interface LCACalculationResult {
  readonly totalEmissionGco2PerMj: number; // E
  readonly eEc: number;
  readonly eL: number;
  readonly eP: number;
  readonly eTd: number;
  readonly eU: number;
  readonly eSca: number;
  readonly eCcs: number;
  readonly eCcr: number;
  readonly fossilComparator: number; // 94.0 gCO2eq/MJ
  readonly ghgSavingsRatio: number; // (EF - E) / EF
  readonly isRedIiCompliant: boolean; // >= 65%
  readonly isRedIiiCompliant: boolean; // >= 70%
}

export class LCACalculator {
  public static readonly FOSSIL_COMPARATOR_EF_T = 94.0;
  public static readonly RED_II_MIN_SAVINGS = 0.65;
  public static readonly RED_III_MIN_SAVINGS = 0.70;
  public static readonly DEFAULT_BIODIESEL_LHV = 37.2; // MJ/kg

  /**
   * Calculates transport emissions e_td in gCO2eq / MJ
   */
  public static computeTransportEmissions(
    legs: readonly TransportLeg[],
    biodieselLhvMjPerKg = LCACalculator.DEFAULT_BIODIESEL_LHV
  ): number {
    if (legs.length === 0) return 0.0;

    let totalGco2 = 0.0;
    let totalEnergyMj = 0.0;

    for (const leg of legs) {
      const ef = leg.emissionFactorGco2Tkm ?? 62.0;
      totalGco2 += leg.distanceKm * leg.payloadTonnes * ef;
      totalEnergyMj += leg.payloadTonnes * 1000.0 * biodieselLhvMjPerKg;
    }

    return totalEnergyMj > 0 ? totalGco2 / totalEnergyMj : 0.0;
  }

  /**
   * Calculates processing emissions e_p with co-product allocation factor
   */
  public static computeProcessingEmissions(
    inputs: ProcessingInputs,
    biodieselYieldTonnes = 0.95,
    glycerinYieldTonnes = 0.10,
    glycerinLhvMjPerKg = 16.0,
    biodieselLhvMjPerKg = LCACalculator.DEFAULT_BIODIESEL_LHV
  ): number {
    const grossEmissionsGco2 =
      inputs.electricityKwhPerTonne * inputs.gridEmissionFactorGco2Kwh +
      inputs.naturalGasMjPerTonne * inputs.gasEmissionFactorGco2Mj +
      inputs.methanolKgPerTonne * inputs.methanolEmissionFactorGco2Kg +
      inputs.catalystKgPerTonne * inputs.catalystEmissionFactorGco2Kg;

    const energyBiodiesel = biodieselYieldTonnes * biodieselLhvMjPerKg;
    const energyGlycerin = glycerinYieldTonnes * glycerinLhvMjPerKg;
    const allocationFactor = energyBiodiesel / (energyBiodiesel + energyGlycerin);

    const biodieselTotalEnergyMj = biodieselYieldTonnes * 1000.0 * biodieselLhvMjPerKg;
    return (grossEmissionsGco2 * allocationFactor) / biodieselTotalEnergyMj;
  }

  /**
   * Full RED II / RED III calculation
   * E = e_ec + e_l + e_p + e_td + e_u - e_sca - e_ccs - e_ccr
   * SAVING = (E_F(t) - E) / E_F(t)
   */
  public static computeLCA(params: {
    feedstock: FeedstockCategory;
    eP: number;
    eTd: number;
    eEc?: number;
    eL?: number;
    eU?: number;
    eSca?: number;
    eCcs?: number;
    eCcr?: number;
  }): LCACalculationResult {
    // Waste/Residue rule: e_ec = 0, e_l = 0 for UCO
    const isWaste =
      params.feedstock === FeedstockCategory.UCO_ANNEX_IX_B ||
      params.feedstock === FeedstockCategory.ANIMAL_FAT_CAT_1_2;

    const actualEEc = isWaste ? 0.0 : (params.eEc ?? 35.0);
    const actualEL = isWaste ? 0.0 : (params.eL ?? 12.0);
    const actualEU = params.eU ?? 0.0;
    const actualESca = params.eSca ?? 0.0;
    const actualECcs = params.eCcs ?? 0.0;
    const actualECcr = params.eCcr ?? 0.0;

    const totalE =
      actualEEc +
      actualEL +
      params.eP +
      params.eTd +
      actualEU -
      actualESca -
      actualECcs -
      actualECcr;

    const efT = LCACalculator.FOSSIL_COMPARATOR_EF_T;
    const savingsRatio = (efT - totalE) / efT;

    return {
      totalEmissionGco2PerMj: Number(totalE.toFixed(4)),
      eEc: Number(actualEEc.toFixed(4)),
      eL: Number(actualEL.toFixed(4)),
      eP: Number(params.eP.toFixed(4)),
      eTd: Number(params.eTd.toFixed(4)),
      eU: Number(actualEU.toFixed(4)),
      eSca: Number(actualESca.toFixed(4)),
      eCcs: Number(actualECcs.toFixed(4)),
      eCcr: Number(actualECcr.toFixed(4)),
      fossilComparator: efT,
      ghgSavingsRatio: Number(savingsRatio.toFixed(4)),
      isRedIiCompliant: savingsRatio >= LCACalculator.RED_II_MIN_SAVINGS,
      isRedIiiCompliant: savingsRatio >= LCACalculator.RED_III_MIN_SAVINGS,
    };
  }
}
