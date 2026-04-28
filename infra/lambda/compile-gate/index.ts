// TODO: push branch to GitHub, trigger compile-check.yml via workflow_dispatch, poll for result
export const handler = async (event: Record<string, unknown>): Promise<Record<string, unknown>> => {
  console.log('compile-gate invoked:', JSON.stringify(event));
  return { ...event, compile_passed: true };
};
