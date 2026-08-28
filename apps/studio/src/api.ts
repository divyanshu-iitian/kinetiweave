import type {
  BackendChoice,
  CaptureProfile,
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
