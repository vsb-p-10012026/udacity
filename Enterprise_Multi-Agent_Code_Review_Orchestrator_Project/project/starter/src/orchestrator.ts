import path from 'path';
import { fileURLToPath } from 'url';
import { query } from '@anthropic-ai/claude-agent-sdk';
import { ReviewReport } from './types/report-types.js';
import { mcpServersConfig } from './config/mcp.config.js';
import { buildOrchestratorPrompt } from './prompts/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "../..");
/**
 * Orchestrator configuration options
 */
export interface OrchestratorOptions {
  model?: string;
  maxTurns?: number;
}

/**
 * Main Code Review Orchestrator
 * Coordinates subagents to analyze pull requests and generate comprehensive reports
 */
export class CodeReviewOrchestrator {
  private model: string;
  private maxTurns: number;

  constructor(options: OrchestratorOptions = {}) {
    this.model = options.model || process.env.ANTHROPIC_MODEL || "claude-sonnet-4-5-20250929";
    this.maxTurns = options.maxTurns || 15;
  }

  /**
   * Review a pull request using parallel subagent analysis
   * @param owner - Repository owner
   * @param repo - Repository name
   * @param prNumber - Pull request number
   * @returns Complete review report
   */
  async reviewPullRequest(
    owner: string,
    repo: string,
    prNumber: number
  ): Promise<ReviewReport> {
    console.log(`\nStarting Code Review Orchestrator for ${owner}/${repo} PR #${prNumber}...`);
    
    const systemPrompt = buildOrchestratorPrompt({ owner, repo, prNumber });

    const messages: Array<{ role: "user" | "assistant"; content: string }> = [
      {
        role: "user",
        content: `Please review pull request #${prNumber} for repository ${owner}/${repo}. Utilize the available GitHub and ESLint tools to gather PR details, analyze code quality, test coverage, and provide suggestions.`,
      },
    ];

    let finalReport: ReviewReport | null = null;

    // Run orchestrator agent loop
    for (let turn = 0; turn < this.maxTurns; turn++) {
      console.log(`\n--- Orchestrator Turn ${turn + 1} ---`);

      // Using the Claude Agent SDK query pattern or client messages create depending on architecture setup
      // Here we integrate with standard mcpServers configuration and subprocess management
      for await (const message of query({
        prompt: (async function* () {
          for (const m of messages) {
            yield {
              type: "user" as const,
              message: { role: m.role as any, content: m.content },
              parent_tool_use_id: null,
              session_id: "orchestrator-session",
            };
          }
        })(),
        options: {
          model: this.model as any,
          cwd: PROJECT_ROOT,
          settingSources: ["project"],
          mcpServers: mcpServersConfig as any,
        },
      })){
        if (message.type === "assistant") {
          const content = message.message?.content;
          if (Array.isArray(content)) {
            messages.push({
              role: "assistant",
              content: content.map(c => (c.type === "text" ? c.text : JSON.stringify(c))).join("\n"),
            });
          }
        }

        // Capture structured or text review report output
        if (
          message.type === "result" &&
          message.subtype === "success" &&
          message.structured_output
        ) {
          finalReport = message.structured_output as ReviewReport;
        }
      }

      if (finalReport) {
        break;
      }
    }

    if (!finalReport) {
      throw new Error(`Failed to generate comprehensive review report for PR #${prNumber}`);
    }

    return finalReport;
  }
}
