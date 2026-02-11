import pytest

from tau2.data_model.message import ToolCall
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
from tau2.domains.library.environment import get_environment
from tau2.environment.environment import Environment


@pytest.fixture
def library_db() -> LibraryDB:
    return LibraryDB(
        patrons={
            "alice_johnson": Patron(
                patron_id="alice_johnson",
                name="Alice Johnson",
                email="alice@email.com",
                phone="555-0001",
                address="1 Main St",
                membership_type="standard",
                membership_expiry="2026-12-31",
                active_loans=["loan_alice_gatsby"],
                holds=[],
                fines_owed=12.50,
                borrowing_limit=10,
            ),
            "bob_smith": Patron(
                patron_id="bob_smith",
                name="Bob Smith",
                email="bob@university.edu",
                phone="555-0002",
                address="2 College Ave",
                membership_type="student",
                membership_expiry="2026-08-31",
                active_loans=["loan_bob_algorithms"],
                holds=[],
                fines_owed=0.0,
                borrowing_limit=15,
            ),
            "carol_davis": Patron(
                patron_id="carol_davis",
                name="Carol Davis",
                email="carol@email.com",
                phone="555-0003",
                address="3 Oak Lane",
                membership_type="standard",
                membership_expiry="2025-01-01",
                active_loans=[],
                holds=[],
                fines_owed=0.0,
                borrowing_limit=10,
            ),
        },
        books={
            "the_great_gatsby": Book(
                book_id="the_great_gatsby",
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                isbn="978-0743273565",
                category="fiction",
                copies=["gatsby_copy_1", "gatsby_copy_2"],
            ),
            "intro_to_algorithms": Book(
                book_id="intro_to_algorithms",
                title="Introduction to Algorithms",
                author="Thomas Cormen",
                isbn="978-0262033848",
                category="non-fiction",
                copies=["algorithms_copy"],
            ),
            "a_brief_history_of_time": Book(
                book_id="a_brief_history_of_time",
                title="A Brief History of Time",
                author="Stephen Hawking",
                isbn="978-0553380163",
                category="science",
                copies=["brief_history_copy"],
            ),
        },
        copies={
            "gatsby_copy_1": Copy(
                copy_id="gatsby_copy_1",
                book_id="the_great_gatsby",
                branch_id="central_library",
                status="checked_out",
                due_date="2026-02-01",
                borrower_id="alice_johnson",
            ),
            "gatsby_copy_2": Copy(
                copy_id="gatsby_copy_2",
                book_id="the_great_gatsby",
                branch_id="central_library",
                status="available",
                due_date=None,
                borrower_id=None,
            ),
            "algorithms_copy": Copy(
                copy_id="algorithms_copy",
                book_id="intro_to_algorithms",
                branch_id="central_library",
                status="checked_out",
                due_date="2026-03-01",
                borrower_id="bob_smith",
            ),
            "brief_history_copy": Copy(
                copy_id="brief_history_copy",
                book_id="a_brief_history_of_time",
                branch_id="central_library",
                status="available",
                due_date=None,
                borrower_id=None,
            ),
        },
        branches={
            "central_library": Branch(
                branch_id="central_library",
                name="Central Library",
                address="100 Main St",
                hours="Mon-Sat 9-9, Sun 12-6",
                phone="555-1000",
            ),
            "westside_branch": Branch(
                branch_id="westside_branch",
                name="Westside Branch",
                address="450 West Ave",
                hours="Mon-Fri 10-7, Sat 10-5",
                phone="555-2000",
            ),
        },
        loans={
            "loan_alice_gatsby": Loan(
                loan_id="loan_alice_gatsby",
                patron_id="alice_johnson",
                copy_id="gatsby_copy_1",
                checkout_date="2026-01-11",
                due_date="2026-02-01",
                return_date=None,
                renewals_count=0,
                fine_amount=0.0,
            ),
            "loan_bob_algorithms": Loan(
                loan_id="loan_bob_algorithms",
                patron_id="bob_smith",
                copy_id="algorithms_copy",
                checkout_date="2026-02-01",
                due_date="2026-03-01",
                return_date=None,
                renewals_count=0,
                fine_amount=0.0,
            ),
            "loan_alice_gatsby_old": Loan(
                loan_id="loan_alice_gatsby_old",
                patron_id="alice_johnson",
                copy_id="gatsby_copy_1",
                checkout_date="2025-11-01",
                due_date="2025-11-22",
                return_date="2025-12-01",
                renewals_count=0,
                fine_amount=2.25,
            ),
        },
        holds={
            "hold_bob_gatsby": Hold(
                hold_id="hold_bob_gatsby",
                patron_id="bob_smith",
                book_id="the_great_gatsby",
                branch_id="central_library",
                placed_date="2026-02-01",
                status="pending",
                position_in_queue=1,
                expiry_date=None,
            ),
        },
        fines={
            "fine_alice_1": Fine(
                fine_id="fine_alice_1",
                patron_id="alice_johnson",
                loan_id="loan_alice_gatsby",
                amount=8.50,
                reason="overdue",
                status="outstanding",
                issued_date="2026-02-05",
            ),
            "fine_alice_2": Fine(
                fine_id="fine_alice_2",
                patron_id="alice_johnson",
                loan_id="loan_alice_gatsby_old",
                amount=4.00,
                reason="overdue",
                status="outstanding",
                issued_date="2025-12-01",
            ),
        },
        events={
            "story_hour": Event(
                event_id="story_hour",
                branch_id="central_library",
                title="Story Hour",
                description="Story time for kids.",
                date="2026-02-14",
                time="10:00",
                capacity=20,
                registered_patrons=[],
                status="upcoming",
            ),
            "book_club": Event(
                event_id="book_club",
                branch_id="central_library",
                title="Book Club",
                description="Monthly book club.",
                date="2026-02-20",
                time="18:30",
                capacity=2,
                registered_patrons=["alice_johnson"],
                status="upcoming",
            ),
        },
    )


@pytest.fixture
def environment(library_db: LibraryDB) -> Environment:
    return get_environment(library_db)


# ── READ tool tests ──────────────────────────────────────────────────────


def test_find_patron_by_name(environment: Environment):
    call = ToolCall(id="1", name="find_patron_by_name", arguments={"name": "Alice"})
    response = environment.get_response(call)
    assert not response.error
    assert "Alice Johnson" in response.content

    # Not found
    call = ToolCall(id="2", name="find_patron_by_name", arguments={"name": "Nonexistent"})
    response = environment.get_response(call)
    assert not response.error
    assert "[]" in response.content


def test_find_patron_by_card(environment: Environment):
    call = ToolCall(id="1", name="find_patron_by_card", arguments={"card_number": "alice_johnson"})
    response = environment.get_response(call)
    assert not response.error
    assert "Alice Johnson" in response.content

    # Not found
    call = ToolCall(id="2", name="find_patron_by_card", arguments={"card_number": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


def test_find_branch_by_name(environment: Environment):
    call = ToolCall(id="1", name="find_branch_by_name", arguments={"name": "Central"})
    response = environment.get_response(call)
    assert not response.error
    assert "Central Library" in response.content
    assert "central_library" in response.content

    # Partial match on Westside
    call = ToolCall(id="2", name="find_branch_by_name", arguments={"name": "westside"})
    response = environment.get_response(call)
    assert not response.error
    assert "Westside Branch" in response.content
    assert "westside_branch" in response.content

    # Not found
    call = ToolCall(id="3", name="find_branch_by_name", arguments={"name": "Nonexistent"})
    response = environment.get_response(call)
    assert not response.error
    assert "[]" in response.content


def test_get_patron_details(environment: Environment):
    call = ToolCall(id="1", name="get_patron_details", arguments={"patron_id": "alice_johnson"})
    response = environment.get_response(call)
    assert not response.error
    assert "Alice Johnson" in response.content

    # Not found
    call = ToolCall(id="2", name="get_patron_details", arguments={"patron_id": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


def test_search_catalog_by_title(environment: Environment):
    call = ToolCall(id="1", name="search_catalog", arguments={"title": "Gatsby"})
    response = environment.get_response(call)
    assert not response.error
    assert "Great Gatsby" in response.content


def test_search_catalog_by_author(environment: Environment):
    call = ToolCall(id="1", name="search_catalog", arguments={"author": "Hawking"})
    response = environment.get_response(call)
    assert not response.error
    assert "Brief History" in response.content


def test_search_catalog_by_category(environment: Environment):
    call = ToolCall(id="1", name="search_catalog", arguments={"category": "science"})
    response = environment.get_response(call)
    assert not response.error
    assert "Brief History" in response.content


def test_get_book_availability(environment: Environment):
    call = ToolCall(id="1", name="get_book_availability", arguments={"book_id": "the_great_gatsby"})
    response = environment.get_response(call)
    assert not response.error
    assert "gatsby_copy_1" in response.content
    assert "gatsby_copy_2" in response.content

    # Not found
    call = ToolCall(id="2", name="get_book_availability", arguments={"book_id": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


def test_get_loan_details(environment: Environment):
    call = ToolCall(id="1", name="get_loan_details", arguments={"loan_id": "loan_alice_gatsby"})
    response = environment.get_response(call)
    assert not response.error
    assert "loan_alice_gatsby" in response.content

    # Not found
    call = ToolCall(id="2", name="get_loan_details", arguments={"loan_id": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


def test_list_patron_loans(environment: Environment):
    call = ToolCall(id="1", name="list_patron_loans", arguments={"patron_id": "alice_johnson"})
    response = environment.get_response(call)
    assert not response.error
    assert "loan_alice_gatsby" in response.content


def test_list_patron_fines(environment: Environment):
    call = ToolCall(id="1", name="list_patron_fines", arguments={"patron_id": "alice_johnson"})
    response = environment.get_response(call)
    assert not response.error
    assert "fine_alice_1" in response.content
    assert "fine_alice_2" in response.content


def test_list_events(environment: Environment):
    call = ToolCall(id="1", name="list_events", arguments={"branch_id": "central_library"})
    response = environment.get_response(call)
    assert not response.error
    assert "Story Hour" in response.content

    # Branch not found
    call = ToolCall(id="2", name="list_events", arguments={"branch_id": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


# ── WRITE tool tests ─────────────────────────────────────────────────────


def test_checkout_book_blocked_by_fines(environment: Environment):
    # alice_johnson has $12.50 in fines — checkout should be blocked
    call = ToolCall(
        id="1",
        name="checkout_book",
        arguments={"patron_id": "alice_johnson", "copy_id": "brief_history_copy"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "fines" in response.content.lower()


def test_checkout_book_expired_membership(environment: Environment):
    # carol_davis has expired membership
    call = ToolCall(
        id="1",
        name="checkout_book",
        arguments={"patron_id": "carol_davis", "copy_id": "brief_history_copy"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "expired" in response.content.lower()


def test_checkout_book_success(environment: Environment):
    # bob_smith has no fines, active membership, and room for more loans
    call = ToolCall(
        id="1",
        name="checkout_book",
        arguments={"patron_id": "bob_smith", "copy_id": "brief_history_copy"},
    )
    response = environment.get_response(call)
    assert not response.error

    # Verify DB state
    copy = environment.tools.db.copies["brief_history_copy"]
    assert copy.status == "checked_out"
    assert copy.borrower_id == "bob_smith"
    patron = environment.tools.db.patrons["bob_smith"]
    assert len(patron.active_loans) == 2


def test_checkout_book_at_borrowing_limit(environment: Environment, library_db: LibraryDB):
    # Fill bob_smith up to borrowing limit
    patron = library_db.patrons["bob_smith"]
    patron.active_loans = [f"loan_fake_{i}" for i in range(15)]
    env = get_environment(library_db)

    call = ToolCall(
        id="1",
        name="checkout_book",
        arguments={"patron_id": "bob_smith", "copy_id": "brief_history_copy"},
    )
    response = env.get_response(call)
    assert response.error
    assert "borrowing limit" in response.content.lower()


def test_return_book_success(environment: Environment):
    # Return gatsby_copy_1 (checked out by alice_johnson, loan_alice_gatsby)
    call = ToolCall(id="1", name="return_book", arguments={"copy_id": "gatsby_copy_1"})
    response = environment.get_response(call)
    assert not response.error

    copy = environment.tools.db.copies["gatsby_copy_1"]
    assert copy.status == "available"
    assert copy.borrower_id is None
    patron = environment.tools.db.patrons["alice_johnson"]
    assert "loan_alice_gatsby" not in patron.active_loans


def test_return_book_not_checked_out(environment: Environment):
    call = ToolCall(id="1", name="return_book", arguments={"copy_id": "gatsby_copy_2"})
    response = environment.get_response(call)
    assert response.error


def test_renew_loan_success(environment: Environment):
    # loan_bob_algorithms (bob_smith, student) has 0 renewals and no holds on intro_to_algorithms
    call = ToolCall(id="1", name="renew_loan", arguments={"loan_id": "loan_bob_algorithms"})
    response = environment.get_response(call)
    assert not response.error

    loan = environment.tools.db.loans["loan_bob_algorithms"]
    assert loan.renewals_count == 1


def test_renew_loan_blocked_by_hold(environment: Environment):
    # loan_alice_gatsby is for gatsby_copy_1 (the_great_gatsby), and hold_bob_gatsby is pending on the_great_gatsby
    call = ToolCall(id="1", name="renew_loan", arguments={"loan_id": "loan_alice_gatsby"})
    response = environment.get_response(call)
    assert response.error
    assert "hold" in response.content.lower()


def test_renew_loan_max_renewals(environment: Environment):
    # Set loan_bob_algorithms to max renewals for student (3)
    environment.tools.db.loans["loan_bob_algorithms"].renewals_count = 3
    call = ToolCall(id="1", name="renew_loan", arguments={"loan_id": "loan_bob_algorithms"})
    response = environment.get_response(call)
    assert response.error
    assert "maximum" in response.content.lower() or "renewals" in response.content.lower()


def test_place_hold_success(environment: Environment):
    # Place hold on intro_to_algorithms at central_library (algorithms_copy is checked out, so hold is valid)
    call = ToolCall(
        id="1",
        name="place_hold",
        arguments={
            "patron_id": "alice_johnson",
            "book_id": "intro_to_algorithms",
            "branch_id": "central_library",
        },
    )
    response = environment.get_response(call)
    assert not response.error

    patron = environment.tools.db.patrons["alice_johnson"]
    assert len(patron.holds) == 1


def test_place_hold_book_available(environment: Environment):
    # the_great_gatsby has gatsby_copy_2 available at central_library — hold should fail
    call = ToolCall(
        id="1",
        name="place_hold",
        arguments={
            "patron_id": "bob_smith",
            "book_id": "the_great_gatsby",
            "branch_id": "central_library",
        },
    )
    response = environment.get_response(call)
    assert response.error
    assert "available" in response.content.lower()


def test_cancel_hold_success(environment: Environment):
    call = ToolCall(id="1", name="cancel_hold", arguments={"hold_id": "hold_bob_gatsby"})
    response = environment.get_response(call)
    assert not response.error

    hold = environment.tools.db.holds["hold_bob_gatsby"]
    assert hold.status == "cancelled"


def test_cancel_hold_not_found(environment: Environment):
    call = ToolCall(id="1", name="cancel_hold", arguments={"hold_id": "nonexistent"})
    response = environment.get_response(call)
    assert response.error


def test_waive_fine_not_eligible(environment: Environment):
    # alice_johnson has two fines (fine_alice_1 and fine_alice_2)
    # Since there are multiple fines, waiver should not be eligible
    call = ToolCall(
        id="1",
        name="waive_fine",
        arguments={"fine_id": "fine_alice_1", "reason": "First time"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "not eligible" in response.content.lower() or "prior fines" in response.content.lower()


def test_waive_fine_success(environment: Environment):
    # Create a patron with only one fine (first offense)
    environment.tools.db.patrons["patron_solo"] = Patron(
        patron_id="patron_solo",
        name="Solo Finer",
        email="solo@email.com",
        phone="555-9999",
        address="9 Solo St",
        membership_type="standard",
        membership_expiry="2026-12-31",
        active_loans=[],
        holds=[],
        fines_owed=5.00,
        borrowing_limit=10,
    )
    environment.tools.db.fines["fine_solo"] = Fine(
        fine_id="fine_solo",
        patron_id="patron_solo",
        loan_id="loan_alice_gatsby",
        amount=5.00,
        reason="overdue",
        status="outstanding",
        issued_date="2026-02-01",
    )
    call = ToolCall(
        id="1",
        name="waive_fine",
        arguments={"fine_id": "fine_solo", "reason": "First offense"},
    )
    response = environment.get_response(call)
    assert not response.error

    fine = environment.tools.db.fines["fine_solo"]
    assert fine.status == "waived"
    patron = environment.tools.db.patrons["patron_solo"]
    assert patron.fines_owed == 0.0


def test_pay_fine_success(environment: Environment):
    call = ToolCall(
        id="1",
        name="pay_fine",
        arguments={"fine_id": "fine_alice_1", "amount": 8.50, "payment_method": "cash"},
    )
    response = environment.get_response(call)
    assert not response.error

    fine = environment.tools.db.fines["fine_alice_1"]
    assert fine.status == "paid"
    assert fine.amount == 0.0
    patron = environment.tools.db.patrons["alice_johnson"]
    assert patron.fines_owed == 4.00


def test_pay_fine_partial(environment: Environment):
    call = ToolCall(
        id="1",
        name="pay_fine",
        arguments={"fine_id": "fine_alice_1", "amount": 3.00, "payment_method": "credit_card"},
    )
    response = environment.get_response(call)
    assert not response.error

    fine = environment.tools.db.fines["fine_alice_1"]
    assert fine.status == "outstanding"
    assert fine.amount == 5.50
    patron = environment.tools.db.patrons["alice_johnson"]
    assert patron.fines_owed == 9.50


def test_pay_fine_exceeds_amount(environment: Environment):
    call = ToolCall(
        id="1",
        name="pay_fine",
        arguments={"fine_id": "fine_alice_1", "amount": 100.00, "payment_method": "cash"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "exceeds" in response.content.lower()


def test_register_for_event_success(environment: Environment):
    call = ToolCall(
        id="1",
        name="register_for_event",
        arguments={"patron_id": "alice_johnson", "event_id": "story_hour"},
    )
    response = environment.get_response(call)
    assert not response.error

    event = environment.tools.db.events["story_hour"]
    assert "alice_johnson" in event.registered_patrons


def test_register_for_event_full(environment: Environment):
    # book_club has capacity 2, alice_johnson is already registered
    # Register bob_smith to fill it
    call = ToolCall(
        id="1",
        name="register_for_event",
        arguments={"patron_id": "bob_smith", "event_id": "book_club"},
    )
    response = environment.get_response(call)
    assert not response.error

    # Now event is full, try adding another valid patron
    environment.tools.db.patrons["patron_extra"] = Patron(
        patron_id="patron_extra",
        name="Extra Person",
        email="extra@email.com",
        phone="555-8888",
        address="8 Extra Rd",
        membership_type="standard",
        membership_expiry="2026-12-31",
        active_loans=[],
        holds=[],
        fines_owed=0.0,
        borrowing_limit=10,
    )
    call = ToolCall(
        id="2",
        name="register_for_event",
        arguments={"patron_id": "patron_extra", "event_id": "book_club"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "full" in response.content.lower() or "capacity" in response.content.lower()


def test_register_for_event_expired_membership(environment: Environment):
    # carol_davis has expired membership
    call = ToolCall(
        id="1",
        name="register_for_event",
        arguments={"patron_id": "carol_davis", "event_id": "story_hour"},
    )
    response = environment.get_response(call)
    assert response.error
    assert "expired" in response.content.lower()


def test_renew_membership(environment: Environment):
    # carol_davis has expired membership (2025-01-01)
    call = ToolCall(
        id="1",
        name="renew_membership",
        arguments={"patron_id": "carol_davis"},
    )
    response = environment.get_response(call)
    assert not response.error

    patron = environment.tools.db.patrons["carol_davis"]
    # Should be renewed for a year from today (since it's already expired)
    assert patron.membership_expiry > "2026-12-31"


def test_request_interlibrary_loan(environment: Environment):
    call = ToolCall(
        id="1",
        name="request_interlibrary_loan",
        arguments={"patron_id": "bob_smith", "book_id": "book_99"},
    )
    response = environment.get_response(call)
    assert not response.error
    assert "submitted" in response.content.lower()


def test_transfer_to_human_agents(environment: Environment):
    call = ToolCall(
        id="1",
        name="transfer_to_human_agents",
        arguments={"summary": "Patron needs help with a complex issue."},
    )
    response = environment.get_response(call)
    assert not response.error
    assert "transfer successful" in response.content.lower()


def test_calculate(environment: Environment):
    call = ToolCall(id="1", name="calculate", arguments={"expression": "12.50 - 3.00"})
    response = environment.get_response(call)
    assert not response.error
    assert "9.5" in response.content


# ── Assertion helper tests ───────────────────────────────────────────────


def test_assert_patron_loan_count(environment: Environment):
    assert environment.tools.assert_patron_loan_count("alice_johnson", 1)
    assert not environment.tools.assert_patron_loan_count("alice_johnson", 5)


def test_assert_copy_status(environment: Environment):
    assert environment.tools.assert_copy_status("gatsby_copy_1", "checked_out")
    assert not environment.tools.assert_copy_status("gatsby_copy_1", "available")


def test_assert_fine_status(environment: Environment):
    assert environment.tools.assert_fine_status("fine_alice_1", "outstanding")
    assert not environment.tools.assert_fine_status("fine_alice_1", "paid")
