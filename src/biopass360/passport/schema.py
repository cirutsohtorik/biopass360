"""Digital Raw Material Passport (DPP) Schema for Biofuel Feedstocks.

Compliant with EU ESPR (Ecodesign for Sustainable Products Regulation),
RED II/III mass balance chain of custody, and ISCC EU certification standards.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FeedstockClassification(str, Enum):
    ANNEX_IX_A_ADVANCED = "ANNEX_IX_A_ADVANCED"
    ANNEX_IX_B_UCO = "ANNEX_IX_B_UCO"
    ANNEX_IX_B_ANIMAL_FAT = "ANNEX_IX_B_ANIMAL_FAT"
    CONVENTIONAL_FOOD_CROP = "CONVENTIONAL_FOOD_CROP"


class GeoProvenance(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude coordinate")
    facility_name: str = Field(..., description="Name of collection hub or aggregation point")
    municipality: str = Field(..., description="City / Region, e.g. Izmir")
    country_code: str = Field("TR", min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    iscc_certificate_id: str = Field(..., description="ISCC EU certificate number of collector")


class PhysicalMetrics(BaseModel):
    volume_liters: float = Field(..., gt=0.0, description="Measured volume in liters")
    gross_weight_kg: float = Field(..., gt=0.0, description="Weighbridge gross weight in kg")
    tare_weight_kg: float = Field(..., ge=0.0, description="Weighbridge tare weight in kg")
    net_weight_kg: float = Field(..., gt=0.0, description="Net weight in kg")
    density_kg_per_m3_at_15c: float = Field(
        ...,
        ge=880.0,
        le=940.0,
        description="Standard liquid density at 15 deg C (UCO typical: 915-925 kg/m3)",
    )

    @field_validator("net_weight_kg")
    @classmethod
    def validate_net_weight(cls, v: float, info) -> float:
        gross = info.data.get("gross_weight_kg")
        tare = info.data.get("tare_weight_kg")
        if gross is not None and tare is not None:
            expected = gross - tare
            if abs(v - expected) > 1.0:
                raise ValueError(f"Net weight {v} does not match gross ({gross}) - tare ({tare})")
        return v


class SpectralQualityRecord(BaseModel):
    spectrometer_serial: str = Field(..., description="Hardware ID of portable NIR sensor")
    scan_timestamp: datetime = Field(..., description="Timestamp of gate spectroscopic scan")
    ffa_percent: float = Field(..., ge=0.0, le=100.0, description="Free fatty acid content wt %")
    moisture_percent: float = Field(..., ge=0.0, le=100.0, description="Moisture and sediment wt %")
    tpc_percent: float = Field(..., ge=0.0, le=100.0, description="Total polar compounds wt %")
    adulteration_verdict: str = Field(..., description="GENUINE_UCO, PALM_OIL_ADULTERATION, etc.")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="0.0 normal, 1.0 severe outlier")
    spectral_hash: str = Field(..., description="SHA-256 digest of 900-1700nm raw absorbance array")


class MRVEmissionMetrics(BaseModel):
    total_lca_gco2_per_mj: float = Field(..., description="E = e_ec + e_l + e_p + e_td ...")
    fossil_comparator_gco2_per_mj: float = Field(94.0, description="RED II/III baseline E_F(t)")
    ghg_savings_percent: float = Field(..., ge=0.0, le=100.0, description="SAVING %")
    is_red_ii_compliant: bool = Field(..., description="Meets RED II >=65% threshold")
    is_red_iii_compliant: bool = Field(..., description="Meets RED III >=70% threshold")
    transport_distance_km: float = Field(..., ge=0.0, description="Cumulative logistics distance")


class CustodyTransferEvent(BaseModel):
    timestamp: datetime = Field(..., description="Event timestamp (ISO 8601)")
    event_type: str = Field(..., description="COLLECTION, TRANSIT_CHECKPOINT, REFINERY_INTAKE")
    custodian_name: str = Field(..., description="Entity handling the batch")
    custodian_tax_id: str = Field(..., description="Tax/Vat registration ID")
    location_coordinates: str = Field(..., description="Lat,Long coordinate string")


class DigitalRawMaterialPassport(BaseModel):
    """Canonical Digital Product Passport model for BioPass 360."""
    passport_id: str = Field(..., description="Unique DPP ID, e.g. UCO-2026-TR-IZM-00892")
    schema_version: str = Field("1.0.0", description="BioPass 360 DPP schema version")
    issued_at: datetime = Field(default_factory=datetime.utcnow, description="Issuance timestamp")
    feedstock_type: FeedstockClassification = Field(..., description="RED II Annex IX category")
    provenance: GeoProvenance = Field(..., description="Geographical origin")
    physical: PhysicalMetrics = Field(..., description="Weight, volume, and density metrics")
    quality: SpectralQualityRecord = Field(..., description="NIR spectroscopic lab validation")
    mrv: MRVEmissionMetrics = Field(..., description="RED III GHG LCA figures")
    chain_of_custody: List[CustodyTransferEvent] = Field(default_factory=list)

    # Cryptographic integrity fields
    canonical_hash: Optional[str] = Field(None, description="SHA-256 hex digest of canonical payload")
    signature: Optional[str] = Field(None, description="Ed25519 digital signature of refinery private key")
    public_key_hex: Optional[str] = Field(None, description="Refinery verification public key")
    qr_verification_url: Optional[str] = Field(None, description="Scannable URL payload for field verification")
