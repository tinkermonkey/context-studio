import { describe, it, expect } from "vitest";
import { IDLE_CUTOFF_MS, activeMsAt, recordActivity, startClock } from "../reviewTiming";

describe("active review time", () => {
  it("counts the time since the clock started", () => {
    const clock = startClock(1_000);
    expect(activeMsAt(clock, 1_000)).toBe(0);
    expect(activeMsAt(clock, 6_000)).toBe(5_000);
  });

  it("adds up the gaps between activity", () => {
    let clock = startClock(0);
    clock = recordActivity(clock, 10_000);
    clock = recordActivity(clock, 25_000);
    expect(clock.activeMs).toBe(25_000);
    expect(activeMsAt(clock, 30_000)).toBe(30_000);
  });

  it("leaves out an idle gap longer than two minutes", () => {
    let clock = startClock(0);
    clock = recordActivity(clock, 10_000);
    // Away for three minutes, then back.
    clock = recordActivity(clock, 10_000 + 3 * 60_000);
    expect(clock.activeMs).toBe(10_000);
    expect(activeMsAt(clock, 10_000 + 3 * 60_000 + 4_000)).toBe(14_000);
  });

  it("counts a gap of exactly the cutoff", () => {
    const clock = recordActivity(startClock(0), IDLE_CUTOFF_MS);
    expect(clock.activeMs).toBe(IDLE_CUTOFF_MS);
  });

  it("does not count the time after the last activity once it passes the cutoff", () => {
    const clock = recordActivity(startClock(0), 5_000);
    expect(activeMsAt(clock, 5_000 + IDLE_CUTOFF_MS + 1)).toBe(5_000);
  });

  it("ignores a clock that went backwards", () => {
    const clock = recordActivity(startClock(10_000), 4_000);
    expect(clock.activeMs).toBe(0);
    expect(activeMsAt(clock, 4_000)).toBe(0);
  });
});
