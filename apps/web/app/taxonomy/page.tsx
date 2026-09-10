import { redirect } from "next/navigation";
import { getTaxonomy, type TaxonomyNode } from "@/lib/api";

function NodeList({ nodes, depth }: { nodes: TaxonomyNode[]; depth: number }) {
  if (nodes.length === 0) return null;
  return (
    <ul className={depth === 0 ? "tree" : undefined}>
      {nodes.map((node) => (
        <li key={node.id}>
          <span>{node.name}</span>
          {node.description && <span className="muted"> — {node.description}</span>}
          <NodeList nodes={node.children} depth={depth + 1} />
        </li>
      ))}
    </ul>
  );
}

export default async function TaxonomyPage() {
  const { data, error } = await getTaxonomy();

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Taxonomy</h1>
        <p>Could not load the taxonomy: {error.message}</p>
      </main>
    );
  }

  if (data === null) {
    return (
      <main>
        <h1>Taxonomy</h1>
        <p className="muted">
          No active taxonomy version yet. Categories are discovered from the review corpus rather
          than seeded, so this fills in once the classification pipeline runs.
        </p>
      </main>
    );
  }

  return (
    <main>
      <h1>Taxonomy</h1>
      <p>
        Version {data.version_number}
        {data.activated_at && (
          <span className="muted">
            {" "}
            — active since {new Date(data.activated_at).toLocaleDateString()}
          </span>
        )}
      </p>
      <NodeList nodes={data.nodes} depth={0} />
    </main>
  );
}
