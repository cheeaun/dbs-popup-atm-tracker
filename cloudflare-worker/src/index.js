const GITHUB_API_BASE = "https://api.github.com";
const WINDOW_TIME_ZONE = "Asia/Singapore";

function getSgtDateParts(date) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: WINDOW_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const parts = formatter.formatToParts(date);
  const map = {};
  for (const part of parts) {
    if (part.type !== "literal") {
      map[part.type] = part.value;
    }
  }
  return {
    year: Number.parseInt(map.year, 10),
    month: Number.parseInt(map.month, 10),
    day: Number.parseInt(map.day, 10),
    hour: Number.parseInt(map.hour, 10),
    minute: Number.parseInt(map.minute, 10),
  };
}

function isWithinCollectionWindow(now = new Date()) {
  const { year, month, day, hour } = getSgtDateParts(now);
  if (year !== 2026 || month !== 2) {
    return false;
  }

  if (day >= 3 && day <= 15) {
    return hour >= 10 && hour <= 21;
  }

  if (day === 16) {
    return hour >= 10 && hour <= 12;
  }

  return false;
}

function requiredEnv(name, env) {
  const value = env[name];
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

async function dispatchWorkflow(env, source) {
  const owner = requiredEnv("GITHUB_OWNER", env);
  const repo = requiredEnv("GITHUB_REPO", env);
  const workflow = requiredEnv("GITHUB_WORKFLOW", env);
  const ref = env.GITHUB_REF || "main";
  const token = requiredEnv("GITHUB_TOKEN", env);
  const retryCount = Math.max(
    0,
    Number.parseInt(env.GITHUB_DISPATCH_MAX_RETRIES || "2", 10),
  );

  const url =
    `${GITHUB_API_BASE}/repos/${owner}/${repo}/actions/workflows/` +
    `${encodeURIComponent(workflow)}/dispatches`;
  const payload = JSON.stringify({ ref });

  for (let attempt = 0; attempt <= retryCount; attempt += 1) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "cf-worker-github-dispatch",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: payload,
    });

    if (response.status === 204) {
      console.log(
        `[${source}] Dispatched ${workflow} on ${owner}/${repo}@${ref} (attempt ${attempt + 1})`,
      );
      return;
    }

    const responseText = await response.text();
    const retryable = response.status === 429 || response.status >= 500;
    if (retryable && attempt < retryCount) {
      const backoffMs = 750 * (attempt + 1);
      console.warn(
        `[${source}] Dispatch failed with ${response.status}. Retrying in ${backoffMs}ms...`,
      );
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
      continue;
    }

    throw new Error(
      `[${source}] Dispatch failed (${response.status}): ${responseText || "no response body"}`,
    );
  }
}

export default {
  async scheduled(event, env, ctx) {
    if (!isWithinCollectionWindow(new Date(event.scheduledTime))) {
      console.log("[scheduled] Outside collection window, skipping dispatch.");
      return;
    }
    ctx.waitUntil(dispatchWorkflow(env, "scheduled"));
  },
};
