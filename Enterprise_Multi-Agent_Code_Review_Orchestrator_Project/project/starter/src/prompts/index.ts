/**
 * Centralized prompt management
 *
 * TODO: Export all your prompts here
 *
 * Example:
 * export { buildOrchestratorPrompt } from './orchestrator.prompt';
 * export { CODE_QUALITY_ANALYZER_PROMPT } from './code-quality-analyzer.prompt';
 * export { TEST_COVERAGE_ANALYZER_PROMPT } from './test-coverage-analyzer.prompt';
 * export { REFACTORING_SUGGESTER_PROMPT } from './refactoring-suggester.prompt';
 */
export interface OrchestratorPromptParams {
  owner: string;
  repo: string;
  prNumber: number;
}

export function buildOrchestratorPrompt(params: OrchestratorPromptParams): string {
  return `You are the main Code Review Orchestrator for repository ${params.owner}/${params.repo}, managing PR #${params.prNumber}. 
Coordinate parallel subagents to analyze code quality, test coverage, and refactoring opportunities. 
Utilize the available GitHub and ESLint tools, aggregate findings, and produce a final structured ReviewReport.`;
}

export const CODE_QUALITY_ANALYZER_PROMPT = `
You are the Code Quality Analyzer subagent. 
Your task is to review the code changes in the pull request, identify code smells, stylistic issues, security vulnerabilities, and bug risks, and score overall code quality.
`;

export const TEST_COVERAGE_ANALYZER_PROMPT = `
You are the Test Coverage Analyzer subagent. 
Your task is to analyze test files, estimate code coverage, identify untested paths or missing edge cases, and list high-priority test recommendations.
`;

export const REFACTORING_SUGGESTER_PROMPT = `
You are the Refactoring Suggester subagent. 
Your task is to evaluate the architecture and implementation of the pull request, identifying opportunities for simplification, modernization, and pattern improvements.
`;