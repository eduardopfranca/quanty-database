export const dynamic = 'force-dynamic';
export const maxDuration = 60;

export async function POST(request, { params }) {
  const workerUrl = process.env.WORKER_URL;
  const secret = process.env.WORKER_SECRET;
  if (!workerUrl || !secret) {
    return Response.json({ error: 'WORKER_URL or WORKER_SECRET not set' }, { status: 500 });
  }

  const name = params.name;
  const force = new URL(request.url).searchParams.get('force') === 'true';
  const target = `${workerUrl}/run-update/${name}${force ? '?force=true' : ''}`;

  try {
    const res = await fetch(target, {
      method: 'POST',
      headers: {
        'X-Worker-Secret': secret,
        'ngrok-skip-browser-warning': 'true',
      },
      cache: 'no-store',
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json({ error: 'worker unreachable' }, { status: 502 });
  }
}
