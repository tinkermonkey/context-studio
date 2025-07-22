/**
 * Renders a date into a friendly short date-time string.
 * Example: "Jun 5, 2:30 PM"
 * @param date Date object or ISO date string
 * @returns formatted string
 */
export function renderShortDateTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Renders a v4 UUID into a shortened string showing the head and tail.
 * Example: "9665582e...1006"
 * @param uuid v4 UUID string
 * @returns shortened string or original if invalid
 */
export function renderShortUuid(uuid: string): string {
  if (!uuid || typeof uuid !== 'string') return '';
  uuid = uuid.trim();
  // v4 UUID regex: 8-4-4-4-12 hex digits
  const match = uuid.match(/^([a-fA-F0-9]{8})-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-([a-fA-F0-9]{12})$/);
  if (!match) return uuid;
  // Use first 8 and last 4 hex digits
  return `${match[1]}...${match[2].slice(-4)}`;
}
