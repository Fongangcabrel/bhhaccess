import type { ApiClient } from "./client";
import type { Checkpoint, RecentScan, ScanResult } from "./types";

/** What a paired phone may do: pair, list posts, scan. No login, no back-office. */
export class DeviceApi {
  constructor(private readonly client: ApiClient) {}

  pair(code: string) {
    return this.client.post<{ device_token: string; device_name: string }>("/device/pair", { code });
  }

  checkpoints() {
    return this.client.get<Checkpoint[]>("/device/checkpoints");
  }

  settings() {
    return this.client.get<{ name: string; voice_enabled: boolean }>("/device/settings");
  }

  /** The agent holds this post now: the server records a change of post (audit). */
  takePost(checkpointId: number) {
    return this.client.post<{ checkpoint_id: number; current_post: string; since: string }>(
      "/device/post", { checkpoint_id: checkpointId });
  }

  /** This phone's last scans (current shift), newest first. */
  recentScans(limit = 30) {
    return this.client.get<RecentScan[]>(`/device/scans?limit=${limit}`);
  }

  scanQr(checkpointId: number, token: string) {
    return this.client.post<ScanResult>("/device/scan", { checkpoint_id: checkpointId, token });
  }

  scanManual(checkpointId: number, matricule: string) {
    return this.client.post<ScanResult>("/device/scan/manual", { checkpoint_id: checkpointId, matricule });
  }
}

/** The two calls the scanner hook needs (lets tests pass a tiny fake). */
export type Scanner = Pick<DeviceApi, "scanQr" | "scanManual">;
