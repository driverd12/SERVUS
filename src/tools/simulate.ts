import { z } from "zod";

export const simulateWorkflowSchema = z.object({
  workflow: z.enum(["onboard_us", "offboard_us"]),
  employment_type: z.enum(["FTE", "CON", "INT", "SUP"]),
  offboarding_mode: z.enum(["log-only", "staged", "execute"]).optional(),
  manager_dn_resolved: z.boolean().optional(),
  scim_ready: z.boolean().optional(),
  actual_outcomes: z.record(z.boolean()).optional(),
});

export function simulateWorkflow(input: z.infer<typeof simulateWorkflowSchema>) {
  const scimReady = input.scim_ready ?? true;
  const managerResolved = input.manager_dn_resolved ?? true;
  const actual = input.actual_outcomes ?? {};

  const expected = buildExpectedOutcomes(input.workflow, input.employment_type, {
    scimReady,
    managerResolved,
    offboardingMode: input.offboarding_mode ?? "log-only",
  });

  const steps = Object.entries(expected).map(([name, expectedValue]) => {
    const actualValue = actual[name];
    const status =
      actualValue === undefined ? "expected" : actualValue === expectedValue ? "match" : "mismatch";
    return {
      step: name,
      expected: expectedValue,
      actual: actualValue ?? null,
      status,
    };
  });

  const mismatches = steps.filter((step) => step.status === "mismatch");

  return {
    deterministic: true,
    workflow: input.workflow,
    employment_type: input.employment_type,
    summary: {
      steps: steps.length,
      mismatches: mismatches.length,
      pass: mismatches.length === 0,
    },
    steps,
  };
}

function buildExpectedOutcomes(
  workflow: "onboard_us" | "offboard_us",
  employmentType: "FTE" | "CON" | "INT" | "SUP",
  options: {
    scimReady: boolean;
    managerResolved: boolean;
    offboardingMode: "log-only" | "staged" | "execute";
  }
): Record<string, boolean> {
  if (workflow === "offboard_us") {
    return {
      require_two_source_confirmation: true,
      execute_destructive_actions: options.offboardingMode === "execute",
      preserve_protected_targets: true,
      notify_incident_channel: true,
    };
  }

  return {
    wait_for_scim: options.scimReady,
    manager_dn_available: options.managerResolved,
    apply_google_customization: options.scimReady,
    apply_slack_customization: employmentType !== "SUP" && options.scimReady,
    apply_badge_queue: employmentType !== "SUP" && options.scimReady,
  };
}
