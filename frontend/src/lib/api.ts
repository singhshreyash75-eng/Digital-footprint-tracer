const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function createInvestigation(payload: {
  name: string;
  target: string;
}) {
  const response = await fetch(
    `${API_BASE_URL}/investigations`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Investigation request failed: ${response.status}`,
    );
  }

  return response.json();
}