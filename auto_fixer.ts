// auto_fixer.ts
import { Project, IndentationText, QuoteKind } from "ts-morph";
import path from "path";

/**
 * The core code fixer using the TypeScript compiler API via ts-morph.
 * This script understands the code's structure (AST) and can perform
 * safe and accurate modifications.
 */
async function fixProject(projectPath: string): Promise<void> {
  console.log("🤖 [TS] Initializing TypeScript project...");

  const project = new Project({
    // It's crucial to point to the project's tsconfig.json
    // to understand path aliases like `@/components`.
    tsConfigFilePath: path.join(projectPath, "tsconfig.json"),
    manipulationSettings: {
      indentationText: IndentationText.TwoSpaces,
      quoteKind: QuoteKind.Double,
    },
  });

  console.log(`🤖 [TS] Analyzing all source files in: ${projectPath}`);
  const sourceFiles = project.getSourceFiles();
  console.log(`🤖 [TS] Found ${sourceFiles.length} files to process.`);

  for (const sourceFile of sourceFiles) {
    const filePath = sourceFile.getFilePath();
    console.log(`  - Processing ${path.basename(filePath)}`);

    // The magic happens here. ts-morph provides high-level functions
    // that use the TypeScript language service to fix common issues.
    
    // 1. Fix missing imports. This looks for undefined identifiers
    //    (like 'AnimatedButton' or 'useState') and adds imports if
    //    the symbol can be found in the project or its dependencies.
    sourceFile.fixMissingImports();

    // 2. Organize imports. This powerful command does three things:
    //    - Removes unused imports.
    //    - Merges multiple import declarations from the same module.
    //    - Sorts imports alphabetically.
    //    This single line replaces all our complex regex logic from Python.
    sourceFile.organizeImports();
  }

  // Save all the changes made to the files in memory back to the disk.
  console.log("🤖 [TS] Saving all changes...");
  await project.save();
  console.log("🤖 [TS] Code fixing complete!");
}

// --- Main execution block ---
const targetDirectory = process.argv[2];

if (!targetDirectory) {
  console.error("❌ [TS] Error: Please provide a project directory path.");
  process.exit(1);
}

fixProject(path.resolve(targetDirectory)).catch((err) => {
  console.error("❌ [TS] An unexpected error occurred:", err);
  process.exit(1);
});