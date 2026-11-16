import { useT } from "../../i18n";
import { useCallback, useEffect, useState } from "react";
import type { Checkpoint } from "../../api/types";
import { useDevice } from "../../device/DeviceContext";
import { CheckpointPicker } from "../checkpoint/CheckpointPicker";
import { useSelectedCheckpoint } from "../checkpoint/useCheckpoint";
import { ScanPage } from "./ScanPage";

/** Choose the post once, then scan. The choice is remembered on the phone. */
export function ScanFlow() {
  const { api, voiceEnabled } = useDevice();
  const { t } = useT();
  const { checkpointId, select, clear } = useSelectedCheckpoint();
  const [posts, setPosts] = useState<Checkpoint[] | null>(null);

  const load = useCallback(() => api.checkpoints().then(setPosts).catch(() => setPosts([])), [api]);

  // Resolve the remembered id back to a checkpoint (it may have been removed or deactivated).
  useEffect(() => {
    if (checkpointId !== null && posts === null) void load();
  }, [checkpointId, posts, load]);

  const checkpoint = posts?.find((c) => c.id === checkpointId) ?? null;
  useEffect(() => {
    if (posts !== null && checkpointId !== null && !checkpoint) clear();
  }, [posts, checkpointId, checkpoint, clear]);

  if (checkpointId !== null && posts === null) return <p className="center muted">{t("flow.loading")}</p>;
  if (!checkpoint) {
    return <CheckpointPicker onSelect={(c) => { setPosts(null); select(c.id); }} />;
  }
  // Same zone, other direction: one agent at a single door switches in one tap.
  const otherSide = posts?.find((c) => c.zone_id === checkpoint.zone_id && c.direction !== checkpoint.direction) ?? null;
  return (
    <ScanPage
      api={api}
      checkpoint={checkpoint}
      otherSide={otherSide}
      onSwitchSide={(c) => select(c.id)}
      onChangeCheckpoint={() => { setPosts(null); clear(); }}
      voice={voiceEnabled}
    />
  );
}
