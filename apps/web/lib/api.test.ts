import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined })),
}));

const { apiGet, getReview, getInsight } = await import("./api");

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiGet", () => {
  it("returns the parsed envelope on a successful response", async () => {
    const payload = { data: { id: "1" }, error: null };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(payload))),
    );

    await expect(apiGet<{ id: string }>("/anything")).resolves.toEqual(payload);
  });

  it("returns an INTERNAL_ERROR envelope when the network call throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );

    const result = await apiGet("/anything");
    expect(result.data).toBeNull();
    expect(result.error?.code).toBe("INTERNAL_ERROR");
  });
});

describe("getReview", () => {
  it("requests the review detail endpoint by id", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: null, error: null })));
    vi.stubGlobal("fetch", fetchMock);

    await getReview("abc-123");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/reviews/abc-123"),
      expect.any(Object),
    );
  });
});

describe("getInsight", () => {
  it("requests the insight detail endpoint by id", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: null, error: null })));
    vi.stubGlobal("fetch", fetchMock);

    await getInsight("xyz-789");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/insights/xyz-789"),
      expect.any(Object),
    );
  });
});
