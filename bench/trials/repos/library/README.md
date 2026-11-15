# library

Members borrow books (a limit per membership tier), return them, pay fines for late returns, put books on hold
when no copy is free, and get a notification when a held book comes back. Loans can be renewed unless someone is
waiting. Staff see overdue loans and fine revenue.

Server in Python (lib/), browser page in plain JavaScript (web/). Policy numbers live in lib/policy.py.
