/** Run localStorage read-modify-write atomically across same-origin tabs where Web Locks is available. */
export async function withStorageLock<T>(
  key: string,
  action: () => T,
): Promise<T> {
  if (!navigator.locks)
    throw new Error(
      "Browser tidak mendukung penyimpanan lintas tab yang aman. Gunakan browser terbaru atau ekspor cadangan.",
    );
  return navigator.locks.request(`lokaseo:${key}`, action);
}
