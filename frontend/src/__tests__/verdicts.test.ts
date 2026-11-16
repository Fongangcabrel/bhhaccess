import type { Flag, Verdict } from "../api/types";
import { describeFlag, describeVerdict } from "../lib/verdicts";

const VERDICTS: Verdict[] = [
  "AUTORISE", "REFUSE_ZONE", "REFUSE_REVOQUE", "REFUSE_EXPIRE",
  "REFUSE_EMPLOYE_INACTIF", "REFUSE_INVALIDE", "REFUSE_ANTIPASSBACK", "SORTIE_ENREGISTREE",
];
const FLAGS: Flag[] = [
  "SORTIE_BADGE_REVOQUE", "SORTIE_BADGE_EXPIRE", "SORTIE_EMPLOYE_SUSPENDU",
  "DOUBLE_ENTREE", "SORTIE_SANS_ENTREE", "DEBLOQUE",
];

describe("verdict presentation", () => {
  it.each(VERDICTS)("has a title for %s", (verdict) => {
    expect(describeVerdict(verdict).title).not.toBe("");
  });

  it("colours entries green, exits blue and every refusal red", () => {
    expect(describeVerdict("AUTORISE").tone).toBe("ok");
    expect(describeVerdict("SORTIE_ENREGISTREE").tone).toBe("exit");
    VERDICTS.filter((v) => v.startsWith("REFUSE_")).forEach((v) => expect(describeVerdict(v).tone).toBe("deny"));
  });

  it.each(FLAGS)("has a label for flag %s", (flag) => {
    expect(describeFlag(flag)).not.toBe("");
  });
});
