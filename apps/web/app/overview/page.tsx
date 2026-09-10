import { redirect } from "next/navigation";
import { getOverview } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default async function OverviewPage() {
  const { data, error } = await getOverview();

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Overview</h1>
        <p>Could not load overview: {error.message}</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Overview</h1>
      <p>
        {formatDate(data.start_date)} – {formatDate(data.end_date)}
      </p>
      <div className="stat-row">
        <div className="stat">
          <span className="stat-value">{data.review_count}</span>
          <span className="muted">Reviews</span>
        </div>
        <div className="stat">
          <span className="stat-value">{data.average_rating?.toFixed(1) ?? "—"}</span>
          <span className="muted">Average rating</span>
        </div>
        <div className="stat">
          <span className="stat-value">{data.active_insights.length}</span>
          <span className="muted">Active insights</span>
        </div>
      </div>

      <h2>Rating trend</h2>
      {data.rating_trend.length === 0 ? (
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
            {data.rating_trend.map((point) => (
              <tr key={point.date}>
                <td>{formatDate(point.date)}</td>
                <td>{point.review_count}</td>
                <td>{point.average_rating?.toFixed(1) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Active insights</h2>
      {data.active_insights.length === 0 ? (
        <p className="muted">
          None yet — insight generation runs downstream of the classification pipeline.
        </p>
      ) : (
        <ul>
          {data.active_insights.map((insight) => (
            <li key={insight.id}>
              {insight.title} — <span className="muted">{insight.severity}</span>
            </li>
          ))}
        </ul>
      )}

      <h2>Top themes</h2>
      <p className="muted">
        Positive/negative themes need a taxonomy version to group by; none exists yet.
      </p>
    </main>
  );
}
