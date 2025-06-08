// auto_fixer.ts
import { Project, SourceFile, SyntaxKind, Node } from "ts-morph";
import path from "node:path";

/**
 * Specifically corrects known wrong imports that ts-morph might add.
 * This runs AFTER fixMissingImports and acts as a "cleanup" step.
 */
function correctAmbiguousImports(sourceFile: SourceFile): boolean {
  let wasModified = false;
  for (const importDeclaration of sourceFile.getImportDeclarations()) {
    // Rule 1: 'Button' should never come from 'react-day-picker' in this project.
    if (importDeclaration.getModuleSpecifierValue() === 'react-day-picker') {
      const buttonImport = importDeclaration.getNamedImports().find(spec => spec.getName() === 'Button');
      if (buttonImport) {
        console.log(`    - Correcting wrong import: Button from 'react-day-picker'.`);
        buttonImport.remove();
        // Add the correct import
        sourceFile.addImportDeclaration({
            moduleSpecifier: '@/components/ui/button',
            namedImports: ['Button']
        });
        wasModified = true;
      }
    }
  }
  return wasModified;
}

/**
 * Checks if a source file uses the react-day-picker library.
 */
function fileUsesDayPicker(sourceFile: SourceFile): boolean {
    return /react-day-picker|Calendar/.test(sourceFile.getFullText());
}

/**
 * Wraps the root JSX element in a `DayPickerProvider` if needed.
 */
function wrapRootJsxInProvider(sourceFile: SourceFile): boolean {
    const returnStatement = sourceFile.getDescendantsOfKind(SyntaxKind.ReturnStatement).pop();
    if (!returnStatement) return false;

    const returnExpression = returnStatement.getExpression();
    if (!returnExpression || !Node.isJsxElement(returnExpression) && !Node.isJsxFragment(returnExpression)) return false;
    
    // Avoid double-wrapping
    if (returnExpression.getParentIfKind(SyntaxKind.JsxElement)?.getOpeningElement().getTagNameNode().getText() === 'DayPickerProvider') {
        return false;
    }

    returnExpression.replaceWithText(`<DayPickerProvider initialProps={{}}>${returnExpression.getText()}</DayPickerProvider>`);
    return true;
}

/**
 * The core code fixer logic.
 */
async function fixProject(projectPath: string, specificFilePaths: string[]): Promise<void> {
  console.log("🤖 [TS] Initializing TypeScript project...");
  const project = new Project({ tsConfigFilePath: path.join(projectPath, "tsconfig.json") });
  
  let sourceFiles: SourceFile[];

  // --- PERFORMANCE OPTIMIZATION ---
  // If specific file paths are provided, only load those files.
  if (specificFilePaths.length > 0) {
    console.log(`🤖 [TS] Targeted mode: Processing ${specificFilePaths.length} specific file(s).`);
    sourceFiles = specificFilePaths.map(filePath => {
        try {
            // `addSourceFileAtPath` is robust for adding files that may or may not be known to the project yet.
            return project.addSourceFileAtPath(filePath);
        } catch (e) {
            console.error(`    - ❌ Critical error adding file ${filePath}: ${e}`);
            // Re-throw to halt the process if a file can't be added
            throw e;
        }
    });
  } else {
    // This fallback is kept for standalone script usage but won't be hit by the Python orchestrator.
    console.log(`🤖 [TS] Fallback mode: Scanning all files in project.`);
    sourceFiles = project.getSourceFiles().filter(f => !f.getFilePath().includes("/node_modules/") && /\.(ts|tsx)$/.test(f.getFilePath()));
  }
  console.log(`🤖 [TS] Loaded ${sourceFiles.length} files to process.`);

  // --- PASS 1: Fix imports and correct common mistakes ---
  for (const sourceFile of sourceFiles) {
    const baseName = path.basename(sourceFile.getFilePath());
    console.log(`  - Running import fixes on ${baseName}`);
    // Let ts-morph do the heavy lifting.
    sourceFile.fixMissingImports();
    // Surgically correct known mistakes it might make.
    correctAmbiguousImports(sourceFile);
  }
  
  // --- PASS 2: Fix context providers ---
  // This needs to run after imports are fixed, so we know which files use the library.
  if (sourceFiles.some(fileUsesDayPicker)) {
    console.log("  - Project uses DayPicker. Applying provider fix to entry points...");
    // Only check page.tsx files within the set of files being processed
    const pageFiles = sourceFiles.filter(f => f.getFilePath().includes('/app/') && f.getFilePath().endsWith('page.tsx'));
    for (const pageFile of pageFiles) {
        if (wrapRootJsxInProvider(pageFile)) {
            console.log(`    - Wrapped ${path.basename(pageFile.getFilePath())} in DayPickerProvider.`);
        }
    }
  }

  // --- PASS 3: Final cleanup ---
  for (const sourceFile of sourceFiles) {
      // Add DayPickerProvider import if needed after wrapping
      if (sourceFile.getFullText().includes('<DayPickerProvider')) {
          sourceFile.addImportDeclaration({ moduleSpecifier: 'react-day-picker', namedImports: ['DayPickerProvider'] });
      }
      // Organize all imports alphabetically and remove unused ones.
      sourceFile.organizeImports();
  }

  console.log("🤖 [TS] Saving all changes...");
  await project.save();
  console.log("🤖 [TS] Code fixing complete!");
}

// --- Main execution block ---
// FIX: Argument indices are adjusted for `ts-node script.ts arg1 arg2 ...`
// `process.argv` will be: `['node', 'path/to/ts-node', 'path/to/auto_fixer.ts', projectDirectory, ...specificFiles]`
const projectDirectory = process.argv[2];
const specificFiles = process.argv.slice(3);

if (!projectDirectory) {
  console.error("❌ [TS] Error: Project directory path is required as the first argument.");
  process.exit(1);
}

fixProject(path.resolve(projectDirectory), specificFiles).catch((err) => {
  console.error("❌ [TS] An unexpected error occurred:", err);
  process.exit(1);
});