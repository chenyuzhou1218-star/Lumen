export async function retryFetch(url, options, attempts = 3) {
  for (let i = 0; i < attempts; i++) {
    try {
      return await fetch(url, options);
    } catch (e) {
      if (i === attempts - 1) throw e;
    }
  }
}
