export const dynamic = 'force-dynamic';

export async function GET() {
  const workerUrl = process.env.WORKER_URL;
  if (!workerUrl) {
    return Response.json({ error: 'WORKER_URL not set' }, { status: 500 });
  }

  try {
    const res = await fetch(`${workerUrl}/status`, {
      headers: { 'ngrok-skip-browser-warning': 'true' },
      cache: 'no-store',
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json({ error: 'worker unreachable' }, { status: 502 });
  }
}
