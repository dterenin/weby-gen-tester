// auto_fixer.ts
import { Project, IndentationText, QuoteKind, SourceFile, SyntaxKind, Node } from "ts-morph";
import path from "node:path";

/**
 * Specifically corrects known wrong imports that ts-morph might add.
 * This runs AFTER fixMissingImports and acts as a "cleanup" step.
 */
function correctAmbiguousImports(sourceFile: SourceFile) {
  let wasModified = false;
  for (const importDeclaration of sourceFile.getImportDeclarations()) {
    // Rule 1: 'Button' should never come from 'react-day-picker'
    if (importDeclaration.getModuleSpecifierValue() === 'react-day-picker') {
      const buttonImport = importDeclaration.getNamedImports().find(spec => spec.getName() === 'Button');
      if (buttonImport) {
        console.log(`    - Correcting wrong import: Button from 'react-day-picker'.`);
        buttonImport.remove();
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

function fileUsesDayPicker(sourceFile: SourceFile): boolean {
    return /react-day-picker|Calendar/.test(sourceFile.getFullText());
}

function wrapRootJsxInProvider(sourceFile: SourceFile): boolean {
    const returnStatement = sourceFile.getDescendantsOfKind(SyntaxKind.ReturnStatement).pop();
    if (!returnStatement) return false;

    const returnExpression = returnStatement.getExpression();
    if (!returnExpression || !Node.isJsxElement(returnExpression) && !Node.isJsxFragment(returnExpression)) return false;
    
    if (returnExpression.getParentIfKind(SyntaxKind.JsxElement)?.getOpeningElement().getTagNameNode().getText() === 'DayPickerProvider') {
        return false; // Already wrapped
    }

    returnExpression.replaceWithText(`<DayPickerProvider initialProps={{}}>${returnExpression.getText()}</DayPickerProvider>`);
    return true;
}

/**
 * The core code fixer.
 */
async function fixProject(projectPath: string): Promise<void> {
  console.log("🤖 [TS] Initializing TypeScript project...");
  const project = new Project({ tsConfigFilePath: path.join(projectPath, "tsconfig.json") });
  const sourceFiles = project.getSourceFiles().filter(f => !f.getFilePath().includes("/node_modules/") && /\.(ts|tsx)$/.test(f.getFilePath()));
  
  console.log(`🤖 [TS] Found ${sourceFiles.length} files to process.`);

  // --- PASS 1: Fix imports and correct common mistakes ---
  for (const sourceFile of sourceFiles) {
    const baseName = path.basename(sourceFile.getFilePath());
    console.log(`  - Running import fixes on ${baseName}`);

    // Step 1: Let ts-morph do the heavy lifting. This gives us 75% success.
    sourceFile.fixMissingImports();
    
    // Step 2: Surgically correct the known mistake it makes.
    correctAmbiguousImports(sourceFile);
  }
  
  // --- PASS 2: Fix context providers ---
  // This needs to run after imports are fixed, so we know which files use the library.
  if (sourceFiles.some(fileUsesDayPicker)) {
    console.log("  - Project uses DayPicker. Applying provider fix to entry points...");
    const pageFiles = sourceFiles.filter(f => f.getFilePath().includes('/app/') && f.getFilePath().endsWith('page.tsx'));
    
    for (const pageFile of pageFiles) {
        if (wrapRootJsxInProvider(pageFile)) {
            // The import will be added in the final pass
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
      sourceFile.organizeImports();
  }

  console.log("🤖 [TS] Saving all changes...");
  await project.save();
  console.log("🤖 [TS] Code fixing complete!");
}

// --- Main execution block ---
const targetDirectory = process.argv[2];
if (!targetDirectory) {
  console.error("❌ [TS] Error: Project directory path is required.");
  process.exit(1);
}
fixProject(path.resolve(targetDirectory)).catch((err) => {
  console.error("❌ [TS] An unexpected error occurred:", err);
  process.exit(1);
});