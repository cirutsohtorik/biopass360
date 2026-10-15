"""Unit tests for Digital Raw Material Passport schema & cryptographic tampering."""

import unittest
from biopass360.passport.signer import PassportCryptoSigner, compute_sha256_hash


class TestPassportCryptoSigner(unittest.TestCase):
    def setUp(self):
        self.priv_hex, self.pub_hex = PassportCryptoSigner.generate_keypair()
        self.signer = PassportCryptoSigner(self.priv_hex, self.pub_hex)
        self.sample_passport = {
            "passport_id": "DPP-TR-IZM-2026-B001",
            "schema_version": "1.0.0",
            "feedstock_type": "ANNEX_IX_B_UCO",
            "physical": {
                "net_weight_kg": 24500.0,
                "volume_liters": 26630.43,
                "density_kg_per_m3_at_15c": 920.0,
            },
            "quality": {
                "ffa_percent": 2.4,
                "moisture_percent": 0.65,
                "tpc_percent": 18.5,
                "verdict": "GENUINE_UCO",
            },
            "mrv": {
                "total_emission_gco2_mj": 14.1,
                "ghg_savings_percent": 85.0,
                "is_red_iii_compliant": True,
            },
        }

    def test_sign_and_verify_valid_passport(self):
        """Signed passport must pass signature and hash verification."""
        signed = self.signer.sign_passport(dict(self.sample_passport))
        self.assertIn("canonical_hash", signed)
        self.assertIn("signature", signed)
        self.assertIn("qr_verification_url", signed)

        is_valid = PassportCryptoSigner.verify_passport(signed)
        self.assertTrue(is_valid)

    def test_tamper_detection(self):
        """Tampering with physical weight or GHG emission invalidates the passport."""
        signed = self.signer.sign_passport(dict(self.sample_passport))

        # Attacker secretly modifies net_weight_kg or ghg_savings_percent
        signed["physical"]["net_weight_kg"] = 30000.0

        is_valid = PassportCryptoSigner.verify_passport(signed)
        self.assertFalse(is_valid, "Tampered passport should fail verification!")


if __name__ == "__main__":
    unittest.main()
