/** Temporal sandbox workflow for the bounded infrastructure smoke check. */
import { proxyActivities } from "@temporalio/workflow";
import type { TemporalSmokeResult } from "./native-infrastructure-smoke-domain.js";
const activities = proxyActivities<{
    readonly hswm_research_fabric_smoke_activity: (value: {
        readonly run_id: string;
    }) => Promise<TemporalSmokeResult["result"]>;
}>({ startToCloseTimeout: "15 seconds" });
export const hswm_research_fabric_smoke_workflow = (value: {
    readonly run_id: string;
}): Promise<TemporalSmokeResult["result"]> => activities.hswm_research_fabric_smoke_activity(value);
