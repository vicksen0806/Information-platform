const KNOWN_SOURCE_NAMES: Record<string, string> = {
  "news.google.com": "Google新闻",
  "google.com": "Google",
  "ltn.com.tw": "自由时报",
  "ettoday.net": "ETtoday新闻云",
  "udn.com": "联合新闻网",
  "storm.mg": "风传媒",
  "newtalk.tw": "Newtalk新闻",
  "thenewslens.com": "The News Lens",
  "cna.com.tw": "中央社",
  "setn.com": "三立新闻网",
  "reuters.com": "Reuters",
  "bbc.com": "BBC",
  "yahoo.com": "Yahoo",
  "yahoo.co.jp": "Yahoo Japan",
};

function sourceNameFromUrl(url: string): string {
  try {
    let host = new URL(url).hostname.toLowerCase();
    if (host.startsWith("www.")) {
      host = host.slice(4);
    }

    if (KNOWN_SOURCE_NAMES[host]) {
      return KNOWN_SOURCE_NAMES[host];
    }

    for (const [domain, name] of Object.entries(KNOWN_SOURCE_NAMES)) {
      if (host.endsWith(`.${domain}`)) {
        return name;
      }
    }

    const [root] = host.split(".");
    return root ? root.charAt(0).toUpperCase() + root.slice(1) : "来源";
  } catch {
    return "来源";
  }
}

function cleanSourceLabel(label: string | undefined, url: string): string {
  const normalized = (label || "").trim().replace(/^[\[\(（]+|[\]\)）]+$/g, "").replace(/\s+/g, " ");
  if (!normalized) {
    return sourceNameFromUrl(url);
  }
  if (/^https?:\/\//i.test(normalized)) {
    return sourceNameFromUrl(url);
  }
  if (normalized.length > 32 || /[/?&=]/.test(normalized)) {
    return sourceNameFromUrl(url);
  }
  return normalized;
}

export function normalizeMarkdownLinks(markdown: string): string {
  return markdown
    .replace(/([（(])\[([^\]\n]{1,120})\]\((https?:\/\/[^\s)]+)(?=$|\n)/g, (_, open: string, label: string, url: string) => {
      return `${open}[${cleanSourceLabel(label, url)}](${url})${open === "（" ? "）" : ")"}`;
    })
    .replace(/\[([^\]\n]{1,120})\]\((https?:\/\/[^\s)]+)(?=$|\n)/g, (_, label: string, url: string) => {
      return `[${cleanSourceLabel(label, url)}](${url})`;
    })
    .replace(/\[([^\]\n]{1,120})\]\((https?:\/\/[^\s)]+)\)/g, (_, label: string, url: string) => {
      return `[${cleanSourceLabel(label, url)}](${url})`;
    })
    .replace(/(?<!\]\()(https?:\/\/[^\s)]+)/g, (_, url: string) => {
      return `[${sourceNameFromUrl(url)}](${url})`;
    });
}
