import { redirect } from "next/navigation";
import { getInsights } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default async function InsightsPage() {
  const { data, error } = await getInsights();

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Insights</h1>
        <p>Could not load insights: {error.message}</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Insights</h1>
      <p>
        {data.length} insight{data.length === 1 ? "" : "s"}. Generation runs downstream of the
        classification pipeline, so this fills in once that pipeline exists.
      </p>
      {data.length === 0 ? (
        <p className="muted">None yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {data.map((insight) => (
              <tr key={insight.id}>
                <td>{insight.title}</td>
                <td>{insight.severity}</td>
                <td>{insight.status}</td>
                <td>{formatDate(insight.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
