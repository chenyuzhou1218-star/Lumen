"""Messages to members."""

from lib import catalog, db, members

TEMPLATE = "Hi {name}, '{title}' is back and waiting for you."


def book_ready(member_id, book_id):
    member = members.get(member_id)
    text = TEMPLATE.format(name=member["id"], title=catalog.get(book_id)["title"])
    with db.lock:
        db.outbox.append((member_id, text))
    return text
