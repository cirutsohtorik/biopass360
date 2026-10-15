"""FastAPI Router & Service Endpoints for BioPass 360 REST API.

Provides:
- POST /api/v1/batches/intake       : Register physical delivery manifest
- POST /api/v1/spectral/verify      : Run NIR chemometrics & fraud detection
- POST /api/v1/mrv/compute-lca      : Execute RED II / RED III GHG calculations
- POST /api/v1/passports/issue      : Generate cryptographically signed Digital Passport
- GET  /api/v1/passports/{id}/verify: Public auditor & customs verification portal
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from biopass360.mrv.lca_engine import (
    CoProductAllocation,
    FeedstockCategory,
    LCACalculator,
    ProcessingInputs,
    TransportLeg,
)
from biopass360.spectral.adulteration_detector import (
    GateAction,
    SampleVerdict,
    SpectralAdulterationEngine,
)
from biopass360.passport.signer import PassportCryptoSigner


# ============================================================================
# API Request & Response DTOs
# ============================================================================

class BatchIntakeRequest(BaseModel):
    batch_reference_id: str = Field(..., example="TR-IZM-2026-B940")
    feedstock_type: FeedstockCategory = Field(FeedstockCategory.UCO_ANNEX_IX_B)
    supplier_facility_name: str = Field(..., example="Ege Atık Yağ Toplama Ltd.")
    supplier_iscc_cert: str = Field(..., example="EU-ISCC-Cert-TR2026-9912")
    origin_latitude: float = Field(38.4237, example=38.4237)
    origin_longitude: float = Field(27.1428, example=27.1428)
    origin_city: str = Field("Izmir", example="Izmir")
    gross_weight_kg: float = Field(24800.0, gt=0)
    tare_weight_kg: float = Field(14200.0, ge=0)
    measured_density_at_15c: float = Field(920.0, ge=880.0, le=940.0)


class BatchIntakeResponse(BaseModel):
    batch_id: str
    net_weight_kg: float
    calculated_volume_liters: float
    status: str
    created_at: datetime


class SpectralVerifyRequest(BaseModel):
    batch_id: str
    spectrometer_serial: str = Field("NIR-TRINAMIX-PRO-042", example="NIR-TRINAMIX-PRO-042")
    wavelengths_nm: List[float] = Field(..., description="Array of measured wavelengths in nm (900-1700)")
    absorbance_values: List[float] = Field(..., description="Measured raw absorbance values")


class SpectralVerifyResponse(BaseModel):
    batch_id: str
    ffa_percent: float
    moisture_percent: float
    tpc_percent: float
    unsaturation_index: float
    anomaly_score: float
    verdict: SampleVerdict
    gate_action: GateAction
    confidence: float
    can_issue_passport: bool
    explanation: str


class MRVComputeRequest(BaseModel):
    batch_id: str
    feedstock_type: FeedstockCategory = Field(FeedstockCategory.UCO_ANNEX_IX_B)
    transport_distance_km: float = Field(..., gt=0.0, example=180.0)
    transport_mode: str = Field("road_truck", example="road_truck")
    biorefinery_grid_kwh_per_t: float = Field(35.0, example=35.0)
    natural_gas_mj_per_t: float = Field(850.0, example=850.0)
    methanol_kg_per_t: float = Field(105.0, example=105.0)


class MRVComputeResponse(BaseModel):
    batch_id: str
    total_lca_emission_gco2_mj: float
    e_ec: float
    e_l: float
    e_p: float
    e_td: float
    ghg_savings_percent: float
    is_red_ii_compliant: bool
    is_red_iii_compliant: bool
    threshold_margin_percent: float


class IssuePassportRequest(BaseModel):
    batch_id: str
    intake_data: BatchIntakeResponse
    quality_data: SpectralVerifyResponse
    mrv_data: MRVComputeResponse


class PassportVerifyResponse(BaseModel):
    passport_id: str
    is_signature_valid: bool
    is_tamper_free: bool
    is_red_iii_compliant: bool
    ghg_savings_percent: float
    quality_verdict: str
    issued_at: datetime
    auditor_verification_status: str


# ============================================================================
# In-Memory Repository for MVP Demonstration
# ============================================================================

PASS_DB: Dict[str, Dict[str, Any]] = {}
SERVER_PRIV_HEX, SERVER_PUB_HEX = PassportCryptoSigner.generate_keypair()
SIGNER = PassportCryptoSigner(SERVER_PRIV_HEX, SERVER_PUB_HEX)


# ============================================================================
# API Service Controller Functions
# ============================================================================

def handle_batch_intake(req: BatchIntakeRequest) -> BatchIntakeResponse:
    """Processes weighbridge intake and registers candidate batch."""
    net_weight = req.gross_weight_kg - req.tare_weight_kg
    # Volume in liters: (Mass kg / Density kg/m3) * 1000
    volume_liters = (net_weight / req.measured_density_at_15c) * 1000.0

    return BatchIntakeResponse(
        batch_id=req.batch_reference_id,
        net_weight_kg=round(net_weight, 2),
        calculated_volume_liters=round(volume_liters, 2),
        status="REGISTERED_AWAITING_SPECTRAL_VERIFICATION",
        created_at=datetime.utcnow(),
    )


def handle_spectral_verify(req: SpectralVerifyRequest) -> SpectralVerifyResponse:
    """Executes chemometrics quality and adulteration check."""
    prediction = SpectralAdulterationEngine.analyze_spectrum(
        wavelengths=req.wavelengths_nm,
        absorbance_values=req.absorbance_values,
    )
    can_issue = prediction.gate_action in (GateAction.ACCEPT, GateAction.CONDITIONAL_ACID_TREATMENT)

    return SpectralVerifyResponse(
        batch_id=req.batch_id,
        ffa_percent=prediction.ffa_percent,
        moisture_percent=prediction.moisture_percent,
        tpc_percent=prediction.tpc_percent,
        unsaturation_index=prediction.unsaturation_index,
        anomaly_score=prediction.anomaly_score,
        verdict=prediction.verdict,
        gate_action=prediction.gate_action,
        confidence=prediction.confidence,
        can_issue_passport=can_issue,
        explanation=prediction.explanation,
    )


def handle_mrv_compute(req: MRVComputeRequest) -> MRVComputeResponse:
    """Executes automated RED II / RED III LCA GHG calculations."""
    leg = TransportLeg(
        mode=req.transport_mode,
        distance_km=req.transport_distance_km,
        payload_tonnes=25.0,
    )
    e_td = LCACalculator.compute_transport_emissions([leg])

    inputs = ProcessingInputs(
        electricity_kwh_per_tonne=req.biorefinery_grid_kwh_per_t,
        natural_gas_mj_per_tonne=req.natural_gas_mj_per_t,
        methanol_kg_per_tonne=req.methanol_kg_per_t,
    )
    allocation = CoProductAllocation()
    e_p = LCACalculator.compute_processing_emissions(inputs, allocation)

    result = LCACalculator.compute_lca(
        feedstock=req.feedstock_type,
        e_p=e_p,
        e_td=e_td,
    )

    savings_pct = result.ghg_savings_ratio * 100.0
    margin = savings_pct - 70.0  # Margin over RED III minimum

    return MRVComputeResponse(
        batch_id=req.batch_id,
        total_lca_emission_gco2_mj=result.total_emission_gco2_per_mj,
        e_ec=result.e_ec,
        e_l=result.e_l,
        e_p=result.e_p,
        e_td=result.e_td,
        ghg_savings_percent=round(savings_pct, 2),
        is_red_ii_compliant=result.is_red_ii_compliant,
        is_red_iii_compliant=result.is_red_iii_compliant,
        threshold_margin_percent=round(margin, 2),
    )


def handle_issue_passport(req: IssuePassportRequest) -> Dict[str, Any]:
    """Issues and cryptographically signs Digital Raw Material Passport."""
    if not req.quality_data.can_issue_passport:
        raise ValueError("Cannot issue passport: Batch failed spectroscopic quality gate.")
    if not req.mrv_data.is_red_iii_compliant:
        raise ValueError("Cannot issue passport: Batch does not meet RED III 70% GHG threshold.")

    passport_payload = {
        "passport_id": f"DPP-{req.batch_id}",
        "schema_version": "1.0.0",
        "issued_at": datetime.utcnow().isoformat(),
        "feedstock_type": "ANNEX_IX_B_UCO",
        "batch_reference": req.batch_id,
        "physical": {
            "net_weight_kg": req.intake_data.net_weight_kg,
            "volume_liters": req.intake_data.calculated_volume_liters,
        },
        "quality": {
            "ffa_percent": req.quality_data.ffa_percent,
            "moisture_percent": req.quality_data.moisture_percent,
            "tpc_percent": req.quality_data.tpc_percent,
            "verdict": req.quality_data.verdict.value,
        },
        "mrv": {
            "total_emission_gco2_mj": req.mrv_data.total_lca_emission_gco2_mj,
            "ghg_savings_percent": req.mrv_data.ghg_savings_percent,
            "is_red_iii_compliant": req.mrv_data.is_red_iii_compliant,
        },
    }

    signed_passport = SIGNER.sign_passport(passport_payload)
    PASS_DB[signed_passport["passport_id"]] = signed_passport
    return signed_passport


def handle_verify_passport(passport_id: str) -> PassportVerifyResponse:
    """Public auditor and customs verification."""
    passport = PASS_DB.get(passport_id)
    if not passport:
        raise KeyError(f"Passport {passport_id} not found in registry.")

    is_valid = PassportCryptoSigner.verify_passport(passport)

    return PassportVerifyResponse(
        passport_id=passport_id,
        is_signature_valid=is_valid,
        is_tamper_free=is_valid,
        is_red_iii_compliant=passport["mrv"]["is_red_iii_compliant"],
        ghg_savings_percent=passport["mrv"]["ghg_savings_percent"],
        quality_verdict=passport["quality"]["verdict"],
        issued_at=datetime.fromisoformat(passport["issued_at"]),
        auditor_verification_status="VERIFIED_COMPLIANT" if is_valid else "TAMPERED_INVALID",
    )
