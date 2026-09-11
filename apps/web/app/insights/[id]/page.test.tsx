import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getInsight } = vi.hoisted(() => ({ getInsight: vi.fn() }));
vi.mock("@/lib/api", () => ({ getInsight }));

const { redirect, notFound } = vi.hoisted(() => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
  notFound: vi.fn(() => {
    throw new Error("NOT_FOUND");
  }),
}));
vi.mock("next/navigation", () => ({ redirect, notFound }));

const { default: InsightDetailPage } = await import("./page");

describe("InsightDetailPage", () => {
  beforeEach(() => {
    getInsight.mockReset();
    redirect.mockClear();
    notFound.mockClear();
  });

  it("redirects to /login when the session is unauthorized", async () => {
    getInsight.mockResolvedValue({
      data: null,
      error: { code: "UNAUTHORIZED", message: "Not authenticated." },
    });

    await expect(InsightDetailPage({ params: Promise.resolve({ id: "1" }) })).rejects.toThrow(
      "REDIRECT:/login",
    );
  });

  it("calls notFound when the insight does not exist", async () => {
    getInsight.mockResolvedValue({
      data: null,
      error: { code: "RESOURCE_NOT_FOUND", message: "Insight not found." },
    });

    await expect(InsightDetailPage({ params: Promise.resolve({ id: "1" }) })).rejects.toThrow(
      "NOT_FOUND",
    );
  });

  it("renders a generic error message for any other failure", async () => {
    getInsight.mockResolvedValue({
      data: null,
      error: { code: "INTERNAL_ERROR", message: "The API is unreachable." },
    });

    const element = await InsightDetailPage({ params: Promise.resolve({ id: "1" }) });
    render(element);

    expect(
      screen.getByText("Could not load this insight: The API is unreachable."),
    ).toBeInTheDocument();
  });

  it("renders insight details and actions on success", async () => {
    getInsight.mockResolvedValue({
      data: {
        id: "1",
        title: "Wait times climbing",
        summary: "Customers mention longer waits in recent reviews.",
        severity: "medium",
        evidence_summary: "Seen in 6 of the last 20 reviews.",
        status: "monitoring",
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
        resolved_at: null,
        related_review_ids: [],
        actions: [
          {
            id: "a1",
            action_text: "Add extra coverage Friday evening.",
            action_date: null,
            note_text: "Two-week trial.",
            status: "planned",
            created_at: "2026-09-01T00:00:00Z",
            updated_at: "2026-09-01T00:00:00Z",
          },
        ],
        impact: null,
      },
      error: null,
    });

    const element = await InsightDetailPage({ params: Promise.resolve({ id: "1" }) });
    render(element);

    expect(screen.getByText("Wait times climbing")).toBeInTheDocument();
    expect(screen.getByText("Add extra coverage Friday evening.")).toBeInTheDocument();
    expect(screen.getByText(/Not computed yet/)).toBeInTheDocument();
  });
});
