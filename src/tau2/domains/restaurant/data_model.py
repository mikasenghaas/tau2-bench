from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.restaurant.utils import RESTAURANT_DB_PATH
from tau2.environment.db import DB

ReservationStatus = Literal[
    "confirmed", "waitlisted", "cancelled", "no_show", "seated", "completed"
]
OrderStatus = Literal[
    "placed", "preparing", "ready", "delivered", "completed", "cancelled"
]
TableSection = Literal["indoor", "outdoor", "private"]
MenuCategory = Literal["appetizer", "main", "dessert", "drink"]
PaymentType = Literal["credit_card", "cash", "gift_card", "loyalty_points"]


class Customer(BaseModel):
    customer_id: str = Field(description="Unique identifier for the customer")
    name: str = Field(description="Customer's full name")
    email: str = Field(description="Customer's email address")
    phone: str = Field(description="Customer's phone number")
    dietary_restrictions: List[str] = Field(
        default_factory=list,
        description="Dietary restrictions (e.g., vegetarian, vegan)",
    )
    allergy_info: List[str] = Field(
        default_factory=list, description="Known food allergies"
    )
    loyalty_points: int = Field(default=0, description="Accumulated loyalty points")
    reservation_ids: List[str] = Field(
        default_factory=list, description="List of reservation IDs"
    )
    order_ids: List[str] = Field(default_factory=list, description="List of order IDs")


class Reservation(BaseModel):
    reservation_id: str = Field(description="Unique identifier for the reservation")
    customer_id: str = Field(description="ID of the customer who made the reservation")
    location_id: str = Field(description="ID of the restaurant location")
    date: str = Field(description="Reservation date (YYYY-MM-DD)")
    time: str = Field(description="Reservation time (HH:MM)")
    party_size: int = Field(description="Number of guests")
    table_id: Optional[str] = Field(None, description="Assigned table ID")
    status: ReservationStatus = Field(description="Current reservation status")
    special_requests: Optional[str] = Field(
        None, description="Special requests for the reservation"
    )


class Table(BaseModel):
    table_id: str = Field(description="Unique identifier for the table")
    location_id: str = Field(description="ID of the restaurant location")
    capacity: int = Field(description="Maximum number of seats at the table")
    section: TableSection = Field(description="Section of the restaurant")
    is_available: bool = Field(description="Whether the table is currently available")


class Location(BaseModel):
    location_id: str = Field(description="Unique identifier for the location")
    name: str = Field(description="Restaurant location name")
    address: str = Field(description="Restaurant address")
    hours: str = Field(description="Operating hours")
    phone: str = Field(description="Restaurant phone number")


class MenuItem(BaseModel):
    item_id: str = Field(description="Unique identifier for the menu item")
    name: str = Field(description="Item name")
    description: str = Field(description="Item description")
    price: float = Field(description="Item price in dollars")
    category: MenuCategory = Field(description="Menu category")
    allergens: List[str] = Field(
        default_factory=list, description="List of allergens in this item"
    )
    dietary_tags: List[str] = Field(
        default_factory=list, description="Dietary tags (e.g., vegan, gluten-free)"
    )
    available: bool = Field(default=True, description="Whether the item is available")


class OrderItem(BaseModel):
    item_id: str = Field(description="ID of the menu item")
    quantity: int = Field(description="Number of this item ordered")
    modifications: Optional[str] = Field(
        None, description="Special modifications for this item"
    )
    price: float = Field(description="Price per unit of this item")


class Order(BaseModel):
    order_id: str = Field(description="Unique identifier for the order")
    customer_id: str = Field(description="ID of the customer who placed the order")
    reservation_id: Optional[str] = Field(None, description="Associated reservation ID")
    location_id: str = Field(description="ID of the restaurant location")
    items: List[OrderItem] = Field(
        default_factory=list, description="List of items in the order"
    )
    status: OrderStatus = Field(description="Current order status")
    total: float = Field(default=0.0, description="Total order amount in dollars")
    payment_method: Optional[str] = Field(
        None, description="Payment method used (e.g., credit_card, cash)"
    )
    tip: float = Field(default=0.0, description="Tip amount in dollars")
    special_instructions: Optional[str] = Field(
        None, description="Special instructions for the order"
    )


class PaymentMethod(BaseModel):
    payment_method_id: str = Field(
        description="Unique identifier for the payment method"
    )
    customer_id: str = Field(
        description="ID of the customer who owns this payment method"
    )
    type: PaymentType = Field(description="Type of payment method")
    details: str = Field(description="Payment method details (last 4 digits, etc.)")


class RestaurantDB(DB):
    """Restaurant chain database with customers, reservations, tables, locations, menu items, orders, and payment methods."""

    customers: Dict[str, Customer] = Field(
        description="Dictionary of all customers indexed by customer ID"
    )
    reservations: Dict[str, Reservation] = Field(
        description="Dictionary of all reservations indexed by reservation ID"
    )
    tables: Dict[str, Table] = Field(
        description="Dictionary of all tables indexed by table ID"
    )
    locations: Dict[str, Location] = Field(
        description="Dictionary of all locations indexed by location ID"
    )
    menu_items: Dict[str, MenuItem] = Field(
        description="Dictionary of all menu items indexed by item ID"
    )
    orders: Dict[str, Order] = Field(
        description="Dictionary of all orders indexed by order ID"
    )
    payment_methods: Dict[str, PaymentMethod] = Field(
        description="Dictionary of all payment methods indexed by payment method ID"
    )

    def get_statistics(self) -> dict[str, Any]:
        """Get the statistics of the database."""
        return {
            "num_customers": len(self.customers),
            "num_reservations": len(self.reservations),
            "num_tables": len(self.tables),
            "num_locations": len(self.locations),
            "num_menu_items": len(self.menu_items),
            "num_orders": len(self.orders),
            "num_payment_methods": len(self.payment_methods),
        }


def get_db():
    return RestaurantDB.load(RESTAURANT_DB_PATH)
