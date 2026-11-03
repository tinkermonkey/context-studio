import { describe, it, expect, vi } from "vitest";
import { ID_CHUNK_SIZE, listByIdChunks, uniqueIds } from "../idChunks";

describe("idChunks", () => {
  it("dedupes, drops empties and sorts ids", () => {
    expect(uniqueIds(["b", null, "a", "b", undefined, ""])).toEqual(["a", "b"]);
  });

  it("fetches in chunks of 100 and merges the pages", async () => {
    const ids = Array.from({ length: 250 }, (_, i) => `id-${String(i).padStart(3, "0")}`);
    const fetchChunk = vi.fn(async (chunk: string[]) => ({
      items: chunk.map((id) => ({ id })),
      total: chunk.length,
      limit: chunk.length,
      offset: 0,
    }));

    const merged = await listByIdChunks(ids, fetchChunk);

    expect(fetchChunk.mock.calls.map(([chunk]) => chunk.length)).toEqual([
      ID_CHUNK_SIZE,
      ID_CHUNK_SIZE,
      50,
    ]);
    expect(merged.items.map((item) => item.id)).toEqual(ids);
    expect(merged).toMatchObject({ total: 250, limit: 250, offset: 0 });
  });
});
