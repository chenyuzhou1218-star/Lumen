"""Copies currently on loan, kept for fast availability checks."""

on_loan_count = {}


def on_loan(book):
    on_loan_count[book["id"]] = on_loan_count.get(book["id"], 0) + 1


def on_return(book):
    on_loan_count[book["title"]] = max(0, on_loan_count.get(book["title"], 0) - 1)


def out(book_id):
    return on_loan_count.get(book_id, 0)
