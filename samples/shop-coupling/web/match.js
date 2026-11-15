export async function finishMatch(match) {
  await fetch("/api/match/settle", { method: "POST", body: JSON.stringify({ match }) });
  await fetch("/api/match/report", { method: "POST", body: JSON.stringify({ match }) });
}
