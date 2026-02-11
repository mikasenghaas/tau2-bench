from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.library.utils import LIBRARY_DB_PATH
from tau2.environment.db import DB

MembershipType = Literal["standard", "student", "senior", "child"]
CopyStatus = Literal["available", "checked_out", "on_hold", "in_transit", "damaged", "lost"]
HoldStatus = Literal["pending", "ready", "expired", "cancelled"]
FineReason = Literal["overdue", "lost", "damaged"]
FineStatus = Literal["outstanding", "paid", "waived"]
EventStatus = Literal["upcoming", "full", "cancelled", "completed"]


class Patron(BaseModel):
    patron_id: str = Field(description="Unique identifier for the patron")
    name: str = Field(description="Patron's full name")
    email: str = Field(description="Patron's email address")
    phone: str = Field(description="Patron's phone number")
    address: str = Field(description="Patron's mailing address")
    membership_type: MembershipType = Field(description="Type of library membership")
    membership_expiry: str = Field(description="Membership expiration date (YYYY-MM-DD)")
    active_loans: List[str] = Field(default_factory=list, description="List of active loan IDs")
    holds: List[str] = Field(default_factory=list, description="List of active hold IDs")
    fines_owed: float = Field(default=0.0, description="Total outstanding fines in dollars")
    borrowing_limit: int = Field(description="Maximum number of books the patron can borrow")


class Book(BaseModel):
    book_id: str = Field(description="Unique identifier for the book")
    title: str = Field(description="Book title")
    author: str = Field(description="Book author")
    isbn: str = Field(description="ISBN number")
    category: str = Field(description="Book category (e.g., fiction, non-fiction, science)")
    copies: List[str] = Field(default_factory=list, description="List of copy IDs for this book")


class Copy(BaseModel):
    copy_id: str = Field(description="Unique identifier for the copy")
    book_id: str = Field(description="ID of the book this copy belongs to")
    branch_id: str = Field(description="ID of the branch where this copy is located")
    status: CopyStatus = Field(description="Current status of the copy")
    due_date: Optional[str] = Field(None, description="Due date if checked out (YYYY-MM-DD)")
    borrower_id: Optional[str] = Field(None, description="Patron ID of the current borrower")


class Branch(BaseModel):
    branch_id: str = Field(description="Unique identifier for the branch")
    name: str = Field(description="Branch name")
    address: str = Field(description="Branch address")
    hours: str = Field(description="Operating hours")
    phone: str = Field(description="Branch phone number")


class Loan(BaseModel):
    loan_id: str = Field(description="Unique identifier for the loan")
    patron_id: str = Field(description="ID of the borrowing patron")
    copy_id: str = Field(description="ID of the borrowed copy")
    checkout_date: str = Field(description="Date the book was checked out (YYYY-MM-DD)")
    due_date: str = Field(description="Date the book is due (YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, description="Date the book was returned (YYYY-MM-DD)")
    renewals_count: int = Field(default=0, description="Number of times the loan has been renewed")
    fine_amount: float = Field(default=0.0, description="Fine amount accrued on this loan")


class Hold(BaseModel):
    hold_id: str = Field(description="Unique identifier for the hold")
    patron_id: str = Field(description="ID of the patron who placed the hold")
    book_id: str = Field(description="ID of the book being held")
    branch_id: str = Field(description="ID of the branch for pickup")
    placed_date: str = Field(description="Date the hold was placed (YYYY-MM-DD)")
    status: HoldStatus = Field(description="Current status of the hold")
    position_in_queue: int = Field(description="Position in the hold queue")
    expiry_date: Optional[str] = Field(None, description="Date the hold expires (YYYY-MM-DD)")


class Fine(BaseModel):
    fine_id: str = Field(description="Unique identifier for the fine")
    patron_id: str = Field(description="ID of the patron who owes the fine")
    loan_id: str = Field(description="ID of the loan associated with the fine")
    amount: float = Field(description="Fine amount in dollars")
    reason: FineReason = Field(description="Reason for the fine")
    status: FineStatus = Field(description="Current status of the fine")
    issued_date: str = Field(description="Date the fine was issued (YYYY-MM-DD)")


class Event(BaseModel):
    event_id: str = Field(description="Unique identifier for the event")
    branch_id: str = Field(description="ID of the branch hosting the event")
    title: str = Field(description="Event title")
    description: str = Field(description="Event description")
    date: str = Field(description="Event date (YYYY-MM-DD)")
    time: str = Field(description="Event time (HH:MM)")
    capacity: int = Field(description="Maximum number of attendees")
    registered_patrons: List[str] = Field(default_factory=list, description="List of registered patron IDs")
    status: EventStatus = Field(description="Current status of the event")


class LibraryDB(DB):
    """Public library database with patrons, books, copies, branches, loans, holds, fines, and events."""

    patrons: Dict[str, Patron] = Field(
        description="Dictionary of all patrons indexed by patron ID"
    )
    books: Dict[str, Book] = Field(
        description="Dictionary of all books indexed by book ID"
    )
    copies: Dict[str, Copy] = Field(
        description="Dictionary of all copies indexed by copy ID"
    )
    branches: Dict[str, Branch] = Field(
        description="Dictionary of all branches indexed by branch ID"
    )
    loans: Dict[str, Loan] = Field(
        description="Dictionary of all loans indexed by loan ID"
    )
    holds: Dict[str, Hold] = Field(
        description="Dictionary of all holds indexed by hold ID"
    )
    fines: Dict[str, Fine] = Field(
        description="Dictionary of all fines indexed by fine ID"
    )
    events: Dict[str, Event] = Field(
        description="Dictionary of all events indexed by event ID"
    )

    def get_statistics(self) -> dict[str, Any]:
        """Get the statistics of the database."""
        num_patrons = len(self.patrons)
        num_books = len(self.books)
        num_copies = len(self.copies)
        num_branches = len(self.branches)
        num_active_loans = len([l for l in self.loans.values() if l.return_date is None])
        num_holds = len([h for h in self.holds.values() if h.status == "pending"])
        num_outstanding_fines = len([f for f in self.fines.values() if f.status == "outstanding"])
        num_events = len(self.events)
        return {
            "num_patrons": num_patrons,
            "num_books": num_books,
            "num_copies": num_copies,
            "num_branches": num_branches,
            "num_active_loans": num_active_loans,
            "num_pending_holds": num_holds,
            "num_outstanding_fines": num_outstanding_fines,
            "num_events": num_events,
        }


def get_db():
    return LibraryDB.load(LIBRARY_DB_PATH)
