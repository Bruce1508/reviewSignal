import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getReview } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { data, error } = await getReview(id);

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    if (error.code === "RESOURCE_NOT_FOUND") {
      notFound();
    }
    return (
      <main>
        <h1>Review</h1>
        <p>Could not load this review: {error.message}</p>
      </main>
    );
  }

  return (
    <main>
      <p>
        <Link href="/reviews">&larr; Back to reviews</Link>
      </p>
      <h1>{"★".repeat(data.rating)}</h1>
      <p>
        {data.reviewer_name ?? "Anonymous"} &middot; {formatDate(data.created_at)} &middot;{" "}
        {data.source} &middot; {data.analysis_status}
      </p>

      <h2>Review</h2>
      <p>{data.review_text ?? <span className="muted">No comment</span>}</p>

      {data.owner_reply_text && (
        <>
          <h2>Owner reply</h2>
          <p>
            {data.owner_reply_text}
            {data.owner_reply_at && (
              <>
                {" "}
                <span className="muted">({formatDate(data.owner_reply_at)})</span>
              </>
            )}
          </p>
        </>
      )}

      <h2>Analysis</h2>
      {data.analysis === null ? (
        <p className="muted">
          Not analyzed yet — classification runs downstream of the taxonomy pipeline.
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Sentiment</th>
              <th>Confidence</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {data.analysis.aspects.map((aspect) => (
              <tr key={aspect.category_id}>
                <td>{aspect.category_name}</td>
                <td>{aspect.sentiment}</td>
                <td>{aspect.confidence?.toFixed(2) ?? "—"}</td>
                <td>{aspect.evidence_span ?? <span className="muted">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
