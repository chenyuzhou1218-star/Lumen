// Shelf page: shows free copies and borrows a book.
const API = "http://127.0.0.1:8090";

async function showBook(id) {
  const res = await fetch(`${API}/api/book?id=${id}`);
  const data = await res.json();
  document.getElementById(id).textContent = `${data.title}: ${data.avail} free`;
}

async function borrow(memberId, bookId) {
  const res = await fetch(`${API}/api/borrow`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ memberId: memberId, book_id: bookId }),
  });
  const data = await res.json();
  alert(res.ok ? `Due ${data.due}` : data.error);
  showBook(bookId);
}
