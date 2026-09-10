"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function handleClick() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
  }

  return (
    <button type="button" className="logout" onClick={handleClick}>
      Log out
    </button>
  );
}
