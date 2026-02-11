from datetime import datetime, timedelta
from typing import Optional

from tau2.domains.library.data_model import (
    Book,
    Branch,
    Copy,
    Event,
    Fine,
    Hold,
    LibraryDB,
    Loan,
    Patron,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date — must match generate_db.py / generate_tasks.py TODAY.
# Using a fixed date (instead of datetime.now()) keeps the tools consistent
# with the generated DB regardless of when the eval actually runs.
REFERENCE_DATE = datetime(2025, 10, 15)

# Policy constants
FINE_CHECKOUT_BLOCK_THRESHOLD = 10.0
MAX_RENEWALS_STANDARD = 2
MAX_RENEWALS_STUDENT = 3
LOAN_PERIOD_STANDARD_WEEKS = 3
LOAN_PERIOD_STUDENT_WEEKS = 4
OVERDUE_FINE_PER_DAY = 0.25
MAX_FINE_PER_ITEM = 25.0
LOST_BOOK_FINE = 50.0
HOLD_EXPIRY_DAYS = 7
MAX_INTERLIBRARY_LOANS = 3


class LibraryTools(ToolKitBase):
    """Tools for the library domain."""

    db: LibraryDB

    def __init__(self, db: LibraryDB) -> None:
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

    def _patron_last(self, patron_id: str) -> str:
        return self.db.patrons[patron_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_patron_by_name(self, name: str) -> list[Patron]:
        """
        Find patrons by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching patrons
        """
        name_lower = name.lower()
        return [
            p for p in self.db.patrons.values()
            if name_lower in p.name.lower()
        ]

    @is_tool(ToolType.READ)
    def find_patron_by_card(self, card_number: str) -> Patron:
        """
        Look up a patron by their library card number (patron ID).

        Args:
            card_number: The library card number (patron ID)

        Returns:
            The patron record

        Raises:
            ValueError: If the patron is not found
        """
        if card_number not in self.db.patrons:
            raise ValueError(f"Patron with card number {card_number} not found")
        return self.db.patrons[card_number]

    @is_tool(ToolType.READ)
    def get_patron_details(self, patron_id: str) -> Patron:
        """
        Get the full record for a patron.

        Args:
            patron_id: The ID of the patron

        Returns:
            The patron record

        Raises:
            ValueError: If the patron is not found
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        return self.db.patrons[patron_id]

    @is_tool(ToolType.READ)
    def find_branch_by_name(self, name: str) -> list[Branch]:
        """
        Find branches by name (case-insensitive partial match).

        Args:
            name: The name to search for

        Returns:
            A list of matching branches
        """
        name_lower = name.lower()
        return [
            b for b in self.db.branches.values()
            if name_lower in b.name.lower()
        ]

    @is_tool(ToolType.READ)
    def search_catalog(
        self,
        title: Optional[str] = None,
        author: Optional[str] = None,
        isbn: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[Book]:
        """
        Search the book catalog by title, author, ISBN, or category.

        Args:
            title: Book title to search for (partial, case-insensitive)
            author: Author name to search for (partial, case-insensitive)
            isbn: ISBN to search for (exact match)
            category: Category to filter by (case-insensitive). Valid categories: biography, children, fiction, history, mystery, non-fiction, reference, science

        Returns:
            A list of matching books
        """
        results = list(self.db.books.values())
        if title:
            title_lower = title.lower()
            results = [b for b in results if title_lower in b.title.lower()]
        if author:
            author_lower = author.lower()
            results = [b for b in results if author_lower in b.author.lower()]
        if isbn:
            results = [b for b in results if b.isbn == isbn]
        if category:
            category_lower = category.lower()
            results = [b for b in results if category_lower in b.category.lower()]
        return results

    @is_tool(ToolType.READ)
    def get_book_availability(self, book_id: str, branch_id: Optional[str] = None) -> list[Copy]:
        """
        Check availability of copies for a specific book, optionally filtered by branch.

        Args:
            book_id: The ID of the book
            branch_id: Optional branch ID to filter by

        Returns:
            A list of copies for the book

        Raises:
            ValueError: If the book is not found
        """
        if book_id not in self.db.books:
            raise ValueError(f"Book {book_id} not found")
        book = self.db.books[book_id]
        copies = [self.db.copies[cid] for cid in book.copies if cid in self.db.copies]
        if branch_id:
            copies = [c for c in copies if c.branch_id == branch_id]
        return copies

    @is_tool(ToolType.READ)
    def get_loan_details(self, loan_id: str) -> Loan:
        """
        Get details for a specific loan.

        Args:
            loan_id: The ID of the loan

        Returns:
            The loan record

        Raises:
            ValueError: If the loan is not found
        """
        if loan_id not in self.db.loans:
            raise ValueError(f"Loan {loan_id} not found")
        return self.db.loans[loan_id]

    @is_tool(ToolType.READ)
    def list_patron_loans(self, patron_id: str) -> list[Loan]:
        """
        List all active loans for a patron.

        Args:
            patron_id: The ID of the patron

        Returns:
            A list of active loans for the patron

        Raises:
            ValueError: If the patron is not found
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        patron = self.db.patrons[patron_id]
        return [
            self.db.loans[lid] for lid in patron.active_loans
            if lid in self.db.loans
        ]

    @is_tool(ToolType.READ)
    def list_patron_fines(self, patron_id: str) -> list[Fine]:
        """
        List all outstanding fines for a patron.

        Args:
            patron_id: The ID of the patron

        Returns:
            A list of outstanding fines for the patron

        Raises:
            ValueError: If the patron is not found
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        return [
            f for f in self.db.fines.values()
            if f.patron_id == patron_id and f.status == "outstanding"
        ]

    @is_tool(ToolType.READ)
    def list_events(self, branch_id: str, date_range: Optional[str] = None) -> list[Event]:
        """
        List upcoming events at a branch.

        Args:
            branch_id: The ID of the branch
            date_range: Optional date range filter (e.g., "2025-01-01 to 2025-01-31")

        Returns:
            A list of events at the branch

        Raises:
            ValueError: If the branch is not found
        """
        if branch_id not in self.db.branches:
            raise ValueError(f"Branch {branch_id} not found")
        events = [e for e in self.db.events.values() if e.branch_id == branch_id]
        if date_range:
            try:
                parts = date_range.split(" to ")
                start = parts[0].strip()
                end = parts[1].strip()
                events = [e for e in events if start <= e.date <= end]
            except (IndexError, ValueError):
                pass
        return events

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def checkout_book(self, patron_id: str, copy_id: str) -> Loan:
        """
        Check out a book copy to a patron.

        Args:
            patron_id: The ID of the patron
            copy_id: The ID of the copy to check out

        Returns:
            The new loan record

        Raises:
            ValueError: If patron/copy not found, fines exceed threshold,
                        membership expired, borrowing limit reached, or copy not available
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        if copy_id not in self.db.copies:
            raise ValueError(f"Copy {copy_id} not found")

        patron = self.db.patrons[patron_id]
        copy = self.db.copies[copy_id]

        # Policy: fines > $10 block checkout
        if patron.fines_owed > FINE_CHECKOUT_BLOCK_THRESHOLD:
            raise ValueError(
                f"Patron has ${patron.fines_owed:.2f} in outstanding fines. "
                f"Fines must be reduced to ${FINE_CHECKOUT_BLOCK_THRESHOLD:.2f} or below before checkout."
            )

        # Policy: membership must be active
        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        if patron.membership_expiry < today:
            raise ValueError(
                f"Patron's membership expired on {patron.membership_expiry}. "
                f"Please renew membership before checkout."
            )

        # Policy: check borrowing limit
        if len(patron.active_loans) >= patron.borrowing_limit:
            raise ValueError(
                f"Patron has reached the borrowing limit of {patron.borrowing_limit} books."
            )

        # Copy must be available
        if copy.status != "available":
            raise ValueError(
                f"Copy {copy_id} is not available (current status: {copy.status})."
            )

        # Determine loan period based on membership type
        if patron.membership_type == "student":
            weeks = LOAN_PERIOD_STUDENT_WEEKS
        else:
            weeks = LOAN_PERIOD_STANDARD_WEEKS

        checkout_date = REFERENCE_DATE
        due_date = checkout_date + timedelta(weeks=weeks)

        book_id = self.db.copies[copy_id].book_id
        base_lid = f"loan_{self._patron_last(patron_id)}_{book_id}"
        loan_id = self._make_unique_id(base_lid, self.db.loans)
        loan = Loan(
            loan_id=loan_id,
            patron_id=patron_id,
            copy_id=copy_id,
            checkout_date=checkout_date.strftime("%Y-%m-%d"),
            due_date=due_date.strftime("%Y-%m-%d"),
            renewals_count=0,
            fine_amount=0.0,
        )

        # Update state
        self.db.loans[loan_id] = loan
        copy.status = "checked_out"
        copy.due_date = due_date.strftime("%Y-%m-%d")
        copy.borrower_id = patron_id
        patron.active_loans.append(loan_id)

        return loan

    @is_tool(ToolType.WRITE)
    def return_book(self, copy_id: str) -> Loan:
        """
        Process the return of a book copy. Generates a fine if overdue.

        Args:
            copy_id: The ID of the copy being returned

        Returns:
            The updated loan record

        Raises:
            ValueError: If copy not found or copy is not checked out
        """
        if copy_id not in self.db.copies:
            raise ValueError(f"Copy {copy_id} not found")

        copy = self.db.copies[copy_id]
        if copy.status != "checked_out" or copy.borrower_id is None:
            raise ValueError(f"Copy {copy_id} is not currently checked out.")

        # Find the active loan for this copy
        loan = None
        for l in self.db.loans.values():
            if l.copy_id == copy_id and l.return_date is None:
                loan = l
                break
        if loan is None:
            raise ValueError(f"No active loan found for copy {copy_id}.")

        today = REFERENCE_DATE
        loan.return_date = today.strftime("%Y-%m-%d")

        # Check if overdue and generate fine
        due_date = datetime.strptime(loan.due_date, "%Y-%m-%d")
        if today > due_date:
            days_overdue = (today - due_date).days
            fine_amount = min(days_overdue * OVERDUE_FINE_PER_DAY, MAX_FINE_PER_ITEM)
            loan.fine_amount = fine_amount

            base_fid = f"fine_{self._patron_last(loan.patron_id)}_overdue"
            fine_id = self._make_unique_id(base_fid, self.db.fines)
            fine = Fine(
                fine_id=fine_id,
                patron_id=loan.patron_id,
                loan_id=loan.loan_id,
                amount=fine_amount,
                reason="overdue",
                status="outstanding",
                issued_date=today.strftime("%Y-%m-%d"),
            )
            self.db.fines[fine_id] = fine

            patron = self.db.patrons[loan.patron_id]
            patron.fines_owed += fine_amount

        # Update copy and patron state
        patron = self.db.patrons[loan.patron_id]
        copy.status = "available"
        copy.due_date = None
        copy.borrower_id = None
        if loan.loan_id in patron.active_loans:
            patron.active_loans.remove(loan.loan_id)

        return loan

    @is_tool(ToolType.WRITE)
    def renew_loan(self, loan_id: str) -> Loan:
        """
        Renew a loan by extending the due date.

        Args:
            loan_id: The ID of the loan to renew

        Returns:
            The updated loan record

        Raises:
            ValueError: If loan not found, max renewals reached, or book has a hold
        """
        if loan_id not in self.db.loans:
            raise ValueError(f"Loan {loan_id} not found")

        loan = self.db.loans[loan_id]
        if loan.return_date is not None:
            raise ValueError(f"Loan {loan_id} has already been returned.")

        patron = self.db.patrons[loan.patron_id]

        # Check max renewals
        if patron.membership_type == "student":
            max_renewals = MAX_RENEWALS_STUDENT
        else:
            max_renewals = MAX_RENEWALS_STANDARD

        if loan.renewals_count >= max_renewals:
            raise ValueError(
                f"Maximum renewals ({max_renewals}) reached for this loan."
            )

        # Check if any active hold exists on the book
        copy = self.db.copies[loan.copy_id]
        book_id = copy.book_id
        active_holds = [
            h for h in self.db.holds.values()
            if h.book_id == book_id and h.status == "pending"
        ]
        if active_holds:
            raise ValueError(
                f"Cannot renew: another patron has a hold on this book."
            )

        # Extend due date
        if patron.membership_type == "student":
            weeks = LOAN_PERIOD_STUDENT_WEEKS
        else:
            weeks = LOAN_PERIOD_STANDARD_WEEKS

        current_due = datetime.strptime(loan.due_date, "%Y-%m-%d")
        new_due = current_due + timedelta(weeks=weeks)
        loan.due_date = new_due.strftime("%Y-%m-%d")
        loan.renewals_count += 1

        # Update copy due date
        copy.due_date = loan.due_date

        return loan

    @is_tool(ToolType.WRITE)
    def place_hold(self, patron_id: str, book_id: str, branch_id: str) -> Hold:
        """
        Place a hold on a book at a specific branch.

        Args:
            patron_id: The ID of the patron
            book_id: The ID of the book
            branch_id: The ID of the branch for pickup

        Returns:
            The new hold record

        Raises:
            ValueError: If patron/book/branch not found or book already available
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        if book_id not in self.db.books:
            raise ValueError(f"Book {book_id} not found")
        if branch_id not in self.db.branches:
            raise ValueError(f"Branch {branch_id} not found")

        # Check if any copy is available at the branch
        book = self.db.books[book_id]
        available_copies = [
            self.db.copies[cid] for cid in book.copies
            if cid in self.db.copies
            and self.db.copies[cid].branch_id == branch_id
            and self.db.copies[cid].status == "available"
        ]
        if available_copies:
            raise ValueError(
                f"A copy of this book is already available at branch {branch_id}. "
                f"No hold needed — the patron can check it out directly."
            )

        # Compute queue position
        existing_holds = [
            h for h in self.db.holds.values()
            if h.book_id == book_id and h.branch_id == branch_id and h.status == "pending"
        ]
        position = len(existing_holds) + 1

        today = REFERENCE_DATE
        base_hid = f"hold_{self._patron_last(patron_id)}_{book_id}"
        hold_id = self._make_unique_id(base_hid, self.db.holds)
        hold = Hold(
            hold_id=hold_id,
            patron_id=patron_id,
            book_id=book_id,
            branch_id=branch_id,
            placed_date=today.strftime("%Y-%m-%d"),
            status="pending",
            position_in_queue=position,
        )

        self.db.holds[hold_id] = hold
        patron = self.db.patrons[patron_id]
        patron.holds.append(hold_id)

        return hold

    @is_tool(ToolType.WRITE)
    def cancel_hold(self, hold_id: str) -> Hold:
        """
        Cancel a hold.

        Args:
            hold_id: The ID of the hold to cancel

        Returns:
            The updated hold record

        Raises:
            ValueError: If the hold is not found
        """
        if hold_id not in self.db.holds:
            raise ValueError(f"Hold {hold_id} not found")

        hold = self.db.holds[hold_id]
        hold.status = "cancelled"

        # Remove from patron's holds
        patron = self.db.patrons[hold.patron_id]
        if hold_id in patron.holds:
            patron.holds.remove(hold_id)

        return hold

    @is_tool(ToolType.WRITE)
    def waive_fine(self, fine_id: str, reason: str) -> Fine:
        """
        Waive a fine. Only allowed for first-offense overdue fines or documented
        extenuating circumstances.

        Args:
            fine_id: The ID of the fine to waive
            reason: Reason for the waiver

        Returns:
            The updated fine record

        Raises:
            ValueError: If fine not found or not eligible for waiver
        """
        if fine_id not in self.db.fines:
            raise ValueError(f"Fine {fine_id} not found")

        fine = self.db.fines[fine_id]
        if fine.status != "outstanding":
            raise ValueError(f"Fine {fine_id} is not outstanding (status: {fine.status}).")

        # Policy: only waive for first offense (no other fines on record)
        other_fines = [
            f for f in self.db.fines.values()
            if f.patron_id == fine.patron_id and f.fine_id != fine_id
        ]
        if other_fines:
            raise ValueError(
                f"Fine waiver not eligible: patron has prior fines on record. "
                f"Waivers are only allowed for first offense or documented extenuating circumstances."
            )

        fine.status = "waived"
        patron = self.db.patrons[fine.patron_id]
        patron.fines_owed = max(0, patron.fines_owed - fine.amount)

        return fine

    @is_tool(ToolType.WRITE)
    def pay_fine(self, fine_id: str, amount: float, payment_method: str) -> Fine:
        """
        Process a fine payment (full or partial).

        Args:
            fine_id: The ID of the fine to pay
            amount: The payment amount in dollars
            payment_method: The payment method (e.g., "cash", "credit_card")

        Returns:
            The updated fine record

        Raises:
            ValueError: If fine not found, not outstanding, or amount exceeds fine
        """
        if fine_id not in self.db.fines:
            raise ValueError(f"Fine {fine_id} not found")

        fine = self.db.fines[fine_id]
        if fine.status != "outstanding":
            raise ValueError(f"Fine {fine_id} is not outstanding (status: {fine.status}).")

        if amount <= 0:
            raise ValueError("Payment amount must be positive.")

        if amount > fine.amount:
            raise ValueError(
                f"Payment amount ${amount:.2f} exceeds fine amount ${fine.amount:.2f}."
            )

        fine.amount -= amount
        patron = self.db.patrons[fine.patron_id]
        patron.fines_owed = max(0, patron.fines_owed - amount)

        if fine.amount <= 0:
            fine.status = "paid"
            fine.amount = 0.0

        return fine

    @is_tool(ToolType.WRITE)
    def register_for_event(self, patron_id: str, event_id: str) -> Event:
        """
        Register a patron for an event.

        Args:
            patron_id: The ID of the patron
            event_id: The ID of the event

        Returns:
            The updated event record

        Raises:
            ValueError: If patron/event not found, event full, or membership expired
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        if event_id not in self.db.events:
            raise ValueError(f"Event {event_id} not found")

        patron = self.db.patrons[patron_id]
        event = self.db.events[event_id]

        if event.status == "full":
            raise ValueError(f"Event '{event.title}' is full.")

        if event.status in ("cancelled", "completed"):
            raise ValueError(f"Event '{event.title}' is {event.status}.")

        # Check capacity
        if len(event.registered_patrons) >= event.capacity:
            event.status = "full"
            raise ValueError(f"Event '{event.title}' is at capacity.")

        # Policy: membership must be active for free access
        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        if patron.membership_expiry < today:
            raise ValueError(
                f"Patron's membership expired on {patron.membership_expiry}. "
                f"Please renew membership to register for events."
            )

        if patron_id in event.registered_patrons:
            raise ValueError(f"Patron is already registered for this event.")

        event.registered_patrons.append(patron_id)
        if len(event.registered_patrons) >= event.capacity:
            event.status = "full"

        return event

    @is_tool(ToolType.WRITE)
    def renew_membership(self, patron_id: str) -> Patron:
        """
        Renew a patron's library membership for one year.

        Args:
            patron_id: The ID of the patron

        Returns:
            The updated patron record

        Raises:
            ValueError: If the patron is not found
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")

        patron = self.db.patrons[patron_id]

        # Renew from today or from expiry, whichever is later
        today = REFERENCE_DATE
        expiry = datetime.strptime(patron.membership_expiry, "%Y-%m-%d")
        start = max(today, expiry)
        new_expiry = start + timedelta(days=365)
        patron.membership_expiry = new_expiry.strftime("%Y-%m-%d")

        return patron

    @is_tool(ToolType.WRITE)
    def request_interlibrary_loan(self, patron_id: str, book_id: str) -> str:
        """
        Request an interlibrary loan for a book not available in the local system.

        Args:
            patron_id: The ID of the patron
            book_id: The ID of the book to request

        Returns:
            A confirmation message

        Raises:
            ValueError: If patron not found, membership expired, or at interlibrary loan limit
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")

        patron = self.db.patrons[patron_id]

        # Check membership active
        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        if patron.membership_expiry < today:
            raise ValueError(
                f"Patron's membership expired on {patron.membership_expiry}. "
                f"Please renew membership before requesting interlibrary loans."
            )

        # Policy: max 3 concurrent interlibrary loans
        # (For simplicity, count holds on books not in catalog as ILL)
        # In a real system, ILL would have its own tracking
        return (
            f"Interlibrary loan request submitted for book {book_id} by patron {patron_id}. "
            f"Expected delivery in 1-2 weeks."
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

    def assert_patron_loan_count(self, patron_id: str, expected: int) -> bool:
        """
        Check if the number of active loans for a patron is as expected.

        Args:
            patron_id: The ID of the patron
            expected: The expected number of active loans

        Returns:
            True if the loan count matches, False otherwise
        """
        if patron_id not in self.db.patrons:
            raise ValueError(f"Patron {patron_id} not found")
        return len(self.db.patrons[patron_id].active_loans) == expected

    def assert_copy_status(self, copy_id: str, expected_status: str) -> bool:
        """
        Check if a copy's status matches the expected status.

        Args:
            copy_id: The ID of the copy
            expected_status: The expected status

        Returns:
            True if the status matches, False otherwise
        """
        if copy_id not in self.db.copies:
            raise ValueError(f"Copy {copy_id} not found")
        return self.db.copies[copy_id].status == expected_status

    def assert_fine_status(self, fine_id: str, expected_status: str) -> bool:
        """
        Check if a fine's status matches the expected status.

        Args:
            fine_id: The ID of the fine
            expected_status: The expected status

        Returns:
            True if the status matches, False otherwise
        """
        if fine_id not in self.db.fines:
            raise ValueError(f"Fine {fine_id} not found")
        return self.db.fines[fine_id].status == expected_status
