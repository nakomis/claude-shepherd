// TODO (SHEP-34): invoke normalisation layer → reviewer model
export const handler = async (event: Record<string, unknown>): Promise<Record<string, unknown>> => {
  console.log('review invoked:', JSON.stringify(event));
  return { ...event, approved: true, review_notes: 'stub — always approves' };
};
