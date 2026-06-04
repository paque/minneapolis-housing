const basePath = import.meta.env.BASE_URL ?? "/";

export function withBasePath(pathname: string): string {
  if (!pathname) {
    return basePath;
  }

  if (/^(https?:|mailto:|tel:|#)/.test(pathname)) {
    return pathname;
  }

  const normalizedBase = basePath.endsWith("/")
    ? basePath.slice(0, -1)
    : basePath;
  const normalizedPath = pathname.startsWith("/") ? pathname : `/${pathname}`;

  if (!normalizedBase || normalizedBase === "/") {
    return normalizedPath;
  }

  return `${normalizedBase}${normalizedPath}`;
}
