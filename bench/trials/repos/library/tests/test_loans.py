from lib import db, loans


def test_borrow_creates_an_active_loan():
    loan = loans.borrow("m1", "b2")
    assert db.loans[loan["id"]]["status"] == "active"


def test_return_marks_it_returned():
    loan = loans.borrow("m3", "b2")
    assert loans.give_back(loan["id"])["status"] == "returned"
