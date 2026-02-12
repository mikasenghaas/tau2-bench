"""Tests for car rental domain tools."""

import pytest

from tau2.domains.car_rental.data_model import (
    CarRentalDB,
    Customer,
    Extra,
    Invoice,
    InvoiceItem,
    Location,
    PaymentMethod,
    RentalAgreement,
    Reservation,
    Vehicle,
)
from tau2.domains.car_rental.tools import CarRentalTools


@pytest.fixture
def sample_db():
    """Create a small self-contained car rental DB for testing."""
    customers = {
        "john_smith": Customer(
            customer_id="john_smith",
            name="John Smith",
            email="john.smith@gmail.com",
            phone="555-1234",
            driver_license_number="DL-123456",
            license_expiry="2027-06-15",
            dob="1990-05-20",
            loyalty_tier="gold",
            loyalty_points=2000,
            reservations=["res_smith_20251101"],
            payment_methods=[
                PaymentMethod(
                    payment_method_id="pm_john_1",
                    type="credit_card",
                    last_four="4242",
                    brand="Visa",
                )
            ],
        ),
        "jane_doe": Customer(
            customer_id="jane_doe",
            name="Jane Doe",
            email="jane.doe@yahoo.com",
            phone="555-5678",
            driver_license_number="DL-654321",
            license_expiry="2026-12-31",
            dob="2004-08-10",  # Under 25 -> age ~21
            loyalty_tier="none",
            loyalty_points=100,
            reservations=["res_doe_20251105"],
            payment_methods=[
                PaymentMethod(
                    payment_method_id="pm_jane_1",
                    type="debit_card",
                    last_four="1234",
                    brand="Mastercard",
                )
            ],
        ),
        "bob_expired": Customer(
            customer_id="bob_expired",
            name="Bob Expired",
            email="bob@mail.com",
            phone="555-9999",
            driver_license_number="DL-999999",
            license_expiry="2025-01-01",  # Expired
            dob="1985-03-15",
            loyalty_tier="silver",
            loyalty_points=500,
            reservations=[],
            payment_methods=[],
        ),
    }

    locations = {
        "downtown": Location(
            location_id="downtown",
            name="Downtown Office",
            address="123 Main St",
            airport_code=None,
            hours="Mon-Fri 7-9",
            phone="555-0101",
        ),
        "airport": Location(
            location_id="airport",
            name="Springfield Airport",
            address="1200 Airport Dr",
            airport_code="SPI",
            hours="Daily 5-11",
            phone="555-0102",
        ),
    }

    vehicles = {
        "toyota_corolla_downtown": Vehicle(
            vehicle_id="toyota_corolla_downtown",
            make="Toyota",
            model="Corolla",
            year=2024,
            category="economy",
            license_plate="ABC-1234",
            mileage=15000,
            status="available",
            location_id="downtown",
            fuel_type="gasoline",
            features=["gps", "bluetooth"],
        ),
        "bmw_5_series_airport": Vehicle(
            vehicle_id="bmw_5_series_airport",
            make="BMW",
            model="5 Series",
            year=2024,
            category="luxury",
            license_plate="LUX-5555",
            mileage=5000,
            status="available",
            location_id="airport",
            fuel_type="gasoline",
            features=["gps", "heated_seats", "sunroof"],
        ),
        "honda_crv_downtown": Vehicle(
            vehicle_id="honda_crv_downtown",
            make="Honda",
            model="CR-V",
            year=2024,
            category="suv",
            license_plate="SUV-7890",
            mileage=20000,
            status="rented",
            location_id="downtown",
            fuel_type="gasoline",
            features=["gps", "backup_camera"],
        ),
        "ford_fusion_airport": Vehicle(
            vehicle_id="ford_fusion_airport",
            make="Ford",
            model="Fusion",
            year=2024,
            category="midsize",
            license_plate="MID-3456",
            mileage=30000,
            status="available",
            location_id="airport",
            fuel_type="hybrid",
            features=["bluetooth", "cruise_control"],
        ),
    }

    reservations = {
        "res_smith_20251101": Reservation(
            reservation_id="res_smith_20251101",
            customer_id="john_smith",
            vehicle_category="economy",
            pickup_location_id="downtown",
            dropoff_location_id="downtown",
            pickup_datetime="2025-11-01 10:00",
            dropoff_datetime="2025-11-04 10:00",
            vehicle_id="toyota_corolla_downtown",
            status="confirmed",
            insurance_type="none",
            extras=[],
            daily_rate=46.75,  # economy $55 * 0.85 (gold 15% off)
            total_estimate=140.25,
        ),
        "res_doe_20251105": Reservation(
            reservation_id="res_doe_20251105",
            customer_id="jane_doe",
            vehicle_category="economy",
            pickup_location_id="downtown",
            dropoff_location_id="downtown",
            pickup_datetime="2025-11-05 09:00",
            dropoff_datetime="2025-11-07 09:00",
            vehicle_id=None,
            status="cancelled",
            insurance_type="none",
            extras=[],
            daily_rate=35.0,
            total_estimate=70.0,
        ),
        "res_smith_active": Reservation(
            reservation_id="res_smith_active",
            customer_id="john_smith",
            vehicle_category="suv",
            pickup_location_id="downtown",
            dropoff_location_id="downtown",
            pickup_datetime="2025-10-12 10:00",
            dropoff_datetime="2025-10-17 10:00",
            vehicle_id="honda_crv_downtown",
            status="active",
            insurance_type="premium",
            extras=["gps"],
            daily_rate=63.75,
            total_estimate=467.5,
        ),
    }

    rental_agreements = {
        "agr_smith_active": RentalAgreement(
            agreement_id="agr_smith_active",
            reservation_id="res_smith_active",
            customer_id="john_smith",
            vehicle_id="honda_crv_downtown",
            actual_pickup="2025-10-12 10:00",
            actual_dropoff=None,
            fuel_level_out=0.95,
            fuel_level_in=None,
            mileage_out=20000,
            mileage_in=None,
            damage_report=None,
            final_total=None,
        ),
    }

    extras = {
        "gps": Extra(extra_id="gps", name="GPS Navigation", daily_rate=12.0),
        "child_seat": Extra(extra_id="child_seat", name="Child Seat", daily_rate=10.0),
        "additional_driver": Extra(
            extra_id="additional_driver", name="Additional Driver", daily_rate=15.0
        ),
    }

    invoices = {
        "inv_test": Invoice(
            invoice_id="inv_test",
            customer_id="john_smith",
            agreement_id="agr_smith_active",
            line_items=[
                InvoiceItem(
                    description="SUV rental - 5 days",
                    amount=318.75,
                    category="rental",
                )
            ],
            subtotal=318.75,
            taxes=38.25,
            total=357.0,
            status="pending",
            payment_method_id="pm_john_1",
        ),
    }

    return CarRentalDB(
        customers=customers,
        vehicles=vehicles,
        locations=locations,
        reservations=reservations,
        rental_agreements=rental_agreements,
        invoices=invoices,
        extras=extras,
    )


@pytest.fixture
def tools(sample_db):
    return CarRentalTools(sample_db)


# ── READ Tools ──────────────────────────────────────────────────


class TestFindCustomerByName:
    def test_exact_match(self, tools):
        results = tools.find_customer_by_name("John Smith")
        assert len(results) == 1
        assert results[0].customer_id == "john_smith"

    def test_partial_match(self, tools):
        results = tools.find_customer_by_name("smith")
        assert len(results) == 1

    def test_case_insensitive(self, tools):
        results = tools.find_customer_by_name("JANE")
        assert len(results) == 1
        assert results[0].customer_id == "jane_doe"

    def test_no_match(self, tools):
        results = tools.find_customer_by_name("Nonexistent")
        assert len(results) == 0


class TestFindCustomerByEmail:
    def test_found(self, tools):
        result = tools.find_customer_by_email("john.smith@gmail.com")
        assert result.customer_id == "john_smith"

    def test_case_insensitive(self, tools):
        result = tools.find_customer_by_email("JOHN.SMITH@GMAIL.COM")
        assert result.customer_id == "john_smith"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="No customer found"):
            tools.find_customer_by_email("nobody@example.com")


class TestGetCustomerDetails:
    def test_found(self, tools):
        result = tools.get_customer_details("john_smith")
        assert result.name == "John Smith"
        assert result.loyalty_tier == "gold"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_customer_details("nonexistent")


class TestGetReservation:
    def test_found(self, tools):
        res = tools.get_reservation("res_smith_20251101")
        assert res.customer_id == "john_smith"
        assert res.status == "confirmed"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_reservation("nonexistent")


class TestSearchVehicles:
    def test_available(self, tools):
        results = tools.search_vehicles(
            "downtown", "economy", "2025-11-01", "2025-11-03"
        )
        assert len(results) == 1
        assert results[0].vehicle_id == "toyota_corolla_downtown"

    def test_no_available(self, tools):
        results = tools.search_vehicles("downtown", "suv", "2025-11-01", "2025-11-03")
        assert len(results) == 0  # honda_crv is rented

    def test_invalid_location(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.search_vehicles(
                "fake_location", "economy", "2025-11-01", "2025-11-03"
            )


class TestGetVehicleDetails:
    def test_found(self, tools):
        v = tools.get_vehicle_details("toyota_corolla_downtown")
        assert v.make == "Toyota"
        assert v.category == "economy"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_vehicle_details("nonexistent")


class TestGetLocationDetails:
    def test_found(self, tools):
        loc = tools.get_location_details("airport")
        assert loc.airport_code == "SPI"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_location_details("nonexistent")


class TestListLocations:
    def test_returns_all(self, tools):
        locations = tools.list_locations()
        assert len(locations) == 2
        ids = {loc.location_id for loc in locations}
        assert "downtown" in ids
        assert "airport" in ids


class TestListExtras:
    def test_returns_all(self, tools):
        extras = tools.list_extras()
        assert len(extras) == 3
        names = {e.name for e in extras}
        assert "GPS Navigation" in names


class TestGetInvoice:
    def test_found(self, tools):
        inv = tools.get_invoice("inv_test")
        assert inv.total == 357.0

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_invoice("nonexistent")


class TestGetRentalAgreement:
    def test_found(self, tools):
        agr = tools.get_rental_agreement("agr_smith_active")
        assert agr.actual_dropoff is None

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.get_rental_agreement("nonexistent")


class TestFindRentalAgreementsByCustomer:
    def test_found(self, tools):
        agreements = tools.find_rental_agreements_by_customer("john_smith")
        assert len(agreements) == 1
        assert agreements[0].agreement_id == "agr_smith_active"

    def test_no_agreements(self, tools):
        agreements = tools.find_rental_agreements_by_customer("jane_doe")
        assert len(agreements) == 0

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.find_rental_agreements_by_customer("nonexistent")


# ── WRITE Tools ─────────────────────────────────────────────────


class TestCreateReservation:
    def test_success(self, tools):
        res = tools.create_reservation(
            customer_id="john_smith",
            category="economy",
            pickup_location_id="downtown",
            dropoff_location_id="downtown",
            pickup_datetime="2025-12-01 10:00",
            dropoff_datetime="2025-12-03 10:00",
        )
        assert res.status == "confirmed"
        assert res.customer_id == "john_smith"
        assert res.vehicle_category == "economy"
        assert "res_smith_20251201" in res.reservation_id

    def test_invalid_customer(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.create_reservation(
                "nonexistent",
                "economy",
                "downtown",
                "downtown",
                "2025-12-01 10:00",
                "2025-12-03 10:00",
            )

    def test_luxury_underage(self, tools):
        with pytest.raises(ValueError, match="at least 25"):
            tools.create_reservation(
                "jane_doe",
                "luxury",
                "airport",
                "airport",
                "2025-12-01 10:00",
                "2025-12-03 10:00",
            )

    def test_expired_license(self, tools):
        with pytest.raises(ValueError, match="license expired"):
            tools.create_reservation(
                "bob_expired",
                "economy",
                "downtown",
                "downtown",
                "2025-12-01 10:00",
                "2025-12-03 10:00",
            )

    def test_invalid_category(self, tools):
        with pytest.raises(ValueError, match="Invalid category"):
            tools.create_reservation(
                "john_smith",
                "helicopter",
                "downtown",
                "downtown",
                "2025-12-01 10:00",
                "2025-12-03 10:00",
            )

    def test_one_way_surcharge(self, tools):
        res = tools.create_reservation(
            customer_id="john_smith",
            category="midsize",
            pickup_location_id="airport",
            dropoff_location_id="downtown",
            pickup_datetime="2025-12-01 10:00",
            dropoff_datetime="2025-12-03 10:00",
        )
        assert res.total_estimate > 0
        # Should include one-way surcharge of $75
        assert res.pickup_location_id != res.dropoff_location_id

    def test_with_insurance_and_extras(self, tools):
        res = tools.create_reservation(
            customer_id="john_smith",
            category="economy",
            pickup_location_id="downtown",
            dropoff_location_id="downtown",
            pickup_datetime="2025-12-10 10:00",
            dropoff_datetime="2025-12-12 10:00",
            insurance_type="premium",
            extras=["gps", "child_seat"],
        )
        assert res.insurance_type == "premium"
        assert "gps" in res.extras
        assert "child_seat" in res.extras


class TestModifyReservation:
    def test_modify_dates(self, tools):
        res = tools.modify_reservation(
            "res_smith_20251101",
            pickup_datetime="2025-11-02 10:00",
            dropoff_datetime="2025-11-05 10:00",
        )
        assert res.pickup_datetime == "2025-11-02 10:00"
        assert res.dropoff_datetime == "2025-11-05 10:00"

    def test_modify_insurance(self, tools):
        res = tools.modify_reservation("res_smith_20251101", insurance_type="basic")
        assert res.insurance_type == "basic"

    def test_cannot_modify_cancelled(self, tools):
        with pytest.raises(ValueError, match="Cannot modify"):
            tools.modify_reservation("res_doe_20251105", insurance_type="basic")

    def test_cannot_modify_active_insurance(self, tools):
        with pytest.raises(ValueError, match="Cannot modify"):
            tools.modify_reservation("res_smith_active", insurance_type="basic")

    def test_cannot_modify_active_dates(self, tools):
        with pytest.raises(ValueError, match="Cannot modify"):
            tools.modify_reservation(
                "res_smith_active", pickup_datetime="2025-10-13 10:00"
            )

    def test_cannot_modify_active_category(self, tools):
        with pytest.raises(ValueError, match="Cannot modify"):
            tools.modify_reservation("res_smith_active", category="economy")

    def test_modify_active_extras_allowed(self, tools):
        res = tools.modify_reservation("res_smith_active", extras=["gps", "child_seat"])
        assert sorted(res.extras) == ["child_seat", "gps"]

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.modify_reservation("nonexistent", insurance_type="basic")


class TestCancelReservation:
    def test_success(self, tools):
        res = tools.cancel_reservation("res_smith_20251101", "Changed plans")
        assert res.status == "cancelled"
        # Vehicle should be released
        assert tools.db.vehicles["toyota_corolla_downtown"].status == "available"

    def test_already_cancelled(self, tools):
        with pytest.raises(ValueError, match="Cannot cancel"):
            tools.cancel_reservation("res_doe_20251105", "Test")

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.cancel_reservation("nonexistent", "Test")


class TestExtendRental:
    def test_success(self, tools):
        agr = tools.extend_rental("agr_smith_active", "2025-10-19 10:00")
        assert agr.agreement_id == "agr_smith_active"
        # Check reservation dropoff was updated
        res = tools.db.reservations["res_smith_active"]
        assert res.dropoff_datetime == "2025-10-19 10:00"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.extend_rental("nonexistent", "2025-10-20 10:00")


class TestApplyLoyaltyDiscount:
    def test_success(self, tools):
        res = tools.apply_loyalty_discount("res_smith_20251101", 500)
        # 500 points = $50 discount
        assert tools.db.customers["john_smith"].loyalty_points == 1500
        assert res.total_estimate < 140.25

    def test_insufficient_points(self, tools):
        with pytest.raises(ValueError, match="only has"):
            tools.apply_loyalty_discount("res_smith_20251101", 5000)

    def test_invalid_points(self, tools):
        with pytest.raises(ValueError, match="positive"):
            tools.apply_loyalty_discount("res_smith_20251101", 0)

    def test_not_confirmed(self, tools):
        with pytest.raises(ValueError, match="Cannot apply"):
            tools.apply_loyalty_discount("res_doe_20251105", 50)


class TestReportDamage:
    def test_success(self, tools):
        agr = tools.report_damage("agr_smith_active", "Scratch on bumper")
        assert agr.damage_report == "Scratch on bumper"

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.report_damage("nonexistent", "Damage")


class TestIssueCredit:
    def test_success(self, tools):
        result = tools.issue_credit("john_smith", 50.0, "Service failure")
        assert "50.00" in result
        assert tools.db.customers["john_smith"].loyalty_points == 2500  # +500 pts

    def test_over_limit(self, tools):
        with pytest.raises(ValueError, match="exceeds maximum"):
            tools.issue_credit("john_smith", 250.0, "Too much")

    def test_invalid_amount(self, tools):
        with pytest.raises(ValueError, match="positive"):
            tools.issue_credit("john_smith", 0, "Zero")


class TestInitiateRoadsideAssistance:
    def test_success_premium(self, tools):
        result = tools.initiate_roadside_assistance(
            "agr_smith_active", "123 Main St", "flat_tire"
        )
        assert "No additional charge" in result
        assert "flat_tire" in result

    def test_not_found(self, tools):
        with pytest.raises(ValueError, match="not found"):
            tools.initiate_roadside_assistance("nonexistent", "Location", "issue")


# ── GENERIC Tools ───────────────────────────────────────────────


class TestCalculate:
    def test_basic(self, tools):
        assert tools.calculate("75 * 3 + 50") == "275"

    def test_invalid(self, tools):
        with pytest.raises(ValueError, match="invalid characters"):
            tools.calculate("import os")


class TestTransferToHumanAgents:
    def test_success(self, tools):
        result = tools.transfer_to_human_agents("Customer needs help")
        assert "Transfer successful" in result


# ── Assertion Helpers ───────────────────────────────────────────


class TestAssertionHelpers:
    def test_reservation_status(self, tools):
        assert tools.assert_reservation_status("res_smith_20251101", "confirmed")
        assert not tools.assert_reservation_status("res_smith_20251101", "cancelled")
        assert not tools.assert_reservation_status("nonexistent", "confirmed")

    def test_vehicle_status(self, tools):
        assert tools.assert_vehicle_status("toyota_corolla_downtown", "available")
        assert not tools.assert_vehicle_status("toyota_corolla_downtown", "rented")

    def test_reservation_exists(self, tools):
        assert tools.assert_reservation_exists("john_smith")

    def test_reservation_insurance(self, tools):
        assert tools.assert_reservation_insurance("res_smith_20251101", "none")
        assert not tools.assert_reservation_insurance("res_smith_20251101", "basic")

    def test_reservation_extras(self, tools):
        assert tools.assert_reservation_extras("res_smith_active", ["gps"])
        assert not tools.assert_reservation_extras("res_smith_active", ["child_seat"])

    def test_damage_reported(self, tools):
        assert not tools.assert_damage_reported("agr_smith_active")
        tools.report_damage("agr_smith_active", "Test damage")
        assert tools.assert_damage_reported("agr_smith_active")

    def test_reservation_category(self, tools):
        assert tools.assert_reservation_category("res_smith_20251101", "economy")
        assert not tools.assert_reservation_category("res_smith_20251101", "suv")
