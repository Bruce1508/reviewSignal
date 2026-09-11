import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getReview } = vi.hoisted(() => ({ getReview: vi.fn() }));
vi.mock("@/lib/api", () => ({ getReview }));

const { redirect, notFound } = vi.hoisted(() => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
  notFound: vi.fn(() => {
    throw new Error("NOT_FOUND");
  }),
}));
vi.mock("next/navigation", () => ({ redirect, notFound }));

const { default: ReviewDetailPage } = await import("./page");

describe("ReviewDetailPage", () => {
  beforeEach(() => {
    getReview.mockReset();
    redirect.mockClear();
    notFound.mockClear();
  });

  it("redirects to /login when the session is unauthorized", async () => {
    getReview.mockResolvedValue({
      data: null,
      error: { code: "UNAUTHORIZED", message: "Not authenticated." },
    });

    await expect(ReviewDetailPage({ params: Promise.resolve({ id: "1" }) })).rejects.toThrow(
      "REDIRECT:/login",
    );
  });

  it("calls notFound when the review does not exist", async () => {
    getReview.mockResolvedValue({
      data: null,
      error: { code: "RESOURCE_NOT_FOUND", message: "Review not found." },
    });

    await expect(ReviewDetailPage({ params: Promise.resolve({ id: "1" }) })).rejects.toThrow(
      "NOT_FOUND",
    );
  });

  it("renders a generic error message for any other failure", async () => {
    getReview.mockResolvedValue({
      data: null,
      error: { code: "INTERNAL_ERROR", message: "The API is unreachable." },
    });

    const element = await ReviewDetailPage({ params: Promise.resolve({ id: "1" }) });
    render(element);

    expect(
      screen.getByText("Could not load this review: The API is unreachable."),
    ).toBeInTheDocument();
  });

  it("renders review details on success", async () => {
    getReview.mockResolvedValue({
      data: {
        id: "1",
        source: "stub",
        rating: 4,
        review_text: "Great prints, fast turnaround.",
        reviewer_name: "Alex",
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
        owner_reply_text: null,
        owner_reply_at: null,
        analysis_status: "pending",
        analysis: null,
      },
      error: null,
    });

    const element = await ReviewDetailPage({ params: Promise.resolve({ id: "1" }) });
    render(element);

    expect(screen.getByText("Great prints, fast turnaround.")).toBeInTheDocument();
    expect(screen.getByText(/Alex/)).toBeInTheDocument();
    expect(screen.getByText(/Not analyzed yet/)).toBeInTheDocument();
  });
});
