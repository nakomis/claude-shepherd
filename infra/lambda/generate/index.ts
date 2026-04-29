// TODO (SHEP-34): invoke normalisation layer → model provider
export const handler = async (event: Record<string, unknown>): Promise<Record<string, unknown>> => {
  console.log('generate invoked:', JSON.stringify(event));
  return { ...event, generated_files: {} };
};
