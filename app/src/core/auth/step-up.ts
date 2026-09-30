import type { ApiProblem } from '../api/problem.js';

/**
 * Step-up coordination (05 §11.6, 08 §4.7). The API client calls requestStepUp() on 403
 * STEP_UP_REQUIRED; the shell's <vs-step-up-dialog> registers the presenter that shows "Confirm it's
 * you" and resolves true after POST /auth/mfa/step-up or /auth/reauth succeeded.
 */
export type StepUpPresenter = (problem: ApiProblem) => Promise<boolean>;

let presenter: StepUpPresenter | null = null;
let inFlight: Promise<boolean> | null = null;

export function registerStepUpPresenter(fn: StepUpPresenter | null): void {
  presenter = fn;
}

export function requestStepUp(problem: ApiProblem): Promise<boolean> {
  if (!presenter) return Promise.resolve(false);
  if (!inFlight) inFlight = presenter(problem).finally(() => (inFlight = null));
  return inFlight;
}
