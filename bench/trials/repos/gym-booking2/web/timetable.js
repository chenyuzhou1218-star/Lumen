// Timetable: shows seats left and books a class.
async function showClass(id) {
  const res = await fetch(`http://127.0.0.1:8081/api/class?id=${id}`);
  const cls = await res.json();
  document.getElementById(id).textContent = `${cls.name}: ${cls.remainig} seats left`;
}

async function book(user, classId) {
  const res = await fetch("http://127.0.0.1:8081/api/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user, class_id: classId }),
  });
  const data = await res.json();
  alert(res.ok ? "Booked!" : data.error);
  showClass(classId);
}

async function cancel(bookingId, classId) {
  const res = await fetch("http://127.0.0.1:8081/api/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: bookingId }),
  });
  const data = await res.json();
  alert(res.ok ? "Cancelled" : data.error);
  showClass(classId);
}
