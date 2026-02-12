from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.car_rental.utils import CAR_RENTAL_DB_PATH
from tau2.environment.db import DB

VehicleCategory = Literal["economy", "compact", "midsize", "suv", "luxury", "van"]
VehicleStatus = Literal["available", "rented", "maintenance", "reserved"]
FuelType = Literal["gasoline", "diesel", "hybrid", "electric"]
ReservationStatus = Literal["confirmed", "active", "completed", "cancelled", "no_show"]
InsuranceType = Literal["none", "basic", "premium"]
InvoiceStatus = Literal["pending", "paid", "disputed"]
LoyaltyTier = Literal["none", "silver", "gold", "platinum"]
PaymentMethodType = Literal["credit_card", "debit_card"]


class PaymentMethod(BaseModel):
    payment_method_id: str = Field(description="Unique identifier")
    type: PaymentMethodType = Field(description="Payment type")
    last_four: str = Field(description="Last four digits of card")
    brand: str = Field(description="Card brand (Visa, Mastercard, etc.)")


class Customer(BaseModel):
    customer_id: str = Field(description="Unique identifier")
    name: str = Field(description="Full name")
    email: str = Field(description="Email address")
    phone: str = Field(description="Phone number")
    driver_license_number: str = Field(description="Driver license number")
    license_expiry: str = Field(description="License expiry date (YYYY-MM-DD)")
    dob: str = Field(description="Date of birth (YYYY-MM-DD)")
    loyalty_tier: LoyaltyTier = Field(description="Loyalty program tier")
    loyalty_points: int = Field(description="Accumulated loyalty points")
    reservations: List[str] = Field(
        description="List of reservation IDs", default_factory=list
    )
    payment_methods: List[PaymentMethod] = Field(
        description="Payment methods on file", default_factory=list
    )


class Vehicle(BaseModel):
    vehicle_id: str = Field(description="Unique identifier")
    make: str = Field(description="Vehicle manufacturer")
    model: str = Field(description="Vehicle model")
    year: int = Field(description="Model year")
    category: VehicleCategory = Field(description="Vehicle category")
    license_plate: str = Field(description="License plate number")
    mileage: int = Field(description="Current mileage")
    status: VehicleStatus = Field(description="Current status")
    location_id: str = Field(description="Current location ID")
    fuel_type: FuelType = Field(description="Fuel type")
    features: List[str] = Field(
        description="Available features (gps, child_seat, roof_rack, etc.)",
        default_factory=list,
    )


class Location(BaseModel):
    location_id: str = Field(description="Unique identifier")
    name: str = Field(description="Location name")
    address: str = Field(description="Full address")
    airport_code: Optional[str] = Field(
        description="Airport code if airport location", default=None
    )
    hours: str = Field(description="Operating hours")
    phone: str = Field(description="Phone number")


class Extra(BaseModel):
    extra_id: str = Field(description="Unique identifier")
    name: str = Field(description="Extra name (gps, child_seat, etc.)")
    daily_rate: float = Field(description="Daily rate for this extra")


class Reservation(BaseModel):
    reservation_id: str = Field(description="Unique identifier")
    customer_id: str = Field(description="Customer ID")
    vehicle_category: VehicleCategory = Field(description="Requested vehicle category")
    pickup_location_id: str = Field(description="Pickup location ID")
    dropoff_location_id: str = Field(description="Dropoff location ID")
    pickup_datetime: str = Field(description="Pickup date and time (YYYY-MM-DD HH:MM)")
    dropoff_datetime: str = Field(
        description="Dropoff date and time (YYYY-MM-DD HH:MM)"
    )
    vehicle_id: Optional[str] = Field(description="Assigned vehicle ID", default=None)
    status: ReservationStatus = Field(description="Reservation status")
    insurance_type: InsuranceType = Field(description="Insurance selection")
    extras: List[str] = Field(description="List of extra IDs", default_factory=list)
    daily_rate: float = Field(description="Daily rental rate")
    total_estimate: float = Field(description="Estimated total cost")


class RentalAgreement(BaseModel):
    agreement_id: str = Field(description="Unique identifier")
    reservation_id: str = Field(description="Associated reservation ID")
    customer_id: str = Field(description="Customer ID")
    vehicle_id: str = Field(description="Rented vehicle ID")
    actual_pickup: str = Field(description="Actual pickup datetime (YYYY-MM-DD HH:MM)")
    actual_dropoff: Optional[str] = Field(
        description="Actual dropoff datetime (YYYY-MM-DD HH:MM)", default=None
    )
    fuel_level_out: float = Field(description="Fuel level at pickup (0.0-1.0)")
    fuel_level_in: Optional[float] = Field(
        description="Fuel level at return (0.0-1.0)", default=None
    )
    mileage_out: int = Field(description="Mileage at pickup")
    mileage_in: Optional[int] = Field(description="Mileage at return", default=None)
    damage_report: Optional[str] = Field(
        description="Damage report if any", default=None
    )
    final_total: Optional[float] = Field(
        description="Final total after return", default=None
    )


class InvoiceItem(BaseModel):
    description: str = Field(description="Line item description")
    amount: float = Field(description="Line item amount")
    category: str = Field(
        description="Category (rental/insurance/fuel/extra/damage/late_fee/one_way)"
    )


class Invoice(BaseModel):
    invoice_id: str = Field(description="Unique identifier")
    customer_id: str = Field(description="Customer ID")
    agreement_id: str = Field(description="Associated rental agreement ID")
    line_items: List[InvoiceItem] = Field(description="Invoice line items")
    subtotal: float = Field(description="Subtotal before taxes")
    taxes: float = Field(description="Tax amount")
    total: float = Field(description="Total amount")
    status: InvoiceStatus = Field(description="Invoice status")
    payment_method_id: Optional[str] = Field(
        description="Payment method used", default=None
    )


class CarRentalDB(DB):
    """Top-level car rental database."""

    customers: Dict[str, Customer] = Field(description="Customers indexed by ID")
    vehicles: Dict[str, Vehicle] = Field(description="Vehicles indexed by ID")
    locations: Dict[str, Location] = Field(description="Locations indexed by ID")
    reservations: Dict[str, Reservation] = Field(
        description="Reservations indexed by ID"
    )
    rental_agreements: Dict[str, RentalAgreement] = Field(
        description="Rental agreements indexed by ID"
    )
    invoices: Dict[str, Invoice] = Field(description="Invoices indexed by ID")
    extras: Dict[str, Extra] = Field(description="Available extras indexed by ID")

    def get_statistics(self) -> dict[str, Any]:
        """Return counts for each entity collection."""
        return {
            "num_customers": len(self.customers),
            "num_vehicles": len(self.vehicles),
            "num_locations": len(self.locations),
            "num_reservations": len(self.reservations),
            "num_rental_agreements": len(self.rental_agreements),
            "num_invoices": len(self.invoices),
            "num_extras": len(self.extras),
        }


def get_db() -> CarRentalDB:
    return CarRentalDB.load(CAR_RENTAL_DB_PATH)
