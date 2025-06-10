// auto_fixer.ts
import { Project, SourceFile, SyntaxKind, Node, ts, Identifier, ImportDeclaration } from "ts-morph";
import path from "node:path";

// A map to store all available exports in the project.
// Key: export name (e.g., "Button"), Value: information about the export.
const exportMap = new Map<string, { path: string; isDefault: boolean }>();

/**
 * First pass: Traverse the entire project to find and map all available exports.
 * This populates the `exportMap`.
 */
function buildExportMap(project: Project) {
  console.log("  - [Pass 1] Building project-wide export map...");
  project.getSourceFiles().forEach(sourceFile => {
    // Ignore node_modules and declaration files for performance
    if (sourceFile.getFilePath().includes("/node_modules/") || sourceFile.isDeclarationFile()) {
      return;
    }

    const relativePath = path.relative(project.getRootDirectories()[0].getPath(), sourceFile.getFilePath()).replace(/\.(ts|tsx)$/, '');
    const moduleSpecifier = `@/${relativePath}`;

    // Find default exports: `export default ...`
    const defaultExport = sourceFile.getDefaultExportSymbol();
    if (defaultExport) {
      let finalName: string | null = null;
      // CORRECTED: Try to get the actual name from the export expression (e.g., `export default MyComponent`)
      const exportAssignment = defaultExport.getDeclarations()[0];
      if (Node.isExportAssignment(exportAssignment)) {
          const expression = exportAssignment.getExpression();
          if (Node.isIdentifier(expression)) {
              finalName = expression.getText();
          }
      }
      
      // Fallback to the old logic (PascalCased filename) if a name couldn't be inferred
      if (!finalName) {
        const componentName = sourceFile.getBaseNameWithoutExtension();
        // Use PascalCase for component names, common convention.
        finalName = componentName.charAt(0).toUpperCase() + componentName.slice(1);
      }
      
      if (!exportMap.has(finalName)) {
        exportMap.set(finalName, { path: moduleSpecifier, isDefault: true });
      }
    }

    // Find named exports: `export { Button }` or `export const Button = ...`
    sourceFile.getExportSymbols().forEach(symbol => {
      const name = symbol.getName();
      // CORRECTED: `cn` is often a named export from `lib/utils`, this logic will now find it.
      if (name !== "default" && !exportMap.has(name)) {
        exportMap.set(name, { path: moduleSpecifier, isDefault: false });
      }
    });
  });
  console.log(`  - [Pass 1] Export map built. Found ${exportMap.size} unique potential imports.`);
}


/**
 * Second pass: Find unresolved identifiers and add the correct imports based on the export map.
 */
function fixMissingImportsIntelligently(sourceFile: SourceFile) {
  console.log(`  - [Pass 2] Analyzing imports for ${path.basename(sourceFile.getFilePath())}...`);
  const diagnostics = sourceFile.getPreEmitDiagnostics();
  const unresolvedIdentifiers = new Set<string>();

  // Error code 2304: Cannot find name '...'.
  diagnostics.forEach(diagnostic => {
    if (diagnostic.getCode() === 2304) {
      const messageText = diagnostic.getMessageText();
      const match = typeof messageText === 'string' && messageText.match(/'([^']+)'/);
      if (match) {
        unresolvedIdentifiers.add(match[1]);
      }
    }
  });

  if (unresolvedIdentifiers.size === 0) {
    console.log(`    - No unresolved identifiers found. Skipping.`);
    return;
  }

  console.log(`    - Found unresolved identifiers: ${Array.from(unresolvedIdentifiers).join(', ')}`);

  // Add imports for each unresolved identifier found in our map
  unresolvedIdentifiers.forEach(name => {
    // CORRECTED: Add a special, high-priority case for the `cn` utility function.
    if (name === 'cn') {
        console.log(`    - 🎯 Special case: Found 'cn'. Importing from '@/lib/utils'.`);
        sourceFile.addImportDeclaration({
            moduleSpecifier: '@/lib/utils',
            namedImports: ['cn'],
        });
        return; // Skip the generic lookup for `cn`
    }

    const exportInfo = exportMap.get(name);
    if (exportInfo) {
      console.log(`    - Found match for '${name}'. Importing from '${exportInfo.path}' (isDefault: ${exportInfo.isDefault})`);
      
      const newImport: ImportDeclaration = sourceFile.addImportDeclaration({
        moduleSpecifier: exportInfo.path,
      });

      if (exportInfo.isDefault) {
        newImport.setDefaultImport(name);
      } else {
        newImport.addNamedImport(name);
      }
    } else {
        console.log(`    - ⚠️ No match found in export map for '${name}'. It might be a native type or from an un-indexed library.`);
    }
  });
}


/**
 * The core code fixer logic.
 */
async function fixProject(projectPath: string, specificFilePaths: string[]): Promise<void> {
  console.log("🤖 [TS] Initializing TypeScript project...");
  const project = new Project({
    tsConfigFilePath: path.join(projectPath, "tsconfig.json"),
    // Important for performance: skip adding files from node_modules.
    skipAddingFilesFromTsConfig: true,
  });

  // Explicitly add only the files we need to process to the project.
  console.log(`🤖 [TS] Adding ${specificFilePaths.length} source files to the project...`);
  const sourceFiles = specificFilePaths.map(filePath => project.addSourceFileAtPath(filePath));

  // CORRECTED: Scan the *entire* src directory for potential imports, not just components.
  // This is crucial for finding helpers like `cn` in `lib/utils` and components in `ui/`.
  const srcDir = path.join(projectPath, 'src');
  console.log(`🤖 [TS] Indexing all exportable symbols in ${srcDir}...`);
  project.addSourceFilesAtPaths(`${srcDir}/**/*.{ts,tsx}`);
  
  // --- PASS 1: Build the map of all available exports ---
  buildExportMap(project);

  // --- PASS 2: Fix imports intelligently for each target file ---
  for (const sourceFile of sourceFiles) {
    fixMissingImportsIntelligently(sourceFile);
  }
  
  // --- PASS 3: Final cleanup ---
  console.log("  - [Pass 3] Organizing imports and cleaning up...");
  for (const sourceFile of sourceFiles) {
    sourceFile.organizeImports();
  }

  console.log("🤖 [TS] Saving all changes...");
  await project.save();
  console.log("🤖 [TS] Code fixing complete!");
}

// --- Main execution block ---
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