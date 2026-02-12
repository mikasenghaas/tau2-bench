from datetime import datetime, timedelta
from typing import Optional

from tau2.domains.restaurant.data_model import (
    Customer,
    Location,
    MenuItem,
    Order,
    OrderItem,
    Reservation,
    RestaurantDB,
    Table,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date — must match generate_db.py / generate_tasks.py TODAY.
REFERENCE_DATE = datetime(2025, 10, 15)

# Policy constants
LOYALTY_POINTS_PER_DOLLAR = 100  # 100 points = $10 discount
GIFT_CARD_MAX_NO_MANAGER = 50.0
MODIFICATION_CUTOFF_HOURS = 2
CANCELLATION_FEE_CUTOFF_HOURS = 1
CANCELLATION_FEE_PARTY_SIZE = 6


class RestaurantTools(ToolKitBase):
    """Tools for the restaurant domain."""

    db: RestaurantDB

    def __init__(self, db: RestaurantDB) -> None:
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

    def _customer_last(self, customer_id: str) -> str:
        return self.db.customers[customer_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_customer_by_phone(self, phone: str) -> list[Customer]:
        """
        Find customers by phone number (exact or partial match).

        Args:
            phone: The phone number to search for

        Returns:
            A list of matching customers
        """
        return [c for c in self.db.customers.values() if phone in c.phone]

    @is_tool(ToolType.READ)
    def find_customer_by_name(self, name: str) -> list[Customer]:
        """
        Find customers by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching customers
        """
        name_lower = name.lower()
        return [c for c in self.db.customers.values() if name_lower in c.name.lower()]

    @is_tool(ToolType.READ)
    def get_customer_details(self, customer_id: str) -> Customer:
        """
        Get the full record for a customer.

        Args:
            customer_id: The ID of the customer

        Returns:
            The customer record

        Raises:
            ValueError: If the customer is not found
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")
        return self.db.customers[customer_id]

    @is_tool(ToolType.READ)
    def get_reservation(self, reservation_id: str) -> Reservation:
        """
        Get details for a specific reservation.

        Args:
            reservation_id: The ID of the reservation

        Returns:
            The reservation record

        Raises:
            ValueError: If the reservation is not found
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")
        return self.db.reservations[reservation_id]

    @is_tool(ToolType.READ)
    def search_availability(
        self,
        location_id: str,
        date: str,
        time: str,
        party_size: int,
    ) -> list[Table]:
        """
        Search for available tables at a location for a given date, time, and party size.

        Args:
            location_id: The ID of the restaurant location
            date: The desired date (YYYY-MM-DD)
            time: The desired time (HH:MM)
            party_size: The number of guests

        Returns:
            A list of available tables that can accommodate the party

        Raises:
            ValueError: If the location is not found
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location {location_id} not found")

        # Find tables at this location that fit the party and are available
        available = []
        for t in self.db.tables.values():
            if (
                t.location_id == location_id
                and t.capacity >= party_size
                and t.is_available
            ):
                # Check no conflicting confirmed reservation at this date/time
                conflict = any(
                    r.table_id == t.table_id
                    and r.date == date
                    and r.time == time
                    and r.status in ("confirmed", "seated")
                    for r in self.db.reservations.values()
                )
                if not conflict:
                    available.append(t)
        return available

    @is_tool(ToolType.READ)
    def get_menu(self, location_id: str) -> list[MenuItem]:
        """
        Get the current menu for a restaurant location, including availability and allergen info.

        Args:
            location_id: The ID of the restaurant location

        Returns:
            A list of menu items

        Raises:
            ValueError: If the location is not found
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location {location_id} not found")
        return list(self.db.menu_items.values())

    @is_tool(ToolType.READ)
    def get_order(self, order_id: str) -> Order:
        """
        Get details for a specific order.

        Args:
            order_id: The ID of the order

        Returns:
            The order record

        Raises:
            ValueError: If the order is not found
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.db.orders[order_id]

    @is_tool(ToolType.READ)
    def get_location_details(self, location_id: str) -> Location:
        """
        Get details for a restaurant location.

        Args:
            location_id: The ID of the restaurant location

        Returns:
            The location record

        Raises:
            ValueError: If the location is not found
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location {location_id} not found")
        return self.db.locations[location_id]

    @is_tool(ToolType.READ)
    def get_dietary_menu(
        self,
        location_id: str,
        dietary_tag: Optional[str] = None,
        exclude_allergen: Optional[str] = None,
    ) -> list[MenuItem]:
        """
        Get menu items filtered by dietary preference or allergen exclusion.

        Args:
            location_id: The ID of the restaurant location
            dietary_tag: Filter for dietary tag (e.g., "vegan", "gluten-free", "vegetarian")
            exclude_allergen: Exclude items containing this allergen (e.g., "nuts", "dairy", "gluten")

        Returns:
            A list of matching menu items

        Raises:
            ValueError: If the location is not found
        """
        if location_id not in self.db.locations:
            raise ValueError(f"Location {location_id} not found")

        items = [i for i in self.db.menu_items.values() if i.available]
        if dietary_tag:
            tag_lower = dietary_tag.lower()
            items = [
                i for i in items if tag_lower in [t.lower() for t in i.dietary_tags]
            ]
        if exclude_allergen:
            allergen_lower = exclude_allergen.lower()
            items = [
                i
                for i in items
                if allergen_lower not in [a.lower() for a in i.allergens]
            ]
        return items

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def create_reservation(
        self,
        customer_id: str,
        location_id: str,
        date: str,
        time: str,
        party_size: int,
        special_requests: Optional[str] = None,
    ) -> Reservation:
        """
        Create a new reservation for a customer.

        Args:
            customer_id: The ID of the customer
            location_id: The ID of the restaurant location
            date: The reservation date (YYYY-MM-DD)
            time: The reservation time (HH:MM)
            party_size: The number of guests
            special_requests: Any special requests

        Returns:
            The created reservation record

        Raises:
            ValueError: If customer/location not found, or no table available
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")
        if location_id not in self.db.locations:
            raise ValueError(f"Location {location_id} not found")

        # Find a suitable table
        tables = self.search_availability(location_id, date, time, party_size)
        if not tables:
            raise ValueError(
                f"No tables available at {location_id} for party of {party_size} "
                f"on {date} at {time}. Consider alternative times or waitlist."
            )

        # Pick the smallest fitting table
        table = min(tables, key=lambda t: t.capacity)

        base_rid = f"res_{self._customer_last(customer_id)}_{date.replace('-', '')}"
        reservation_id = self._make_unique_id(base_rid, self.db.reservations)

        reservation = Reservation(
            reservation_id=reservation_id,
            customer_id=customer_id,
            location_id=location_id,
            date=date,
            time=time,
            party_size=party_size,
            table_id=table.table_id,
            status="confirmed",
            special_requests=special_requests,
        )

        self.db.reservations[reservation_id] = reservation
        self.db.customers[customer_id].reservation_ids.append(reservation_id)

        return reservation

    @is_tool(ToolType.WRITE)
    def modify_reservation(
        self,
        reservation_id: str,
        date: Optional[str] = None,
        time: Optional[str] = None,
        party_size: Optional[int] = None,
    ) -> Reservation:
        """
        Modify an existing reservation. Can change date, time, or party size.
        Reservations can only be modified up to 2 hours before the reserved time.

        Args:
            reservation_id: The ID of the reservation to modify
            date: New date (YYYY-MM-DD), if changing
            time: New time (HH:MM), if changing
            party_size: New party size, if changing

        Returns:
            The updated reservation record

        Raises:
            ValueError: If reservation not found, not modifiable, or within cutoff
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")

        res = self.db.reservations[reservation_id]
        if res.status not in ("confirmed", "waitlisted"):
            raise ValueError(
                f"Reservation {reservation_id} cannot be modified (status: {res.status})."
            )

        # Check modification cutoff
        res_dt = datetime.strptime(f"{res.date} {res.time}", "%Y-%m-%d %H:%M")
        cutoff = res_dt - timedelta(hours=MODIFICATION_CUTOFF_HOURS)
        if REFERENCE_DATE >= cutoff:
            raise ValueError(
                f"Reservation cannot be modified within {MODIFICATION_CUTOFF_HOURS} hours of the reservation time."
            )

        new_date = date or res.date
        new_time = time or res.time
        new_party = party_size or res.party_size

        # If party size changed, find a suitable table
        if party_size and party_size != res.party_size:
            tables = self.search_availability(
                res.location_id, new_date, new_time, new_party
            )
            if not tables:
                raise ValueError(
                    f"No tables available for the modified party size of {new_party}."
                )
            table = min(tables, key=lambda t: t.capacity)
            res.table_id = table.table_id

        res.date = new_date
        res.time = new_time
        res.party_size = new_party

        return res

    @is_tool(ToolType.WRITE)
    def cancel_reservation(self, reservation_id: str, reason: str) -> Reservation:
        """
        Cancel a reservation. Cancellations within 1 hour of the reservation
        time incur a fee for parties of more than 6.

        Args:
            reservation_id: The ID of the reservation to cancel
            reason: The reason for cancellation

        Returns:
            The updated reservation record

        Raises:
            ValueError: If the reservation is not found or not cancellable
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")

        res = self.db.reservations[reservation_id]
        if res.status not in ("confirmed", "waitlisted"):
            raise ValueError(
                f"Reservation {reservation_id} cannot be cancelled (status: {res.status})."
            )

        # Check cancellation fee
        res_dt = datetime.strptime(f"{res.date} {res.time}", "%Y-%m-%d %H:%M")
        cutoff = res_dt - timedelta(hours=CANCELLATION_FEE_CUTOFF_HOURS)
        late_cancel = REFERENCE_DATE >= cutoff
        large_party = res.party_size > CANCELLATION_FEE_PARTY_SIZE

        res.status = "cancelled"

        if late_cancel and large_party:
            return Reservation(
                **{
                    **res.model_dump(),
                    "special_requests": (
                        f"{res.special_requests or ''} "
                        f"[LATE CANCELLATION FEE APPLIES - party > {CANCELLATION_FEE_PARTY_SIZE}, "
                        f"cancelled within {CANCELLATION_FEE_CUTOFF_HOURS} hour. Reason: {reason}]"
                    ).strip(),
                }
            )

        return res

    @is_tool(ToolType.WRITE)
    def modify_order(
        self,
        order_id: str,
        add_items: Optional[list[dict]] = None,
        remove_items: Optional[list[str]] = None,
    ) -> Order:
        """
        Modify an existing order by adding or removing items.
        Only orders with status 'placed' can be modified.

        Args:
            order_id: The ID of the order to modify
            add_items: List of items to add, each with 'item_id', 'quantity', and optional 'modifications'
            remove_items: List of item_ids to remove from the order

        Returns:
            The updated order record

        Raises:
            ValueError: If the order is not found or cannot be modified
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.db.orders[order_id]
        if order.status != "placed":
            raise ValueError(
                f"Order {order_id} cannot be modified (status: {order.status})."
            )

        # Remove items
        if remove_items:
            for item_id in remove_items:
                found = False
                for oi in order.items:
                    if oi.item_id == item_id:
                        order.items.remove(oi)
                        found = True
                        break
                if not found:
                    raise ValueError(f"Item {item_id} not found in order {order_id}.")

        # Add items
        if add_items:
            for item_spec in add_items:
                item_id = item_spec["item_id"]
                if item_id not in self.db.menu_items:
                    raise ValueError(f"Menu item {item_id} not found.")
                menu_item = self.db.menu_items[item_id]
                if not menu_item.available:
                    raise ValueError(f"Menu item '{menu_item.name}' is not available.")
                quantity = item_spec.get("quantity", 1)
                modifications = item_spec.get("modifications")
                order.items.append(
                    OrderItem(
                        item_id=item_id,
                        quantity=quantity,
                        modifications=modifications,
                        price=menu_item.price,
                    )
                )

        # Recalculate total
        order.total = round(sum(oi.price * oi.quantity for oi in order.items), 2)

        return order

    @is_tool(ToolType.WRITE)
    def cancel_order_item(self, order_id: str, item_id: str, reason: str) -> Order:
        """
        Remove a specific item from an order. Only orders with status 'placed'
        or 'preparing' can have items removed.

        Args:
            order_id: The ID of the order
            item_id: The ID of the menu item to remove
            reason: The reason for removal

        Returns:
            The updated order record

        Raises:
            ValueError: If order/item not found or order cannot be modified
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.db.orders[order_id]
        if order.status not in ("placed", "preparing"):
            raise ValueError(
                f"Order {order_id} items cannot be removed (status: {order.status})."
            )

        found = False
        for oi in order.items:
            if oi.item_id == item_id:
                order.items.remove(oi)
                found = True
                break

        if not found:
            raise ValueError(f"Item {item_id} not found in order {order_id}.")

        # Recalculate total
        order.total = round(sum(oi.price * oi.quantity for oi in order.items), 2)

        if not order.items:
            order.status = "cancelled"

        return order

    @is_tool(ToolType.WRITE)
    def apply_loyalty_discount(self, order_id: str, points: int) -> Order:
        """
        Apply a loyalty points discount to an order. 100 points = $10.00 discount.

        Args:
            order_id: The ID of the order
            points: Number of loyalty points to redeem

        Returns:
            The updated order record

        Raises:
            ValueError: If order not found, customer lacks points, or order not eligible
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.db.orders[order_id]
        if order.status not in ("placed", "preparing"):
            raise ValueError(
                f"Loyalty discount cannot be applied to order with status: {order.status}."
            )

        customer = self.db.customers[order.customer_id]
        if customer.loyalty_points < points:
            raise ValueError(
                f"Customer has {customer.loyalty_points} points but tried to redeem {points}."
            )

        if points <= 0:
            raise ValueError("Points must be positive.")

        discount = round(points / LOYALTY_POINTS_PER_DOLLAR * 10, 2)
        if discount > order.total:
            raise ValueError(
                f"Discount (${discount:.2f}) exceeds order total (${order.total:.2f})."
            )

        order.total = round(order.total - discount, 2)
        customer.loyalty_points -= points

        return order

    @is_tool(ToolType.WRITE)
    def issue_gift_card(self, customer_id: str, amount: float, reason: str) -> str:
        """
        Issue a gift card to a customer as compensation. Maximum $50 without
        manager approval. Only for service failures.

        Args:
            customer_id: The ID of the customer
            amount: The gift card amount in dollars
            reason: The reason for issuing the gift card

        Returns:
            A confirmation message

        Raises:
            ValueError: If customer not found or amount exceeds limit
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")

        if amount <= 0:
            raise ValueError("Gift card amount must be positive.")

        if amount > GIFT_CARD_MAX_NO_MANAGER:
            raise ValueError(
                f"Gift card amount ${amount:.2f} exceeds the maximum of "
                f"${GIFT_CARD_MAX_NO_MANAGER:.2f} without manager approval. "
                f"Please transfer to a manager for approval."
            )

        customer = self.db.customers[customer_id]
        gc_id = self._make_unique_id(
            f"gc_{self._customer_last(customer_id)}", self.db.payment_methods
        )
        from tau2.domains.restaurant.data_model import PaymentMethod

        self.db.payment_methods[gc_id] = PaymentMethod(
            payment_method_id=gc_id,
            customer_id=customer_id,
            type="gift_card",
            details=f"${amount:.2f} gift card - {reason}",
        )

        return (
            f"Gift card {gc_id} for ${amount:.2f} issued to {customer.name}. "
            f"Reason: {reason}"
        )

    # ── GENERIC tools ─────────────────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """
        Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '12.50 - 3.00'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

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

    def assert_reservation_status(
        self, reservation_id: str, expected_status: str
    ) -> bool:
        """
        Check if a reservation's status matches the expected status.

        Args:
            reservation_id: The ID of the reservation
            expected_status: The expected status

        Returns:
            True if the status matches, False otherwise
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")
        return self.db.reservations[reservation_id].status == expected_status

    def assert_reservation_party_size(
        self, reservation_id: str, expected_party_size: int
    ) -> bool:
        """
        Check if a reservation's party size matches the expected value.

        Args:
            reservation_id: The ID of the reservation
            expected_party_size: The expected party size

        Returns:
            True if the party size matches, False otherwise
        """
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")
        return self.db.reservations[reservation_id].party_size == expected_party_size

    def assert_order_status(self, order_id: str, expected_status: str) -> bool:
        """
        Check if an order's status matches the expected status.

        Args:
            order_id: The ID of the order
            expected_status: The expected status

        Returns:
            True if the status matches, False otherwise
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.db.orders[order_id].status == expected_status

    def assert_order_item_count(self, order_id: str, expected_count: int) -> bool:
        """
        Check if the number of items in an order matches the expected count.

        Args:
            order_id: The ID of the order
            expected_count: The expected number of items

        Returns:
            True if the count matches, False otherwise
        """
        if order_id not in self.db.orders:
            raise ValueError(f"Order {order_id} not found")
        return len(self.db.orders[order_id].items) == expected_count

    def assert_customer_loyalty_points(
        self, customer_id: str, expected_points: int
    ) -> bool:
        """
        Check if a customer's loyalty points match the expected value.

        Args:
            customer_id: The ID of the customer
            expected_points: The expected loyalty points

        Returns:
            True if the points match, False otherwise
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")
        return self.db.customers[customer_id].loyalty_points == expected_points

    def assert_customer_reservation_count(
        self, customer_id: str, expected_count: int
    ) -> bool:
        """
        Check if a customer's reservation count matches expected value.

        Args:
            customer_id: The ID of the customer
            expected_count: The expected number of reservations

        Returns:
            True if the count matches, False otherwise
        """
        if customer_id not in self.db.customers:
            raise ValueError(f"Customer {customer_id} not found")
        return len(self.db.customers[customer_id].reservation_ids) == expected_count
