import math
from datetime import datetime

from tau2.domains.car_rental.data_model import (
    CarRentalDB,
    Customer,
    Extra,
    Invoice,
    Location,
    RentalAgreement,
    Reservation,
    Vehicle,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date for all date comparisons
REFERENCE_DATE = datetime(2025, 10, 15)

# Policy constants
MIN_DRIVER_AGE = 21
LUXURY_MIN_AGE = 25
FREE_CANCEL_HOURS = 48
CANCEL_FEE = 50.0
ONE_WAY_SURCHARGE = 75.0
REFUEL_RATE_PER_GALLON = 8.0
LATE_GRACE_HOURS = 1
INSURANCE_BASIC_DAILY = 15.0
INSURANCE_PREMIUM_DAILY = 30.0
BASIC_DEDUCTIBLE = 500.0
PREMIUM_DEDUCTIBLE = 0.0
ROADSIDE_FEE = 150.0
MAX_CREDIT_AMOUNT = 200.0
LOYALTY_SILVER_DISCOUNT = 0.10
LOYALTY_GOLD_DISCOUNT = 0.15
LOYALTY_PLATINUM_DISCOUNT = 0.20
LOYALTY_POINTS_PER_DOLLAR = 10
TAX_RATE = 0.12


def _make_unique_id(base: str, existing: dict) -> str:
    """Return base if unique, else append _2, _3, etc."""
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def _customer_last(customer_id: str) -> str:
    """Extract last name component from customer_id."""
    parts = customer_id.split("_")
    return parts[-1] if parts else customer_id


def _rental_days(pickup: str, dropoff: str) -> int:
    """Calculate number of rental days (minimum 1)."""
    p = datetime.strptime(pickup, "%Y-%m-%d %H:%M")
    d = datetime.strptime(dropoff, "%Y-%m-%d %H:%M")
    delta = d - p
    hours = delta.total_seconds() / 3600
    return max(1, math.ceil(hours / 24))


class CarRentalTools(ToolKitBase):
    db: CarRentalDB

    def __init__(self, db: CarRentalDB) -> None:
        super().__init__(db)

    # ── READ Tools ──────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_customer_by_name(self, name: str) -> list[Customer]:
        """Find customers by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching customers
        """
        name_lower = name.lower()
        return [c for c in self.db.customers.values() if name_lower in c.name.lower()]

    @is_tool(ToolType.READ)
    def find_customer_by_email(self, email: str) -> Customer:
        """Find a customer by their email address.

        Args:
            email: The email address to search for

        Returns:
            The matching customer

        Raises:
            ValueError: If no customer is found with that email
        """
        for c in self.db.customers.values():
            if c.email.lower() == email.lower():
                return c
        raise ValueError(f"No customer found with email '{email}'")

    @is_tool(ToolType.READ)
    def get_customer_details(self, customer_id: str) -> Customer:
        """Get full customer profile by ID.

        Args:
            customer_id: The customer's unique identifier

        Returns:
            The customer record

        Raises:
            ValueError: If the customer ID does not exist
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer '{customer_id}' not found")
        return self.db.customers[customer_id]

    @is_tool(ToolType.READ)
    def get_reservation(self, reservation_id: str) -> Reservation:
        """Get reservation details by ID.

        Args:
            reservation_id: The reservation's unique identifier

        Returns:
            The reservation record

        Raises:
            ValueError: If the reservation ID does not exist
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation '{reservation_id}' not found")
        return self.db.reservations[reservation_id]

    @is_tool(ToolType.READ)
    def search_vehicles(
        self,
        location_id: str,
        category: str,
        pickup_date: str,
        dropoff_date: str,
    ) -> list[Vehicle]:
        """Search for available vehicles at a location by category and dates.

        Args:
            location_id: The location ID to search at
            category: Vehicle category (economy/compact/midsize/suv/luxury/van)
            pickup_date: Pickup date (YYYY-MM-DD)
            dropoff_date: Dropoff date (YYYY-MM-DD)

        Returns:
            A list of available vehicles matching the criteria
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location '{location_id}' not found")
        return [
            v
            for v in self.db.vehicles.values()
            if v.location_id == location_id
            and v.category == category
            and v.status == "available"
        ]

    @is_tool(ToolType.READ)
    def get_vehicle_details(self, vehicle_id: str) -> Vehicle:
        """Get vehicle details by ID.

        Args:
            vehicle_id: The vehicle's unique identifier

        Returns:
            The vehicle record

        Raises:
            ValueError: If the vehicle ID does not exist
        """
        if vehicle_id not in self.db.vehicles:
            raise ValueError(f"Vehicle '{vehicle_id}' not found")
        return self.db.vehicles[vehicle_id]

    @is_tool(ToolType.READ)
    def get_location_details(self, location_id: str) -> Location:
        """Get location details and hours.

        Args:
            location_id: The location's unique identifier

        Returns:
            The location record

        Raises:
            ValueError: If the location ID does not exist
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location '{location_id}' not found")
        return self.db.locations[location_id]

    @is_tool(ToolType.READ)
    def list_locations(self) -> list[Location]:
        """List all rental locations with their details.

        Returns:
            A list of all rental locations
        """
        return list(self.db.locations.values())

    @is_tool(ToolType.READ)
    def list_extras(self) -> list[Extra]:
        """List all available add-on extras and their daily rates.

        Returns:
            A list of all available extras
        """
        return list(self.db.extras.values())

    @is_tool(ToolType.READ)
    def get_invoice(self, invoice_id: str) -> Invoice:
        """Get invoice details by ID.

        Args:
            invoice_id: The invoice's unique identifier

        Returns:
            The invoice record

        Raises:
            ValueError: If the invoice ID does not exist
        """
        if invoice_id not in self.db.invoices:
            raise ValueError(f"Invoice '{invoice_id}' not found")
        return self.db.invoices[invoice_id]

    @is_tool(ToolType.READ)
    def get_rental_agreement(self, agreement_id: str) -> RentalAgreement:
        """Get rental agreement details by ID.

        Args:
            agreement_id: The rental agreement's unique identifier

        Returns:
            The rental agreement record

        Raises:
            ValueError: If the agreement ID does not exist
        """
        if agreement_id not in self.db.rental_agreements:
            raise ValueError(f"Rental agreement '{agreement_id}' not found")
        return self.db.rental_agreements[agreement_id]

    @is_tool(ToolType.READ)
    def find_rental_agreements_by_customer(
        self, customer_id: str
    ) -> list[RentalAgreement]:
        """Find all rental agreements for a customer.

        Args:
            customer_id: The customer's unique identifier

        Returns:
            A list of rental agreements for the customer

        Raises:
            ValueError: If the customer ID does not exist
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer '{customer_id}' not found")
        return [
            a
            for a in self.db.rental_agreements.values()
            if a.customer_id == customer_id
        ]

    # ── WRITE Tools ─────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def create_reservation(
        self,
        customer_id: str,
        category: str,
        pickup_location_id: str,
        dropoff_location_id: str,
        pickup_datetime: str,
        dropoff_datetime: str,
        insurance_type: str = "none",
        extras: list[str] | None = None,
    ) -> Reservation:
        """Create a new vehicle reservation.

        Args:
            customer_id: The customer's unique identifier
            category: Vehicle category (economy/compact/midsize/suv/luxury/van)
            pickup_location_id: Pickup location ID
            dropoff_location_id: Dropoff location ID
            pickup_datetime: Pickup date and time (YYYY-MM-DD HH:MM)
            dropoff_datetime: Dropoff date and time (YYYY-MM-DD HH:MM)
            insurance_type: Insurance type (none/basic/premium), defaults to none
            extras: List of extra IDs to add, defaults to none

        Returns:
            The created reservation

        Raises:
            ValueError: If customer not found, invalid category, invalid locations,
                        driver too young, or license expired
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer '{customer_id}' not found")
        customer = self.db.customers[customer_id]

        if pickup_location_id not in self.db.locations:
            raise ValueError(f"Location '{pickup_location_id}' not found")
        if dropoff_location_id not in self.db.locations:
            raise ValueError(f"Location '{dropoff_location_id}' not found")

        valid_categories = [
            "economy",
            "compact",
            "midsize",
            "suv",
            "luxury",
            "van",
        ]
        if category not in valid_categories:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of: {valid_categories}"
            )

        if insurance_type not in ("none", "basic", "premium"):
            raise ValueError(
                f"Invalid insurance type '{insurance_type}'. Must be none, basic, or premium"
            )

        # Age check
        dob = datetime.strptime(customer.dob, "%Y-%m-%d")
        pickup_dt = datetime.strptime(pickup_datetime, "%Y-%m-%d %H:%M")
        age = (pickup_dt - dob).days // 365
        if age < MIN_DRIVER_AGE:
            raise ValueError(
                f"Driver must be at least {MIN_DRIVER_AGE} years old. Customer is {age}."
            )
        if category == "luxury" and age < LUXURY_MIN_AGE:
            raise ValueError(
                f"Driver must be at least {LUXURY_MIN_AGE} years old for luxury vehicles. Customer is {age}."
            )

        # License expiry check
        license_exp = datetime.strptime(customer.license_expiry, "%Y-%m-%d")
        if license_exp < pickup_dt:
            raise ValueError(
                f"Driver's license expired on {customer.license_expiry}. Cannot create reservation."
            )

        # Find available vehicle
        available = [
            v
            for v in self.db.vehicles.values()
            if v.location_id == pickup_location_id
            and v.category == category
            and v.status == "available"
        ]
        if not available:
            raise ValueError(
                f"No available {category} vehicles at location '{pickup_location_id}'"
            )

        # Assign first available vehicle
        vehicle = available[0]

        # Validate extras
        extra_ids = extras or []
        for eid in extra_ids:
            if eid not in self.db.extras:
                raise ValueError(f"Extra '{eid}' not found")

        # Calculate pricing
        days = _rental_days(pickup_datetime, dropoff_datetime)

        # Base daily rate by category
        base_rates = {
            "economy": 35.0,
            "compact": 45.0,
            "midsize": 55.0,
            "suv": 75.0,
            "luxury": 120.0,
            "van": 85.0,
        }
        daily_rate = base_rates[category]

        # Apply loyalty discount
        discount = {
            "none": 0.0,
            "silver": LOYALTY_SILVER_DISCOUNT,
            "gold": LOYALTY_GOLD_DISCOUNT,
            "platinum": LOYALTY_PLATINUM_DISCOUNT,
        }.get(customer.loyalty_tier, 0.0)
        daily_rate = round(daily_rate * (1 - discount), 2)

        # Calculate total estimate
        rental_cost = daily_rate * days

        insurance_cost = 0.0
        if insurance_type == "basic":
            insurance_cost = INSURANCE_BASIC_DAILY * days
        elif insurance_type == "premium":
            insurance_cost = INSURANCE_PREMIUM_DAILY * days

        extras_cost = sum(self.db.extras[eid].daily_rate * days for eid in extra_ids)

        one_way = (
            ONE_WAY_SURCHARGE if pickup_location_id != dropoff_location_id else 0.0
        )

        total_estimate = rental_cost + insurance_cost + extras_cost + one_way

        # Create reservation with deterministic ID
        last = _customer_last(customer_id)
        pickup_date_str = pickup_datetime.split(" ")[0].replace("-", "")
        base_id = f"res_{last}_{pickup_date_str}"
        res_id = _make_unique_id(base_id, self.db.reservations)

        reservation = Reservation(
            reservation_id=res_id,
            customer_id=customer_id,
            vehicle_category=category,
            pickup_location_id=pickup_location_id,
            dropoff_location_id=dropoff_location_id,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=dropoff_datetime,
            vehicle_id=vehicle.vehicle_id,
            status="confirmed",
            insurance_type=insurance_type,
            extras=extra_ids,
            daily_rate=daily_rate,
            total_estimate=round(total_estimate, 2),
        )

        # Update state
        self.db.reservations[res_id] = reservation
        customer.reservations.append(res_id)
        vehicle.status = "reserved"

        return reservation

    @is_tool(ToolType.WRITE)
    def modify_reservation(
        self,
        reservation_id: str,
        pickup_datetime: str | None = None,
        dropoff_datetime: str | None = None,
        category: str | None = None,
        extras: list[str] | None = None,
        insurance_type: str | None = None,
    ) -> Reservation:
        """Modify an existing reservation.

        Can change dates, vehicle category, extras, or insurance type.
        Only confirmed reservations can be fully modified.
        Active reservations allow extras changes only.

        Args:
            reservation_id: The reservation's unique identifier
            pickup_datetime: New pickup date and time (YYYY-MM-DD HH:MM)
            dropoff_datetime: New dropoff date and time (YYYY-MM-DD HH:MM)
            category: New vehicle category
            extras: New list of extra IDs (replaces existing)
            insurance_type: New insurance type (none/basic/premium)

        Returns:
            The modified reservation

        Raises:
            ValueError: If reservation not found, not modifiable, or invalid changes
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation '{reservation_id}' not found")
        res = self.db.reservations[reservation_id]

        if res.status == "active":
            # Active reservations only allow extras changes
            if any(
                x is not None
                for x in [pickup_datetime, dropoff_datetime, category, insurance_type]
            ):
                raise ValueError(
                    "Cannot modify dates, category, or insurance on an active reservation. "
                    "Only extras can be updated. Use extend_rental to change the return date."
                )
        elif res.status != "confirmed":
            raise ValueError(
                f"Cannot modify reservation with status '{res.status}'. "
                "Only confirmed or active reservations can be modified."
            )

        # Apply changes
        if pickup_datetime is not None:
            res.pickup_datetime = pickup_datetime
        if dropoff_datetime is not None:
            res.dropoff_datetime = dropoff_datetime

        if category is not None:
            valid_categories = [
                "economy",
                "compact",
                "midsize",
                "suv",
                "luxury",
                "van",
            ]
            if category not in valid_categories:
                raise ValueError(f"Invalid category '{category}'")

            # Check age for luxury
            customer = self.db.customers[res.customer_id]
            dob = datetime.strptime(customer.dob, "%Y-%m-%d")
            pickup_dt = datetime.strptime(res.pickup_datetime, "%Y-%m-%d %H:%M")
            age = (pickup_dt - dob).days // 365
            if category == "luxury" and age < LUXURY_MIN_AGE:
                raise ValueError(
                    f"Driver must be at least {LUXURY_MIN_AGE} for luxury vehicles."
                )

            # If category changed, reassign vehicle
            if category != res.vehicle_category:
                # Release old vehicle
                if res.vehicle_id and res.vehicle_id in self.db.vehicles:
                    self.db.vehicles[res.vehicle_id].status = "available"

                available = [
                    v
                    for v in self.db.vehicles.values()
                    if v.location_id == res.pickup_location_id
                    and v.category == category
                    and v.status == "available"
                ]
                if not available:
                    raise ValueError(
                        f"No available {category} vehicles at pickup location"
                    )
                vehicle = available[0]
                vehicle.status = "reserved"
                res.vehicle_id = vehicle.vehicle_id
                res.vehicle_category = category

                # Recalculate daily rate
                base_rates = {
                    "economy": 35.0,
                    "compact": 45.0,
                    "midsize": 55.0,
                    "suv": 75.0,
                    "luxury": 120.0,
                    "van": 85.0,
                }
                daily = base_rates[category]
                discount = {
                    "none": 0.0,
                    "silver": LOYALTY_SILVER_DISCOUNT,
                    "gold": LOYALTY_GOLD_DISCOUNT,
                    "platinum": LOYALTY_PLATINUM_DISCOUNT,
                }.get(customer.loyalty_tier, 0.0)
                res.daily_rate = round(daily * (1 - discount), 2)

        if insurance_type is not None:
            if insurance_type not in ("none", "basic", "premium"):
                raise ValueError(f"Invalid insurance type '{insurance_type}'")
            res.insurance_type = insurance_type

        if extras is not None:
            for eid in extras:
                if eid not in self.db.extras:
                    raise ValueError(f"Extra '{eid}' not found")
            res.extras = extras

        # Recalculate total
        days = _rental_days(res.pickup_datetime, res.dropoff_datetime)
        rental_cost = res.daily_rate * days

        ins_type = res.insurance_type
        insurance_cost = 0.0
        if ins_type == "basic":
            insurance_cost = INSURANCE_BASIC_DAILY * days
        elif ins_type == "premium":
            insurance_cost = INSURANCE_PREMIUM_DAILY * days

        extras_cost = sum(self.db.extras[eid].daily_rate * days for eid in res.extras)

        one_way = (
            ONE_WAY_SURCHARGE
            if res.pickup_location_id != res.dropoff_location_id
            else 0.0
        )

        res.total_estimate = round(
            rental_cost + insurance_cost + extras_cost + one_way, 2
        )

        return res

    @is_tool(ToolType.WRITE)
    def cancel_reservation(self, reservation_id: str, reason: str) -> Reservation:
        """Cancel a reservation.

        Free cancellation if more than 48 hours before pickup.
        $50 fee applies within 48 hours of pickup.

        Args:
            reservation_id: The reservation's unique identifier
            reason: Reason for cancellation

        Returns:
            The cancelled reservation

        Raises:
            ValueError: If reservation not found or already cancelled/completed
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation '{reservation_id}' not found")
        res = self.db.reservations[reservation_id]

        if res.status in ("cancelled", "completed"):
            raise ValueError(f"Cannot cancel reservation with status '{res.status}'")

        # Release assigned vehicle
        if res.vehicle_id and res.vehicle_id in self.db.vehicles:
            self.db.vehicles[res.vehicle_id].status = "available"

        res.status = "cancelled"

        return res

    @is_tool(ToolType.WRITE)
    def extend_rental(
        self, agreement_id: str, new_dropoff_datetime: str
    ) -> RentalAgreement:
        """Extend an active rental's dropoff date.

        Args:
            agreement_id: The rental agreement's unique identifier
            new_dropoff_datetime: New dropoff date and time (YYYY-MM-DD HH:MM)

        Returns:
            The updated rental agreement

        Raises:
            ValueError: If agreement not found or not active
        """
        if agreement_id not in self.db.rental_agreements:
            raise ValueError(f"Rental agreement '{agreement_id}' not found")
        agreement = self.db.rental_agreements[agreement_id]

        # Check that the rental is active (no actual_dropoff yet)
        if agreement.actual_dropoff is not None:
            raise ValueError("Cannot extend a completed rental")

        # Find the associated reservation and update dropoff
        if agreement.reservation_id in self.db.reservations:
            res = self.db.reservations[agreement.reservation_id]
            res.dropoff_datetime = new_dropoff_datetime

            # Recalculate total estimate
            days = _rental_days(res.pickup_datetime, res.dropoff_datetime)
            rental_cost = res.daily_rate * days

            insurance_cost = 0.0
            if res.insurance_type == "basic":
                insurance_cost = INSURANCE_BASIC_DAILY * days
            elif res.insurance_type == "premium":
                insurance_cost = INSURANCE_PREMIUM_DAILY * days

            extras_cost = sum(
                self.db.extras[eid].daily_rate * days
                for eid in res.extras
                if eid in self.db.extras
            )

            one_way = (
                ONE_WAY_SURCHARGE
                if res.pickup_location_id != res.dropoff_location_id
                else 0.0
            )

            res.total_estimate = round(
                rental_cost + insurance_cost + extras_cost + one_way, 2
            )

        return agreement

    @is_tool(ToolType.WRITE)
    def apply_loyalty_discount(self, reservation_id: str, points: int) -> Reservation:
        """Apply loyalty points as a discount on a reservation.

        100 points = $10 discount.

        Args:
            reservation_id: The reservation's unique identifier
            points: Number of loyalty points to redeem

        Returns:
            The updated reservation with reduced total

        Raises:
            ValueError: If reservation not found, customer doesn't have enough
                        points, or points amount is invalid
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation '{reservation_id}' not found")
        res = self.db.reservations[reservation_id]

        if res.status != "confirmed":
            raise ValueError(
                f"Cannot apply discount to reservation with status '{res.status}'"
            )

        customer = self.db.customers[res.customer_id]

        if points <= 0:
            raise ValueError("Points must be a positive number")
        if points > customer.loyalty_points:
            raise ValueError(
                f"Customer only has {customer.loyalty_points} points, "
                f"cannot redeem {points}"
            )

        discount_amount = (points / 100) * 10
        if discount_amount > res.total_estimate:
            raise ValueError(
                f"Discount amount ${discount_amount:.2f} exceeds "
                f"reservation total ${res.total_estimate:.2f}"
            )

        customer.loyalty_points -= points
        res.total_estimate = round(res.total_estimate - discount_amount, 2)

        return res

    @is_tool(ToolType.WRITE)
    def report_damage(self, agreement_id: str, description: str) -> RentalAgreement:
        """Report damage on a rented vehicle.

        Args:
            agreement_id: The rental agreement's unique identifier
            description: Description of the damage

        Returns:
            The updated rental agreement with damage report

        Raises:
            ValueError: If agreement not found
        """
        if agreement_id not in self.db.rental_agreements:
            raise ValueError(f"Rental agreement '{agreement_id}' not found")
        agreement = self.db.rental_agreements[agreement_id]
        agreement.damage_report = description
        return agreement

    @is_tool(ToolType.WRITE)
    def issue_credit(self, customer_id: str, amount: float, reason: str) -> str:
        """Issue a credit to a customer's account as compensation.

        Maximum credit amount is $200 per incident.

        Args:
            customer_id: The customer's unique identifier
            amount: Credit amount in dollars
            reason: Reason for the credit

        Returns:
            Confirmation message with credit details

        Raises:
            ValueError: If customer not found or amount exceeds maximum
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer '{customer_id}' not found")
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        if amount > MAX_CREDIT_AMOUNT:
            raise ValueError(
                f"Credit amount ${amount:.2f} exceeds maximum of "
                f"${MAX_CREDIT_AMOUNT:.2f}. Transfer to human agent for higher amounts."
            )

        # Convert credit to loyalty points (1 dollar = 10 points)
        points = int(amount * LOYALTY_POINTS_PER_DOLLAR)
        self.db.customers[customer_id].loyalty_points += points

        return (
            f"Credit of ${amount:.2f} issued to customer '{customer_id}' "
            f"({points} loyalty points added). Reason: {reason}"
        )

    @is_tool(ToolType.WRITE)
    def initiate_roadside_assistance(
        self, agreement_id: str, location: str, issue: str
    ) -> str:
        """Request roadside assistance for an active rental.

        Included free with premium insurance. Otherwise costs $150.

        Args:
            agreement_id: The rental agreement's unique identifier
            location: Current location/address of the vehicle
            issue: Description of the issue (flat_tire/dead_battery/lockout/tow/fuel/other)

        Returns:
            Confirmation message with assistance details

        Raises:
            ValueError: If agreement not found or rental not active
        """
        if agreement_id not in self.db.rental_agreements:
            raise ValueError(f"Rental agreement '{agreement_id}' not found")
        agreement = self.db.rental_agreements[agreement_id]

        if agreement.actual_dropoff is not None:
            raise ValueError("Cannot request assistance for a completed rental")

        # Check insurance type from reservation
        res = self.db.reservations.get(agreement.reservation_id)
        has_premium = res is not None and res.insurance_type == "premium"

        fee_msg = (
            "No additional charge (premium insurance)."
            if has_premium
            else f"A fee of ${ROADSIDE_FEE:.2f} will be added to your invoice."
        )

        return (
            f"Roadside assistance dispatched to '{location}' for issue: {issue}. "
            f"Agreement: {agreement_id}. {fee_msg} "
            f"Estimated arrival: 30-60 minutes."
        )

    # ── GENERIC Tools ───────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """Calculate the result of a mathematical expression.

        Args:
            expression: A mathematical expression (e.g. '75.00 * 3 + 50')

        Returns:
            The result as a string
        """
        allowed = set("0123456789.+-*/() ")
        if not all(c in allowed for c in expression):
            raise ValueError(
                "Expression contains invalid characters. "
                "Only numbers and +-*/() are allowed."
            )
        return str(eval(expression))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """Transfer the user to a human agent, with a summary of the user's issue.

        Only transfer if the user explicitly asks for a human agent
        or the issue cannot be resolved with available tools.

        Args:
            summary: A summary of the user's issue

        Returns:
            Confirmation message
        """
        return f"Transfer successful. Summary: {summary}"

    # ── Assertion Helpers (for evaluation) ──────────────────────

    def assert_reservation_status(
        self, reservation_id: str, expected_status: str
    ) -> bool:
        """Check that a reservation has the expected status."""
        if reservation_id not in self.db.reservations:
            return False
        return self.db.reservations[reservation_id].status == expected_status

    def assert_vehicle_status(self, vehicle_id: str, expected_status: str) -> bool:
        """Check that a vehicle has the expected status."""
        if vehicle_id not in self.db.vehicles:
            return False
        return self.db.vehicles[vehicle_id].status == expected_status

    def assert_reservation_exists(self, customer_id: str) -> bool:
        """Check that the customer has at least one reservation."""
        if customer_id not in self.db.customers:
            return False
        return len(self.db.customers[customer_id].reservations) > 0

    def assert_reservation_insurance(
        self, reservation_id: str, expected_insurance: str
    ) -> bool:
        """Check that a reservation has the expected insurance type."""
        if reservation_id not in self.db.reservations:
            return False
        return self.db.reservations[reservation_id].insurance_type == expected_insurance

    def assert_reservation_extras(
        self, reservation_id: str, expected_extras: list[str]
    ) -> bool:
        """Check that a reservation has the expected extras."""
        if reservation_id not in self.db.reservations:
            return False
        return sorted(self.db.reservations[reservation_id].extras) == sorted(
            expected_extras
        )

    def assert_customer_loyalty_points_decreased(
        self, customer_id: str, max_points: int
    ) -> bool:
        """Check that customer's loyalty points are at or below a threshold."""
        if customer_id not in self.db.customers:
            return False
        return self.db.customers[customer_id].loyalty_points <= max_points

    def assert_damage_reported(self, agreement_id: str) -> bool:
        """Check that a damage report exists on the agreement."""
        if agreement_id not in self.db.rental_agreements:
            return False
        return self.db.rental_agreements[agreement_id].damage_report is not None

    def assert_reservation_category(
        self, reservation_id: str, expected_category: str
    ) -> bool:
        """Check that a reservation has the expected vehicle category."""
        if reservation_id not in self.db.reservations:
            return False
        return (
            self.db.reservations[reservation_id].vehicle_category == expected_category
        )
