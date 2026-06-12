export const dynamic = 'force-dynamic';
export const maxDuration = 60;

export async function GET(request, { params }) {
  const workerUrl = process.env.WORKER_URL;
  if (!workerUrl) {
    return Response.json({ error: 'WORKER_URL not set' }, { status: 500 });
  }

  try {
    const upstream = await fetch(`${workerUrl}/report/${params.name}`, {
      headers: { 'ngrok-skip-browser-warning': 'true' },
      cache: 'no-store',
    });
    return Response.json(await upstream.json(), { status: upstream.status });
  } catch {
    return Response.json({ error: 'worker unreachable' }, { status: 502 });
  }
}
