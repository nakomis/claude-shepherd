// TODO: call GitHub API to merge the generated branch
export const handler = async (event: Record<string, unknown>): Promise<Record<string, unknown>> => {
  console.log('merge invoked:', JSON.stringify(event));
  return { success: true, message: 'stub — merge not yet implemented' };
};
