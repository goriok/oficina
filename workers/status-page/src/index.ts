interface Env {
  STATUS: KVNamespace;
}

interface ClusterStatus {
  healthy: boolean;
  ts: string;
  message?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/status" || url.pathname === "/") {
      if (!env.STATUS) {
        return Response.json({ healthy: false, message: "KV binding not configured" }, { status: 503 });
      }
      const raw = await env.STATUS.get("cluster-status");
      if (!raw) {
        return Response.json({ healthy: false, message: "No status reported yet" }, { status: 503 });
      }

      const status: ClusterStatus = JSON.parse(raw);
      const httpStatus = status.healthy ? 200 : 503;

      return Response.json(status, {
        status: httpStatus,
        headers: { "Cache-Control": "no-store" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
