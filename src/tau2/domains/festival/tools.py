from datetime import datetime
from typing import Optional

from tau2.domains.festival.data_model import (
    Attendee,
    CampingReservation,
    FestivalDB,
    LostItem,
    Performance,
    Shuttle,
    Stage,
    Ticket,
    Vendor,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date — must match generate_db.py / generate_tasks.py TODAY.
REFERENCE_DATE = datetime(2025, 10, 15)

# Festival dates
FESTIVAL_START = "2025-10-24"  # Friday
FESTIVAL_END = "2025-10-26"  # Sunday

# Policy constants
REFUND_FULL_DAYS = 14
REFUND_HALF_DAYS = 7
MAX_FESTIVAL_CREDITS = 50.0
CAMPING_CHECKIN_TIME = "14:00"
CAMPING_CHECKOUT_TIME = "12:00"
LOST_ITEM_HOLD_DAYS = 30


class FestivalTools(ToolKitBase):
    """Tools for the festival domain."""

    db: FestivalDB

    def __init__(self, db: FestivalDB) -> None:
        super().__init__(db)

    # ── ID helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_unique_id(base: str, existing) -> str:
        """Return *base* if unique, else base_2, base_3, … (deterministic)."""
        if base not in existing:
            return base
        n = 2
        while f"{base}_{n}" in existing:
            n += 1
        return f"{base}_{n}"

    def _attendee_last(self, attendee_id: str) -> str:
        return self.db.attendees[attendee_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_attendee_by_email(self, email: str) -> list[Attendee]:
        """
        Find attendees by email address (case-insensitive exact match).

        Args:
            email: The email address to search for

        Returns:
            A list of matching attendees
        """
        email_lower = email.lower()
        return [a for a in self.db.attendees.values() if a.email.lower() == email_lower]

    @is_tool(ToolType.READ)
    def find_attendee_by_name(self, name: str) -> list[Attendee]:
        """
        Find attendees by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching attendees
        """
        name_lower = name.lower()
        return [a for a in self.db.attendees.values() if name_lower in a.name.lower()]

    @is_tool(ToolType.READ)
    def get_attendee_details(self, attendee_id: str) -> Attendee:
        """
        Get the full record for an attendee.

        Args:
            attendee_id: The ID of the attendee

        Returns:
            The attendee record

        Raises:
            ValueError: If the attendee is not found
        """
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")
        return self.db.attendees[attendee_id]

    @is_tool(ToolType.READ)
    def get_ticket(self, ticket_id: str) -> Ticket:
        """
        Get details for a specific ticket.

        Args:
            ticket_id: The ID of the ticket

        Returns:
            The ticket record

        Raises:
            ValueError: If the ticket is not found
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id]

    @is_tool(ToolType.READ)
    def get_schedule(
        self,
        day: Optional[str] = None,
        stage: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> list[Performance]:
        """
        Get the performance schedule, optionally filtered by day, stage, or genre.

        Args:
            day: Filter by day (fri, sat, sun)
            stage: Filter by stage name (case-insensitive partial match)
            genre: Filter by genre (case-insensitive partial match)

        Returns:
            A list of matching performances
        """
        results = list(self.db.performances.values())
        if day:
            results = [p for p in results if p.day == day.lower()]
        if stage:
            stage_lower = stage.lower()
            # Find matching stage IDs
            matching_stage_ids = [
                s.stage_id
                for s in self.db.stages.values()
                if stage_lower in s.name.lower()
            ]
            results = [p for p in results if p.stage_id in matching_stage_ids]
        if genre:
            genre_lower = genre.lower()
            results = [p for p in results if genre_lower in p.genre.lower()]
        return sorted(results, key=lambda p: (p.day, p.start_time))

    @is_tool(ToolType.READ)
    def get_performance(self, performance_id: str) -> Performance:
        """
        Get details for a specific performance.

        Args:
            performance_id: The ID of the performance

        Returns:
            The performance record

        Raises:
            ValueError: If the performance is not found
        """
        if performance_id not in self.db.performances:
            raise ValueError(f"Performance {performance_id} not found")
        return self.db.performances[performance_id]

    @is_tool(ToolType.READ)
    def search_lost_items(
        self,
        description: Optional[str] = None,
    ) -> list[LostItem]:
        """
        Search the lost and found inventory by item description.

        Args:
            description: Description to search for (case-insensitive partial match)

        Returns:
            A list of matching lost items (includes found location and date)
        """
        results = [
            item for item in self.db.lost_items.values() if item.status == "unclaimed"
        ]
        if description:
            desc_lower = description.lower()
            results = [
                item for item in results if desc_lower in item.description.lower()
            ]
        return results

    @is_tool(ToolType.READ)
    def get_camping_details(self, reservation_id: str) -> CampingReservation:
        """
        Get details for a camping reservation.

        Args:
            reservation_id: The ID of the camping reservation

        Returns:
            The camping reservation record

        Raises:
            ValueError: If the reservation is not found
        """
        if reservation_id not in self.db.camping_reservations:
            raise ValueError(f"Camping reservation {reservation_id} not found")
        return self.db.camping_reservations[reservation_id]

    @is_tool(ToolType.READ)
    def list_vendors(self, type: Optional[str] = None) -> list[Vendor]:
        """
        List available vendors, optionally filtered by type.

        Args:
            type: Vendor type to filter by (food, merch, art)

        Returns:
            A list of matching vendors
        """
        results = list(self.db.vendors.values())
        if type:
            type_lower = type.lower()
            results = [v for v in results if v.type == type_lower]
        return results

    @is_tool(ToolType.READ)
    def get_shuttle_schedule(self, route: Optional[str] = None) -> list[Shuttle]:
        """
        Get shuttle schedules, optionally filtered by route.

        Args:
            route: Route name to filter by (case-insensitive partial match)

        Returns:
            A list of matching shuttle schedules
        """
        results = list(self.db.shuttles.values())
        if route:
            route_lower = route.lower()
            results = [s for s in results if route_lower in s.route.lower()]
        return results

    @is_tool(ToolType.READ)
    def check_ticket_availability(self, type: str, day: str) -> dict:
        """
        Check remaining ticket availability for a given type and day.

        Args:
            type: Ticket type (day_pass, weekend, vip, artist)
            day: Day to check (fri, sat, sun, all)

        Returns:
            A dictionary with total capacity, sold count, and remaining count

        Raises:
            ValueError: If the ticket type or day is invalid
        """
        valid_types = {"day_pass", "weekend", "vip", "artist"}
        valid_days = {"fri", "sat", "sun", "all"}
        if type not in valid_types:
            raise ValueError(
                f"Invalid ticket type: {type}. Valid types: {sorted(valid_types)}"
            )
        if day not in valid_days:
            raise ValueError(f"Invalid day: {day}. Valid days: {sorted(valid_days)}")

        # Capacity limits
        capacities = {
            ("day_pass", "fri"): 500,
            ("day_pass", "sat"): 500,
            ("day_pass", "sun"): 500,
            ("weekend", "all"): 300,
            ("vip", "fri"): 50,
            ("vip", "sat"): 50,
            ("vip", "sun"): 50,
            ("vip", "all"): 50,
            ("artist", "all"): 20,
        }
        cap_key = (type, day)
        if cap_key not in capacities:
            return {"total": 0, "sold": 0, "remaining": 0}

        total = capacities[cap_key]
        sold = sum(
            1
            for t in self.db.tickets.values()
            if t.type == type and t.day == day and t.status in ("valid", "used")
        )
        return {"total": total, "sold": sold, "remaining": total - sold}

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def upgrade_ticket(
        self, ticket_id: str, new_type: str, payment_method_id: str
    ) -> Ticket:
        """
        Upgrade a ticket to a higher tier. Price difference is charged.

        Args:
            ticket_id: The ID of the ticket to upgrade
            new_type: The new ticket type (weekend, vip)
            payment_method_id: Payment method for the price difference

        Returns:
            The updated ticket record

        Raises:
            ValueError: If ticket not found, invalid upgrade, or new type unavailable
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        if payment_method_id not in self.db.payment_methods:
            raise ValueError(f"Payment method {payment_method_id} not found")

        ticket = self.db.tickets[ticket_id]
        if ticket.status != "valid":
            raise ValueError(
                f"Ticket {ticket_id} is not valid (status: {ticket.status}). "
                f"Only valid tickets can be upgraded."
            )

        type_hierarchy = {"day_pass": 0, "weekend": 1, "vip": 2, "artist": 3}
        if new_type not in type_hierarchy:
            raise ValueError(f"Invalid ticket type: {new_type}")
        if type_hierarchy.get(new_type, 0) <= type_hierarchy.get(ticket.type, 0):
            raise ValueError(
                f"Cannot upgrade from {ticket.type} to {new_type}. "
                f"New type must be a higher tier."
            )

        # Price table
        prices = {
            "day_pass": 75.0,
            "weekend": 180.0,
            "vip": 350.0,
        }
        old_price = prices.get(ticket.type, ticket.price)
        new_price = prices.get(new_type, 0)
        if new_price <= old_price:
            raise ValueError("Upgrade price must be higher than current ticket price.")

        ticket.type = new_type
        ticket.price = new_price
        ticket.payment_method_id = payment_method_id
        if new_type in ("weekend", "vip"):
            ticket.day = "all"

        return ticket

    @is_tool(ToolType.WRITE)
    def transfer_ticket(self, ticket_id: str, new_attendee_email: str) -> Ticket:
        """
        Transfer a ticket to another attendee. Both parties must be registered.
        Each ticket can only be transferred once.

        Args:
            ticket_id: The ID of the ticket to transfer
            new_attendee_email: Email of the new attendee

        Returns:
            The updated ticket record

        Raises:
            ValueError: If ticket/attendee not found, ticket already transferred,
                        or new attendee not registered
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")

        ticket = self.db.tickets[ticket_id]
        if ticket.status != "valid":
            raise ValueError(
                f"Ticket {ticket_id} is not valid (status: {ticket.status}). "
                f"Only valid tickets can be transferred."
            )

        # Find new attendee by email
        new_attendees = [
            a
            for a in self.db.attendees.values()
            if a.email.lower() == new_attendee_email.lower()
        ]
        if not new_attendees:
            raise ValueError(
                f"No registered attendee found with email {new_attendee_email}. "
                f"The recipient must be registered before a ticket can be transferred."
            )
        new_attendee = new_attendees[0]

        old_attendee_id = ticket.attendee_id
        old_attendee = self.db.attendees[old_attendee_id]

        # Transfer the ticket
        ticket.attendee_id = new_attendee.attendee_id
        ticket.status = "transferred"

        # Update attendee ticket lists
        if ticket_id in old_attendee.ticket_ids:
            old_attendee.ticket_ids.remove(ticket_id)
        new_attendee.ticket_ids.append(ticket_id)

        return ticket

    @is_tool(ToolType.WRITE)
    def refund_ticket(self, ticket_id: str, reason: str) -> Ticket:
        """
        Process a ticket refund. Refund amount depends on timing:
        - 14+ days before event: full refund
        - 7-13 days before event: 50% refund
        - Less than 7 days: no refund

        Args:
            ticket_id: The ID of the ticket to refund
            reason: Reason for the refund

        Returns:
            The updated ticket record

        Raises:
            ValueError: If ticket not found, not valid, or outside refund window
        """
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")

        ticket = self.db.tickets[ticket_id]
        if ticket.status != "valid":
            raise ValueError(
                f"Ticket {ticket_id} is not valid (status: {ticket.status}). "
                f"Only valid tickets can be refunded."
            )

        today = REFERENCE_DATE
        festival_start = datetime.strptime(FESTIVAL_START, "%Y-%m-%d")
        days_until = (festival_start - today).days

        if days_until < REFUND_HALF_DAYS:
            raise ValueError(
                f"Cannot refund ticket: festival starts in {days_until} days. "
                f"Refunds are only available 7 or more days before the event."
            )

        ticket.status = "refunded"

        # Remove from attendee's ticket list
        attendee = self.db.attendees[ticket.attendee_id]
        if ticket_id in attendee.ticket_ids:
            attendee.ticket_ids.remove(ticket_id)

        return ticket

    @is_tool(ToolType.WRITE)
    def modify_camping(
        self,
        reservation_id: str,
        zone: Optional[str] = None,
        check_in_date: Optional[str] = None,
        check_out_date: Optional[str] = None,
    ) -> CampingReservation:
        """
        Modify a camping reservation (zone and/or dates).

        Args:
            reservation_id: The ID of the camping reservation
            zone: New camping zone (general, quiet, family, vip)
            check_in_date: New check-in date (YYYY-MM-DD)
            check_out_date: New check-out date (YYYY-MM-DD)

        Returns:
            The updated camping reservation

        Raises:
            ValueError: If reservation not found, not modifiable, or invalid values
        """
        if reservation_id not in self.db.camping_reservations:
            raise ValueError(f"Camping reservation {reservation_id} not found")

        res = self.db.camping_reservations[reservation_id]
        if res.status not in ("reserved", "checked_in"):
            raise ValueError(
                f"Reservation {reservation_id} cannot be modified "
                f"(status: {res.status})."
            )

        valid_zones = {"general", "quiet", "family", "vip"}
        if zone is not None:
            if zone not in valid_zones:
                raise ValueError(
                    f"Invalid zone: {zone}. Valid zones: {sorted(valid_zones)}"
                )
            # VIP camping requires VIP ticket
            if zone == "vip":
                attendee = self.db.attendees[res.attendee_id]
                has_vip = any(
                    self.db.tickets[tid].type == "vip"
                    for tid in attendee.ticket_ids
                    if tid in self.db.tickets
                )
                if not has_vip:
                    raise ValueError("VIP camping zone requires a VIP ticket.")
            res.zone = zone

        if check_in_date is not None:
            res.check_in_date = check_in_date
        if check_out_date is not None:
            res.check_out_date = check_out_date

        return res

    @is_tool(ToolType.WRITE)
    def cancel_camping(self, reservation_id: str) -> CampingReservation:
        """
        Cancel a camping reservation.

        Args:
            reservation_id: The ID of the camping reservation

        Returns:
            The updated camping reservation

        Raises:
            ValueError: If reservation not found or already cancelled/checked_out
        """
        if reservation_id not in self.db.camping_reservations:
            raise ValueError(f"Camping reservation {reservation_id} not found")

        res = self.db.camping_reservations[reservation_id]
        if res.status in ("cancelled", "checked_out"):
            raise ValueError(f"Reservation {reservation_id} is already {res.status}.")

        res.status = "cancelled"

        # Remove reference from attendee
        attendee = self.db.attendees[res.attendee_id]
        if attendee.camping_reservation_id == reservation_id:
            attendee.camping_reservation_id = None

        return res

    @is_tool(ToolType.WRITE)
    def report_lost_item(
        self, attendee_id: str, description: str, last_seen_location: str
    ) -> LostItem:
        """
        Report a lost item. Creates a record in lost and found.

        Args:
            attendee_id: The ID of the attendee reporting the item
            description: Description of the lost item
            last_seen_location: Where the item was last seen

        Returns:
            The new lost item record

        Raises:
            ValueError: If the attendee is not found
        """
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")

        today = REFERENCE_DATE.strftime("%Y-%m-%d %H:%M")
        last_name = self._attendee_last(attendee_id)
        # Deterministic ID based on attendee and description
        desc_slug = description.lower().replace(" ", "_")[:20]
        base_id = f"lost_{last_name}_{desc_slug}"
        item_id = self._make_unique_id(base_id, self.db.lost_items)

        item = LostItem(
            item_id=item_id,
            description=description,
            found_location=last_seen_location,
            found_time=today,
            status="unclaimed",
            claimed_by=None,
        )
        self.db.lost_items[item_id] = item
        return item

    @is_tool(ToolType.WRITE)
    def claim_lost_item(self, item_id: str, attendee_id: str) -> LostItem:
        """
        Claim a found item from lost and found.

        Args:
            item_id: The ID of the lost item
            attendee_id: The ID of the attendee claiming the item

        Returns:
            The updated lost item record

        Raises:
            ValueError: If item/attendee not found or item already claimed
        """
        if item_id not in self.db.lost_items:
            raise ValueError(f"Lost item {item_id} not found")
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")

        item = self.db.lost_items[item_id]
        if item.status != "unclaimed":
            raise ValueError(
                f"Item {item_id} is not unclaimed (status: {item.status})."
            )

        item.status = "claimed"
        item.claimed_by = attendee_id
        return item

    @is_tool(ToolType.WRITE)
    def add_accessibility_note(self, attendee_id: str, needs: str) -> Attendee:
        """
        Record or update accessibility requirements for an attendee.

        Args:
            attendee_id: The ID of the attendee
            needs: Description of accessibility needs

        Returns:
            The updated attendee record

        Raises:
            ValueError: If the attendee is not found
        """
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")

        attendee = self.db.attendees[attendee_id]
        attendee.accessibility_needs = needs
        return attendee

    @is_tool(ToolType.WRITE)
    def issue_festival_credits(
        self, attendee_id: str, amount: float, reason: str
    ) -> str:
        """
        Issue festival credits to compensate an attendee. Maximum $50 per incident.
        Credits are non-transferable.

        Args:
            attendee_id: The ID of the attendee
            amount: The credit amount in dollars (max $50)
            reason: Reason for issuing credits

        Returns:
            Confirmation message

        Raises:
            ValueError: If attendee not found or amount exceeds maximum
        """
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")

        if amount <= 0:
            raise ValueError("Credit amount must be positive.")

        if amount > MAX_FESTIVAL_CREDITS:
            raise ValueError(
                f"Credit amount ${amount:.2f} exceeds maximum of "
                f"${MAX_FESTIVAL_CREDITS:.2f} per incident."
            )

        attendee = self.db.attendees[attendee_id]
        return (
            f"Issued ${amount:.2f} in festival credits to {attendee.name} "
            f"(attendee {attendee_id}). Reason: {reason}"
        )

    # ── GENERIC tools ─────────────────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """
        Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '350 - 180'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

        Returns:
            The result of the mathematical expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """
        Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if
         -  the user explicitly asks for a human agent
         -  given the policy and the available tools, you cannot solve the user's issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred to a human agent.
        """
        return "Transfer successful"

    # ── Assertion helpers (not exposed as tools) ──────────────────────────

    def assert_ticket_status(self, ticket_id: str, expected_status: str) -> bool:
        """Check if a ticket's status matches the expected status."""
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id].status == expected_status

    def assert_ticket_type(self, ticket_id: str, expected_type: str) -> bool:
        """Check if a ticket's type matches the expected type."""
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id].type == expected_type

    def assert_ticket_attendee(self, ticket_id: str, expected_attendee_id: str) -> bool:
        """Check if a ticket belongs to the expected attendee."""
        if ticket_id not in self.db.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        return self.db.tickets[ticket_id].attendee_id == expected_attendee_id

    def assert_camping_status(self, reservation_id: str, expected_status: str) -> bool:
        """Check if a camping reservation's status matches."""
        if reservation_id not in self.db.camping_reservations:
            raise ValueError(f"Camping reservation {reservation_id} not found")
        return self.db.camping_reservations[reservation_id].status == expected_status

    def assert_camping_zone(self, reservation_id: str, expected_zone: str) -> bool:
        """Check if a camping reservation's zone matches."""
        if reservation_id not in self.db.camping_reservations:
            raise ValueError(f"Camping reservation {reservation_id} not found")
        return self.db.camping_reservations[reservation_id].zone == expected_zone

    def assert_lost_item_status(self, item_id: str, expected_status: str) -> bool:
        """Check if a lost item's status matches."""
        if item_id not in self.db.lost_items:
            raise ValueError(f"Lost item {item_id} not found")
        return self.db.lost_items[item_id].status == expected_status

    def assert_attendee_accessibility(
        self, attendee_id: str, expected_needs: str
    ) -> bool:
        """Check if an attendee's accessibility needs contain the expected text."""
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")
        needs = self.db.attendees[attendee_id].accessibility_needs
        if needs is None:
            return False
        return expected_needs.lower() in needs.lower()

    def assert_attendee_ticket_count(self, attendee_id: str, expected: int) -> bool:
        """Check if the number of tickets for an attendee matches."""
        if attendee_id not in self.db.attendees:
            raise ValueError(f"Attendee {attendee_id} not found")
        return len(self.db.attendees[attendee_id].ticket_ids) == expected
