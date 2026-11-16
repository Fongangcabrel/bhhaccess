import { useParams } from "react-router-dom";
import { ScanFlow } from "../features/scan/ScanFlow";
import { useDevice } from "./DeviceContext";
import { PairPage } from "./PairPage";

/** The agent's PWA: not paired -> pairing screen, paired -> pick the post and scan. */
export function DeviceApp() {
  const { paired } = useDevice();
  const { code } = useParams();
  return <div className="pwa">{paired ? <ScanFlow /> : <PairPage initialCode={code ?? ""} />}</div>;
}
