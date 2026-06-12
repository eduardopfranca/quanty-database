export const dynamic = 'force-dynamic';
export const maxDuration = 60;

export async function GET(request, { params }) {
  const workerUrl = process.env.WORKER_URL;
  const secret = process.env.WORKER_SECRET;
  if (!workerUrl || !secret) {
    return Response.json({ error: 'WORKER_URL or WORKER_SECRET not set' }, { status: 500 });
  }

  const name = params.name;

  try {
    const upstream = await fetch(`${workerUrl}/download/${name}`, {
      headers: {
        'X-Worker-Secret': secret,
        'ngrok-skip-browser-warning': 'true',
      },
      cache: 'no-store',
    });

    if (!upstream.ok) {
      return new Response(await upstream.text(), { status: upstream.status });
    }

    const headers = new Headers();
    for (const key of ['content-type', 'content-disposition', 'content-length']) {
      const value = upstream.headers.get(key);
      if (value) headers.set(key, value);
    }
    return new Response(upstream.body, { status: 200, headers });
  } catch {
    return Response.json({ error: 'worker unreachable' }, { status: 502 });
  }
}
