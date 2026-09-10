import { redirect } from "next/navigation";
import { getSettings } from "@/lib/api";

export default async function SettingsPage() {
  const { data, error } = await getSettings();

  if (error) {
    if (error.code === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main>
        <h1>Settings</h1>
        <p>Could not load settings: {error.message}</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Settings</h1>
      <p className="muted">
        Google Business Profile connection and mutation controls (rebuild, editing) are not built
        yet — this shows the current read-only config.
      </p>
      <table className="table">
        <tbody>
          <tr>
            <td>Default date range</td>
            <td>
              {data.default_date_range_days !== null ? (
                `${data.default_date_range_days} days`
              ) : (
                <span className="muted">Not configured</span>
              )}
            </td>
          </tr>
          <tr>
            <td>Daily sync time</td>
            <td>{data.daily_sync_time ?? <span className="muted">Not configured</span>}</td>
          </tr>
          <tr>
            <td>Classification threshold</td>
            <td>
              {data.classification_threshold ?? <span className="muted">Not configured</span>}
            </td>
          </tr>
          <tr>
            <td>Active model</td>
            <td>{data.active_model}</td>
          </tr>
          <tr>
            <td>Embedding model</td>
            <td>{data.embedding_model}</td>
          </tr>
        </tbody>
      </table>
    </main>
  );
}
