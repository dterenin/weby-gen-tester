// auto_fixer.ts
import { Project, SourceFile, Node, ImportDeclaration, SyntaxKind, ts, Identifier } from "ts-morph";
import path from "node:path";

// A map to store all available exports in the project.
const exportMap = new Map<string, { path: string; isDefault: boolean }>();

/**
 * Pass 1: Proactively refactors key components (like Header/Footer) to use named exports.
 * This is still valuable to enforce a consistent style at the source.
 */
function enforceNamedExports(project: Project) {
  console.log("  - [Pass 1] Enforcing named exports for key components...");
  
  const componentsToRefactor = ["src/components/header.tsx", "src/components/footer.tsx"];
  
  for (const relativePath of componentsToRefactor) {
    const sourceFile = project.getSourceFile(sf => sf.getFilePath().endsWith(relativePath));
    if (!sourceFile) continue;

    const exportAssignment = sourceFile.getExportAssignment(e => !e.isExportEquals());
    if (!exportAssignment) continue;
    
    const expression = exportAssignment.getExpression();
    if (!Node.isIdentifier(expression)) continue;

    const exportName = expression.getText();
    console.log(`    - 🔄 Refactoring '${exportName}' in ${relativePath} to a named export.`);
    
    const referencedSymbols = expression.findReferences();
    for (const referencedSymbol of referencedSymbols) {
      for (const reference of referencedSymbol.getReferences()) {
        const node = reference.getNode();
        const importClause = node.getParentIfKind(SyntaxKind.ImportClause);
        if (importClause && importClause.getDefaultImport()?.getText() === exportName) {
          const importDeclaration = importClause.getParentIfKindOrThrow(SyntaxKind.ImportDeclaration);
          const existingNamed = importDeclaration.getNamedImports().map(ni => ni.getName());
          const newNamed = [...existingNamed, exportName].sort();
          importDeclaration.removeDefaultImport();
          importDeclaration.addNamedImports(newNamed);
        }
      }
    }

    const declaration = expression.getSymbolOrThrow().getDeclarations()[0];
    if (Node.isVariableDeclaration(declaration)) {
      const varStatement = declaration.getParent().getParent();
      if (Node.isVariableStatement(varStatement)) varStatement.setIsExported(true);
    } else if (Node.isFunctionDeclaration(declaration) || Node.isClassDeclaration(declaration)) {
      declaration.setIsExported(true);
    }
    
    exportAssignment.remove();
  }
}

/**
 * Pass 2: Build the map of all available exports.
 * This is needed for fixing completely missing imports (TS2304).
 */
function buildExportMap(project: Project) {
  console.log("  - [Pass 2] Building project-wide export map...");
  exportMap.clear();

  project.getSourceFiles().forEach(sourceFile => {
    if (sourceFile.getFilePath().includes("/node_modules/") || sourceFile.isDeclarationFile()) return;
    const relativePath = path.relative(project.getRootDirectories()[0].getPath(), sourceFile.getFilePath()).replace(/\.(ts|tsx)$/, '');
    const moduleSpecifier = `@/${relativePath.replace(/\/index$/, '')}`;
    const defaultExportSymbol = sourceFile.getDefaultExportSymbol();
    if (defaultExportSymbol) {
      let exportName = defaultExportSymbol.getAliasedSymbol()?.getName() ?? defaultExportSymbol.getName();
      if (exportName === 'default') {
        const baseName = sourceFile.getBaseNameWithoutExtension();
        exportName = (baseName !== 'index') ? (baseName.charAt(0).toUpperCase() + baseName.slice(1)) : (path.basename(path.dirname(sourceFile.getFilePath())).charAt(0).toUpperCase() + path.basename(path.dirname(sourceFile.getFilePath())).slice(1));
      }
      if (!exportMap.has(exportName)) exportMap.set(exportName, { path: moduleSpecifier, isDefault: true });
    }
    sourceFile.getExportSymbols().forEach(symbol => {
      const name = symbol.getName();
      if (name !== "default" && !exportMap.has(name)) exportMap.set(name, { path: moduleSpecifier, isDefault: false });
    });
  });
  console.log(`  - [Pass 2] Export map built. Found ${exportMap.size} unique potential imports.`);
}

/**
 * Pass 3: Fix all import-related errors based on TypeScript diagnostics.
 * This is the new, unified, and most reliable fixing mechanism.
 */
function fixImportsBasedOnDiagnostics(sourceFile: SourceFile) {
  console.log(`  - [Pass 3] Fixing imports in ${path.basename(sourceFile.getFilePath())} based on diagnostics...`);
  const diagnostics = sourceFile.getPreEmitDiagnostics();
  if (diagnostics.length === 0) {
    console.log("    - No diagnostics found. Skipping.");
    return;
  }

  let changesMade = false;
  for (const diagnostic of diagnostics) {
    const code = diagnostic.getCode();
    const messageText = diagnostic.getMessageText();
    
    // CASE 1: `Module '...' has no default export. Did you mean 'import { ... } from ...'?`
    if (code === 2613 && typeof messageText === 'string') {
        const match = messageText.match(/Did you mean to use 'import \{ ([^}]+) \} from "([^"]+)"'/);
        if (match) {
            const importName = match[1];
            const fullModuleSpecifier = match[2];
            
            const moduleSpecifier = fullModuleSpecifier.includes('@/') 
                ? fullModuleSpecifier 
                : '@/components/header';
            
            const importDeclaration = sourceFile.getImportDeclaration(d => 
                d.getModuleSpecifier().getLiteralValue().includes('header') || 
                d.getModuleSpecifier().getLiteralValue() === moduleSpecifier
            );
            
            if (importDeclaration && importDeclaration.getDefaultImport()) {
                console.log(`    - 🛠️  Fixing incorrect default import for '${importName}' (TS2613).`);
                importDeclaration.removeDefaultImport();
                importDeclaration.addNamedImport(importName);
                changesMade = true;
            }
        }
    }

    // CASE 2: `Cannot find name '...'`
    if (code === 2304 && typeof messageText === 'string') {
        const match = messageText.match(/'([^']+)'/);
        if (match) {
            const importName = match[1];
            if (importName === 'cn') {
                console.log(`    - 🎯 Adding special case: 'cn' from '@/lib/utils' (TS2304).`);
                sourceFile.addImportDeclaration({ moduleSpecifier: '@/lib/utils', namedImports: ['cn'] });
                changesMade = true;
                continue;
            }

            const exportInfo = exportMap.get(importName);
            if (exportInfo) {
                console.log(`    - ✅ Adding missing import for '${importName}' (TS2304).`);
                const newImport = sourceFile.addImportDeclaration({ moduleSpecifier: exportInfo.path });
                if (exportInfo.isDefault) newImport.setDefaultImport(importName);
                else newImport.addNamedImport(importName);
                changesMade = true;
            }
        }
    }
  }

  if (!changesMade) {
    console.log("    - No actionable import diagnostics found.");
  }
}

/**
 * The core code fixer logic.
 */
async function fixProject(projectPath: string, specificFilePaths: string[]): Promise<void> {
  console.log("🤖 [TS] Initializing TypeScript project...");
  const project = new Project({
    tsConfigFilePath: path.join(projectPath, "tsconfig.json"),
    skipAddingFilesFromTsConfig: true,
  });

  const srcDir = path.join(projectPath, 'src');
  console.log(`🤖 [TS] Indexing all source files in ${srcDir}...`);
  project.addSourceFilesAtPaths(`${srcDir}/**/*.{ts,tsx}`);
  
  // --- PASS 1: Proactively refactor key components to use named exports ---
  enforceNamedExports(project);

  // --- PASS 2: Build the map of all available exports based on the new reality ---
  buildExportMap(project);
  
  // --- PASS 3: Fix all import errors in the target files based on diagnostics ---
  const sourceFilesToFix = specificFilePaths.map(filePath => project.getSourceFileOrThrow(filePath));
  for (const sourceFile of sourceFilesToFix) {
    fixImportsBasedOnDiagnostics(sourceFile);
  }

  // --- PASS 4: Final cleanup ---
  console.log("  - [Pass 4] Organizing imports and cleaning up...");
  for (const sourceFile of sourceFilesToFix) {
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