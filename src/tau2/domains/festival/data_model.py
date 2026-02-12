from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.festival.utils import FESTIVAL_DB_PATH
from tau2.environment.db import DB

TicketType = Literal["day_pass", "weekend", "vip", "artist"]
TicketDay = Literal["fri", "sat", "sun", "all"]
TicketStatus = Literal["valid", "used", "transferred", "refunded", "cancelled"]
CampingZone = Literal["general", "quiet", "family", "vip"]
CampingStatus = Literal["reserved", "checked_in", "checked_out", "cancelled"]
LostItemStatus = Literal["unclaimed", "claimed", "donated"]
VendorType = Literal["food", "merch", "art"]
PaymentType = Literal["credit_card", "festival_credits"]
PerformanceDay = Literal["fri", "sat", "sun"]


class Attendee(BaseModel):
    attendee_id: str = Field(description="Unique identifier for the attendee")
    name: str = Field(description="Attendee's full name")
    email: str = Field(description="Attendee's email address")
    phone: str = Field(description="Attendee's phone number")
    emergency_contact: str = Field(description="Emergency contact info")
    ticket_ids: List[str] = Field(
        default_factory=list, description="List of ticket IDs"
    )
    camping_reservation_id: Optional[str] = Field(
        None, description="Camping reservation ID if any"
    )
    accessibility_needs: Optional[str] = Field(
        None, description="Accessibility requirements"
    )
    wristband_id: Optional[str] = Field(None, description="Wristband ID")
    age_verified: bool = Field(
        default=False, description="Whether age has been verified"
    )


class Ticket(BaseModel):
    ticket_id: str = Field(description="Unique identifier for the ticket")
    attendee_id: str = Field(description="ID of the ticket holder")
    type: TicketType = Field(description="Ticket type")
    day: TicketDay = Field(description="Day(s) the ticket covers")
    status: TicketStatus = Field(description="Current ticket status")
    purchase_date: str = Field(description="Date of purchase (YYYY-MM-DD)")
    price: float = Field(description="Ticket price in dollars")
    payment_method_id: str = Field(description="Payment method used for purchase")


class CampingReservation(BaseModel):
    reservation_id: str = Field(description="Unique identifier for the reservation")
    attendee_id: str = Field(description="ID of the attendee")
    zone: CampingZone = Field(description="Camping zone")
    spot_number: int = Field(description="Assigned spot number")
    check_in_date: str = Field(description="Check-in date (YYYY-MM-DD)")
    check_out_date: str = Field(description="Check-out date (YYYY-MM-DD)")
    status: CampingStatus = Field(description="Current reservation status")
    vehicle_pass: bool = Field(
        default=False, description="Whether a vehicle pass is included"
    )


class Stage(BaseModel):
    stage_id: str = Field(description="Unique identifier for the stage")
    name: str = Field(description="Stage name")
    capacity: int = Field(description="Maximum capacity")
    location_description: str = Field(description="Stage location description")


class Performance(BaseModel):
    performance_id: str = Field(description="Unique identifier for the performance")
    artist_name: str = Field(description="Name of the performing artist/band")
    stage_id: str = Field(description="ID of the stage")
    day: PerformanceDay = Field(description="Day of the performance")
    start_time: str = Field(description="Start time (HH:MM)")
    end_time: str = Field(description="End time (HH:MM)")
    genre: str = Field(description="Music genre")
    age_restriction: Optional[str] = Field(
        None, description="Age restriction (e.g., '18+', '21+')"
    )


class LostItem(BaseModel):
    item_id: str = Field(description="Unique identifier for the lost item")
    description: str = Field(description="Description of the item")
    found_location: str = Field(description="Where the item was found")
    found_time: str = Field(description="When the item was found (YYYY-MM-DD HH:MM)")
    status: LostItemStatus = Field(description="Current status of the item")
    claimed_by: Optional[str] = Field(None, description="Attendee ID who claimed it")


class Vendor(BaseModel):
    vendor_id: str = Field(description="Unique identifier for the vendor")
    name: str = Field(description="Vendor name")
    type: VendorType = Field(description="Type of vendor")
    location: str = Field(description="Vendor location in the festival grounds")
    hours: str = Field(description="Operating hours")


class Shuttle(BaseModel):
    shuttle_id: str = Field(description="Unique identifier for the shuttle")
    route: str = Field(description="Route name")
    departure_times: List[str] = Field(description="List of departure times (HH:MM)")
    pickup_location: str = Field(description="Pickup location")
    dropoff_location: str = Field(description="Drop-off location")
    capacity: int = Field(description="Shuttle capacity")


class PaymentMethod(BaseModel):
    payment_method_id: str = Field(description="Unique identifier")
    type: PaymentType = Field(description="Payment type")
    details: str = Field(description="Payment details (masked)")


class FestivalDB(DB):
    """Multi-day music/arts festival database."""

    attendees: Dict[str, Attendee] = Field(
        description="Dictionary of attendees indexed by attendee ID"
    )
    tickets: Dict[str, Ticket] = Field(
        description="Dictionary of tickets indexed by ticket ID"
    )
    camping_reservations: Dict[str, CampingReservation] = Field(
        description="Dictionary of camping reservations indexed by reservation ID"
    )
    stages: Dict[str, Stage] = Field(
        description="Dictionary of stages indexed by stage ID"
    )
    performances: Dict[str, Performance] = Field(
        description="Dictionary of performances indexed by performance ID"
    )
    lost_items: Dict[str, LostItem] = Field(
        description="Dictionary of lost items indexed by item ID"
    )
    vendors: Dict[str, Vendor] = Field(
        description="Dictionary of vendors indexed by vendor ID"
    )
    shuttles: Dict[str, Shuttle] = Field(
        description="Dictionary of shuttles indexed by shuttle ID"
    )
    payment_methods: Dict[str, PaymentMethod] = Field(
        description="Dictionary of payment methods indexed by ID"
    )

    def get_statistics(self) -> dict[str, Any]:
        """Get the statistics of the database."""
        return {
            "num_attendees": len(self.attendees),
            "num_tickets": len(self.tickets),
            "num_camping_reservations": len(self.camping_reservations),
            "num_stages": len(self.stages),
            "num_performances": len(self.performances),
            "num_lost_items": len(self.lost_items),
            "num_vendors": len(self.vendors),
            "num_shuttles": len(self.shuttles),
        }


def get_db():
    return FestivalDB.load(FESTIVAL_DB_PATH)
