import * as dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { CodeReviewOrchestrator } from './orchestrator.js';
import { ReportGenerator } from './utils/report-generator.js';

// Load environment variables
dotenv.config();

/**
 * Main entry point for the Claude Multi-Agent Code Review System
 * Usage: npm run dev <owner> <repo> <pr-number>
 */
async function main() {
  const [owner, repo, prStr] = process.argv.slice(2);

  // TODO: Validate command line arguments
  // - Check if owner, repo, and prStr are provided
  // - Convert prStr to number and validate it's a valid integer
  // - Exit with error message if validation fails
  if (!owner || !repo || !prStr) {
    console.error('❌ Error: Missing arguments.');
    console.error('Usage: npm run dev <owner> <repo> <pr-number>');
    process.exit(1);
  }

  const prNumber = parseInt(prStr, 10);
  if (isNaN(prNumber) || prNumber <= 0) {
    console.error(`❌ Error: Invalid pull request number '${prStr}'. Must be a valid positive integer.`);
    process.exit(1);
  }

  // TODO: Validate authentication (choose ONE method)
  // Students must have either:
  //   - ANTHROPIC_API_KEY environment variable, OR
  //   - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY for Bedrock
  //
  // If using AWS Bedrock:
  //   - Verify AWS_REGION is set
  //   - Log: "🔐 Using AWS Bedrock authentication"
  // If using Anthropic API:
  //   - Log: "🔐 Using Anthropic API authentication"
  // If neither method is configured:
  //   - Exit with clear error message showing both options
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY;
  const awsAccessKeyId = process.env.AWS_ACCESS_KEY_ID;
  const awsSecretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
  const awsRegion = process.env.AWS_REGION;

  if (anthropicApiKey) {
    console.log('🔐 Using Anthropic API authentication');
  } else if (awsAccessKeyId && awsSecretAccessKey) {
    if (!awsRegion) {
      console.error('❌ Error: AWS_REGION environment variable is required when using AWS Bedrock authentication.');
      process.exit(1);
    }
    console.log('🔐 Using AWS Bedrock authentication');
  } else {
    console.error('❌ Error: No authentication credentials provided.');
    console.error('Please configure either:');
    console.error('  - ANTHROPIC_API_KEY for Anthropic API, OR');
    console.error('  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (with AWS_REGION) for AWS Bedrock.');
    process.exit(1);
  }

  // TODO: Validate ANTHROPIC_MODEL environment variable
  // This is REQUIRED for both authentication methods
  // - For AWS Bedrock: us.anthropic.claude-sonnet-4-5-20250929-v1:0
  // - For Anthropic API: claude-sonnet-4-5-20250929
  // Exit with error if not set
const model = process.env.ANTHROPIC_MODEL;
  if (!model) {
    console.error('❌ Error: ANTHROPIC_MODEL environment variable is not set.');
    console.error('  - For AWS Bedrock: us.anthropic.claude-sonnet-4-5-20250929-v1:0');
    console.error('  - For Anthropic API: claude-sonnet-4-5-20250929');
    process.exit(1);
  }

  console.log(`\n🚀 Starting review for ${owner}/${repo} PR #${prNumber} using model: ${model}`);
  try {
    // TODO: Create orchestrator instance
    const orchestrator = new CodeReviewOrchestrator({ model });

    // TODO: Call .reviewPullRequest(owner, repo, prNumber);
    const report = await orchestrator.reviewPullRequest(owner, repo, prNumber);

    // TODO: Generate formatted reports using ReportGenerator
    // Hint: Use ReportGenerator to create Markdown, HTML, and JSON reports
    // Save reports to 'reports/' directory with appropriate filenames
  const reportsDir = path.resolve(process.cwd(), 'reports');
    if (!fs.existsSync(reportsDir)) {
      fs.mkdirSync(reportsDir, { recursive: true });
    }

    const reportGenerator = new ReportGenerator();
    const markdownContent = reportGenerator.generateMarkdownReport(report);
    const htmlContent = reportGenerator.generateHTMLReport(report);
    const jsonContent = reportGenerator.generateJSONReport(report);

    const baseFileName = `pr-${prNumber}-review`;
    fs.writeFileSync(path.join(reportsDir, `${baseFileName}.md`), markdownContent);
    fs.writeFileSync(path.join(reportsDir, `${baseFileName}.html`), htmlContent);
    fs.writeFileSync(path.join(reportsDir, `${baseFileName}.json`), jsonContent);

    console.log(`\n✨ Success! Review completed and saved to '${reportsDir}/'`);
    console.log(`   - Markdown: ${baseFileName}.md`);
    console.log(`   - HTML:     ${baseFileName}.html`);
    console.log(`   - JSON:     ${baseFileName}.json`);
  } catch (error) {
    console.error('❌ Error during pull request review execution:', error);
    process.exit(1);
  }
}

main();
