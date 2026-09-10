import { redirect } from "next/navigation";
import Link from "next/link";
import {
  getCategoryTrends,
  getRatingTrend,
  getTrendsSummary,
  type CategoryMovement,
} from "@/lib/api";

const SENTIMENTS = ["positive", "neutral", "negative"] as const;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function MovementRow({ movement }: { movement: CategoryMovement }) {
  return (
    <tr>
      <td>{movement.category_name}</td>
      <td>{movement.sentiment}</td>
      <td>{movement.previous_count}</td>
      <td>{movement.current_count}</td>
      <td>{movement.delta > 0 ? `+${movement.delta}` : movement.delta}</td>
    </tr>
  );
}

export default async function TrendsPage({
  searchParams,
}: {
  searchParams: Promise<{ sentiment?: string }>;
}) {
  const { sentiment } = await searchParams;
  const [ratings, summary, categories] = await Promise.all([
    getRatingTrend(),
    getTrendsSummary(),
    getCategoryTrends(sentiment),
  ]);

  if (
    ratings.error?.code === "UNAUTHORIZED" ||
    summary.error?.code === "UNAUTHORIZED" ||
    categories.error?.code === "UNAUTHORIZED"
  ) {
    redirect("/login");
  }
  // Checked as direct property accesses, not through a derived variable, so
  // TypeScript can narrow each of `ratings`/`summary`/`categories` to its `data` arm
  // below.
  if (ratings.error || summary.error || categories.error) {
    const message = (ratings.error ?? summary.error ?? categories.error)?.message;
    return (
      <main>
        <h1>Trends</h1>
        <p>Could not load trends: {message}</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Trends</h1>
      <p>
        Rating history over {formatDate(ratings.data.start_date)} –{" "}
        {formatDate(ratings.data.end_date)}. Category and sentiment trends fill in once the
        classification pipeline runs.
      </p>

      <h2>Rating history</h2>
      {ratings.data.points.length === 0 ? (
        <p className="muted">No reviews in this period.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Day</th>
              <th>Reviews</th>
              <th>Average rating</th>
            </tr>
          </thead>
          <tbody>
            {ratings.data.points.map((point) => (
              <tr key={point.date}>
                <td>{formatDate(point.date)}</td>
                <td>{point.review_count}</td>
                <td>{point.average_rating?.toFixed(1) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Biggest movements this week</h2>
      {summary.data.biggest_increases.length === 0 &&
      summary.data.biggest_decreases.length === 0 ? (
        <p className="muted">No category movements yet — needs the classification pipeline.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Sentiment</th>
              <th>Previous week</th>
              <th>This week</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {summary.data.biggest_increases.map((movement) => (
              <MovementRow
                key={`${movement.category_id}-${movement.sentiment}`}
                movement={movement}
              />
            ))}
            {summary.data.biggest_decreases.map((movement) => (
              <MovementRow
                key={`${movement.category_id}-${movement.sentiment}`}
                movement={movement}
              />
            ))}
          </tbody>
        </table>
      )}

      <h2>
        Categories ({formatDate(categories.data.start_date)} –{" "}
        {formatDate(categories.data.end_date)})
      </h2>
      <form method="get" className="filter-form">
        <select name="sentiment" defaultValue={sentiment ?? ""}>
          <option value="">Any sentiment</option>
          {SENTIMENTS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <button type="submit">Filter</button>
        {sentiment && <Link href="/trends">Clear</Link>}
      </form>
      {categories.data.categories.length === 0 ? (
        <p className="muted">No category mentions yet — needs the classification pipeline.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Sentiment</th>
              <th>Mentions</th>
            </tr>
          </thead>
          <tbody>
            {categories.data.categories.map((point) => (
              <tr key={`${point.category_id}-${point.sentiment}`}>
                <td>{point.category_name}</td>
                <td>{point.sentiment}</td>
                <td>{point.mention_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
