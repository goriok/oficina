interface Env {
  DISCORD_WEBHOOK_URL: string;
  RELAY_TOKEN: string;
}

interface RelayPayload {
  source: string;
  title?: string;
  body: string;
  url?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const authHeader = request.headers.get("Authorization");
    if (!authHeader || authHeader !== `Bearer ${env.RELAY_TOKEN}`) {
      return new Response("Unauthorized", { status: 401 });
    }

    let payload: RelayPayload;
    try {
      payload = await request.json();
    } catch {
      return new Response("Bad Request: invalid JSON", { status: 400 });
    }

    const discordBody = {
      username: "oficina-cluster",
      embeds: [
        {
          title: payload.title ?? payload.source,
          description: payload.body,
          url: payload.url,
          footer: { text: `Source: ${payload.source}` },
        },
      ],
    };

    const res = await fetch(env.DISCORD_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(discordBody),
    });

    if (!res.ok) {
      return new Response("Discord delivery failed", { status: 502 });
    }

    return new Response("OK", { status: 200 });
  },
};
