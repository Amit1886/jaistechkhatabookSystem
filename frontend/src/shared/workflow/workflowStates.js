export const WORKFLOW_STATES = [
  { key: "draft", label: "Draft", tone: "muted", order: 10 },
  { key: "review", label: "Review", tone: "blue", order: 20 },
  { key: "approval", label: "Approval", tone: "amber", order: 30 },
  { key: "completed", label: "Completed", tone: "green", order: 40 },
  { key: "cancelled", label: "Cancelled", tone: "red", order: 50 },
];

export const WORKFLOW_TRANSITIONS = {
  draft: ["review", "cancelled"],
  review: ["approval", "draft", "cancelled"],
  approval: ["completed", "review", "cancelled"],
  completed: [],
  cancelled: [],
};

export function getWorkflowState(key) {
  return WORKFLOW_STATES.find((state) => state.key === key) || WORKFLOW_STATES[0];
}

export function canTransition(from, to) {
  return Boolean(WORKFLOW_TRANSITIONS[from]?.includes(to));
}

