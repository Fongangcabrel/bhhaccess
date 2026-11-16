import type { ApiClient } from "./client";
import type { Checkpoint, ScanResult } from "./types";

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

  scanQr(checkpointId: number, token: string) {
    return this.client.post<ScanResult>("/device/scan", { checkpoint_id: checkpointId, token });
  }

  scanManual(checkpointId: number, matricule: string) {
    return this.client.post<ScanResult>("/device/scan/manual", { checkpoint_id: checkpointId, matricule });
  }
}

/** The two calls the scanner hook needs (lets tests pass a tiny fake). */
export type Scanner = Pick<DeviceApi, "scanQr" | "scanManual">;
