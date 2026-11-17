/**
 * Active review time: the time between pointer or key activity, leaving out
 * any idle gap of more than IDLE_CUTOFF_MS (the reviewer stepped away).
 * Pure: every function takes the current time.
 */

/** An idle gap longer than this is not counted. */
export const IDLE_CUTOFF_MS = 2 * 60 * 1000;

export interface ActiveClock {
  /** When the reviewer was last active (or the clock started). */
  lastActivity: number;
  /** Active time counted up to lastActivity. */
  activeMs: number;
}

export function startClock(now: number): ActiveClock {
  return { lastActivity: now, activeMs: 0 };
}

/** The part of a gap that counts: all of it, unless it is longer than the cutoff. */
function counted(gap: number): number {
  return gap >= 0 && gap <= IDLE_CUTOFF_MS ? gap : 0;
}

/** The clock after activity at `now`. */
export function recordActivity(clock: ActiveClock, now: number): ActiveClock {
  return { lastActivity: now, activeMs: clock.activeMs + counted(now - clock.lastActivity) };
}

/** Active milliseconds at `now`, as a whole number. */
export function activeMsAt(clock: ActiveClock, now: number): number {
  return Math.round(clock.activeMs + counted(now - clock.lastActivity));
}
