import Link from "next/link";
import { redirect } from "next/navigation";
import { getInsight } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function InsightDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { data, error } = await getInsight(id);

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Insight</h1>
        <p>Could not load this insight: {error.message}</p>
      </main>
    );
  }

  return (
    <main>
      <p>
        <Link href="/insights">&larr; Back to insights</Link>
      </p>
      <h1>{data.title}</h1>
      <p>
        {data.severity} &middot; {data.status} &middot; opened {formatDate(data.created_at)}
        {data.resolved_at && <> &middot; resolved {formatDate(data.resolved_at)}</>}
      </p>

      <h2>Summary</h2>
      <p>{data.summary}</p>

      <h2>Evidence</h2>
      <p>{data.evidence_summary}</p>

      <h2>Impact</h2>
      {data.impact === null ? (
        <p className="muted">
          Not computed yet — impact runs as a follow-up job that doesn&rsquo;t exist yet.
        </p>
      ) : (
        <pre>{JSON.stringify(data.impact, null, 2)}</pre>
      )}

      <h2>Actions</h2>
      {data.actions.length === 0 ? (
        <p className="muted">No actions logged yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Status</th>
              <th>Date</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {data.actions.map((action) => (
              <tr key={action.id}>
                <td>{action.action_text}</td>
                <td>{action.status}</td>
                <td>{action.action_date ? formatDate(action.action_date) : "—"}</td>
                <td>{action.note_text ?? <span className="muted">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
