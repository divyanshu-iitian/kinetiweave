import type {
  BackendChoice,
  CaptureProfile,
  AssetRecord,
  EnvironmentCreate,
  EnvironmentRecord,
  JobRecord,
  SystemCapabilities,
} from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function fetchSystem(): Promise<SystemCapabilities> {
  return readJson(await fetch("/api/system"));
}

export async function fetchJobs(): Promise<JobRecord[]> {
  return readJson(await fetch("/api/jobs?limit=20"));
}

export async function fetchJob(id: string): Promise<JobRecord> {
  return readJson(await fetch(`/api/jobs/${id}`));
}

export function uploadVideo(
  file: File,
  profile: CaptureProfile,
  backend: BackendChoice,
  onProgress: (progress: number) => void,
): Promise<JobRecord> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const form = new FormData();
    form.append("video", file);
    form.append("profile", profile);
    form.append("backend", backend);
    request.open("POST", "/api/jobs");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () => {
      let body: unknown;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        reject(new Error("The local API returned an unreadable response."));
        return;
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(body as JobRecord);
      } else {
        const detail = (body as { detail?: string }).detail;
        reject(
          new Error(detail || `Upload failed with status ${request.status}.`),
        );
      }
    });
    request.addEventListener("error", () =>
      reject(new Error("Could not reach the local API.")),
    );
    request.send(form);
  });
}

export function artifactUrl(job: JobRecord, relativePath: string): string {
  return `/api/jobs/${job.id}/artifacts/${relativePath}`;
}

export async function fetchAssets(): Promise<AssetRecord[]> {
  return readJson(await fetch("/api/assets?limit=200"));
}

export function assetGeometryUrl(asset: AssetRecord): string {
  return `/api/assets/${asset.id}/geometry`;
}

export function importGeometry(
  file: File,
  onProgress: (progress: number) => void,
): Promise<AssetRecord> {
  return uploadWithProgress<AssetRecord>(
    "/api/assets/import",
    "geometry",
    file,
    onProgress,
  );
}

export async function fetchEnvironments(): Promise<EnvironmentRecord[]> {
  return readJson(await fetch("/api/environments?limit=200"));
}

export async function createEnvironment(
  input: EnvironmentCreate,
): Promise<EnvironmentRecord> {
  return readJson(
    await fetch("/api/environments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export function environmentPackageUrl(environment: EnvironmentRecord): string {
  return `/api/environments/${environment.id}/package`;
}

function uploadWithProgress<T>(
  url: string,
  field: string,
  file: File,
  onProgress: (progress: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const form = new FormData();
    form.append(field, file);
    request.open("POST", url);
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () => {
      let body: unknown;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        reject(new Error("The local API returned an unreadable response."));
        return;
      }
      if (request.status >= 200 && request.status < 300) resolve(body as T);
      else reject(new Error((body as { detail?: string }).detail || "Upload failed."));
    });
    request.addEventListener("error", () =>
      reject(new Error("Could not reach the local API.")),
    );
    request.send(form);
  });
}
