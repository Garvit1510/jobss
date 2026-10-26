import { useEffect, useRef } from "react";
import { toast } from "sonner";
import api, { errMsg } from "../../lib/api";
import ProctorMonitor from "../oa/ProctorMonitor";
import { MAX_TAB_SWITCHES, useIdentityLockout } from "../../lib/useProctor";

// Live cam + fullscreen gate + identity lockout for a proctored interview; auto-finishes on breach timeout or too many tab switches.
export default function InterviewProctor({ proctor, sessionId, onDone, beforeFinish }) {
  const sent = useRef(false);
  const finish = async (reason) => {
    if (sent.current) return;
    sent.current = true;
    beforeFinish && beforeFinish();
    toast.error(reason, { id: "iv-auto-finish" });
    try {
      const { data } = await api.post("/interview/finish", { session_id: sessionId });
      onDone(data.report || null);
    } catch (e) {
      toast.error(errMsg(e));
      sent.current = false;
    }
  };
  const finishRef = useRef(finish);
  finishRef.current = finish;
  const idLeft = useIdentityLockout(!!proctor.identityBreach, () => finishRef.current("Interview ended: registered candidate not present"));
  const tabs = proctor.flags.filter((f) => f.type === "tab_switch").length;
  useEffect(() => {
    if (tabs >= MAX_TAB_SWITCHES) finishRef.current(`Interview ended after ${tabs} tab switches`);
  }, [tabs]);
  return <ProctorMonitor proctor={proctor} identityCountdown={idLeft} />;
}
