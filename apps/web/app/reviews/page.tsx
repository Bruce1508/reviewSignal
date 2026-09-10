import Link from "next/link";
import { redirect } from "next/navigation";
import { getReviews } from "@/lib/api";

const PAGE_SIZE = 20;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

interface Filters {
  page?: string;
  q?: string;
  rating?: string;
  start_date?: string;
  end_date?: string;
}

function pageHref(filters: Filters, page: number) {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.rating) params.set("rating", filters.rating);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  params.set("page", String(page));
  return `/reviews?${params.toString()}`;
}

export default async function ReviewsPage({ searchParams }: { searchParams: Promise<Filters> }) {
  const filters = await searchParams;
  const page = Math.max(1, Number(filters.page) || 1);
  const rating = filters.rating ? Number(filters.rating) : undefined;
  const hasActiveFilters = Boolean(
    filters.q || filters.rating || filters.start_date || filters.end_date,
  );

  const { data, error } = await getReviews(page, PAGE_SIZE, {
    q: filters.q,
    rating,
    startDate: filters.start_date,
    endDate: filters.end_date,
  });

  if (error) {
    // The cookie's presence is enough for `middleware.ts` to let the request through,
    // but not enough to prove it hasn't expired: that only the API can tell.
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Reviews</h1>
        <p>Could not load reviews: {error.message}</p>
      </main>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <main>
      <h1>Reviews</h1>
      <form method="get" className="filter-form">
        <input type="text" name="q" placeholder="Search text" defaultValue={filters.q ?? ""} />
        <select name="rating" defaultValue={filters.rating ?? ""}>
          <option value="">Any rating</option>
          {[5, 4, 3, 2, 1].map((value) => (
            <option key={value} value={value}>
              {value} star{value === 1 ? "" : "s"}
            </option>
          ))}
        </select>
        <input type="date" name="start_date" defaultValue={filters.start_date ?? ""} />
        <input type="date" name="end_date" defaultValue={filters.end_date ?? ""} />
        <button type="submit">Filter</button>
        {hasActiveFilters && <Link href="/reviews">Clear</Link>}
      </form>

      <p>
        {data.total} review{data.total === 1 ? "" : "s"}
        {hasActiveFilters ? " matching these filters." : "."}
      </p>
      {data.items.length === 0 ? (
        <p className="muted">No reviews match these filters.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Rating</th>
              <th>Review</th>
              <th>Reviewer</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((review) => (
              <tr key={review.id}>
                <td>{formatDate(review.created_at)}</td>
                <td>{"★".repeat(review.rating)}</td>
                <td>
                  <Link href={`/reviews/${review.id}`}>
                    {review.review_text ?? <span className="muted">No comment</span>}
                  </Link>
                </td>
                <td>{review.reviewer_name ?? "Anonymous"}</td>
                <td>{review.analysis_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pager">
        {page > 1 && <Link href={pageHref(filters, page - 1)}>&larr; Previous</Link>}
        <span className="muted">
          Page {page} of {totalPages}
        </span>
        {page < totalPages && <Link href={pageHref(filters, page + 1)}>Next &rarr;</Link>}
      </div>
    </main>
  );
}
