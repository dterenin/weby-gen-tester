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
    
    const filePath = sourceFile.getFilePath();
    console.log(`    - Checking file: ${filePath}`);
    
    // Check if file is in src directory (more robust check)
    if (!filePath.includes('/src/')) {
      console.log(`    - Skipping file outside src: ${filePath}`);
      return;
    }
    
    // Calculate relative path from src directory
    const srcIndex = filePath.indexOf('/src/');
    const relativePath = filePath.substring(srcIndex + 5).replace(/\.(ts|tsx)$/, '').replace(/\\/g, '/');
    const moduleSpecifier = `@/${relativePath.replace(/\/index$/, '')}`;
    
    console.log(`    - Processing file: ${filePath}`);
    console.log(`    - Module specifier: ${moduleSpecifier}`);
    
    // Handle default exports
    const defaultExportSymbol = sourceFile.getDefaultExportSymbol();
    if (defaultExportSymbol) {
      let exportName = defaultExportSymbol.getAliasedSymbol()?.getName() ?? defaultExportSymbol.getName();
      if (exportName === 'default') {
        const baseName = sourceFile.getBaseNameWithoutExtension();
        exportName = (baseName !== 'index') ? (baseName.charAt(0).toUpperCase() + baseName.slice(1)) : (path.basename(path.dirname(sourceFile.getFilePath())).charAt(0).toUpperCase() + path.basename(path.dirname(sourceFile.getFilePath())).slice(1));
      }
      if (!exportMap.has(exportName)) {
        exportMap.set(exportName, { path: moduleSpecifier, isDefault: true });
        console.log(`    - Added default export: ${exportName}`);
      }
    }
    
    // Handle named exports
    const exportSymbols = sourceFile.getExportSymbols();
    exportSymbols.forEach(symbol => {
      const name = symbol.getName();
      if (name !== "default" && !exportMap.has(name)) {
        exportMap.set(name, { path: moduleSpecifier, isDefault: false });
        console.log(`    - Added named export: ${name}`);
      }
    });
  });
  
  console.log(`  - [Pass 2] Export map built. Found ${exportMap.size} unique potential imports.`);
  if (exportMap.size === 0) {
    console.log(`  - [Pass 2] WARNING: No exports found! This might indicate a problem with file indexing.`);
  }
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
    
    console.log(`    - Processing diagnostic ${code}: ${messageText}`);
    
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
            console.log(`    - Looking for missing import: ${importName}`);
            
            if (importName === 'cn') {
                console.log(`    - 🎯 Adding special case: 'cn' from '@/lib/utils' (TS2304).`);
                sourceFile.addImportDeclaration({ moduleSpecifier: '@/lib/utils', namedImports: ['cn'] });
                changesMade = true;
                continue;
            }

            const exportInfo = exportMap.get(importName);
            if (exportInfo) {
                console.log(`    - ✅ Adding missing import for '${importName}' from '${exportInfo.path}' (TS2304).`);
                const newImport = sourceFile.addImportDeclaration({ moduleSpecifier: exportInfo.path });
                if (exportInfo.isDefault) newImport.setDefaultImport(importName);
                else newImport.addNamedImport(importName);
                changesMade = true;
            } else {
                console.log(`    - ❌ Could not find export for '${importName}' in export map.`);
            }
        }
    }

    // CASE 3: `Module '...' or its corresponding type declarations cannot be found`
    if (code === 2307 && typeof messageText === 'string') {
        const match = messageText.match(/Module '([^']+)'/);
        if (match) {
            const modulePath = match[1];
            console.log(`    - 🔍 Found module resolution error for '${modulePath}' (TS2307).`);
            
            // Check if it's a malformed @/ path
            if (modulePath.includes('@/../')) {
                const correctedPath = modulePath.replace('@/../', '@/');
                const importDeclaration = sourceFile.getImportDeclaration(d => 
                    d.getModuleSpecifier().getLiteralValue() === modulePath
                );
                
                if (importDeclaration) {
                    console.log(`    - 🛠️  Fixing malformed path '${modulePath}' to '${correctedPath}' (TS2307).`);
                    importDeclaration.setModuleSpecifier(correctedPath);
                    changesMade = true;
                }
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
  
  console.log(`🤖 [TS] Found ${project.getSourceFiles().length} source files.`);
  
  // --- PASS 1: Proactively refactor key components to use named exports ---
  enforceNamedExports(project);

  // --- PASS 2: Build the map of all available exports based on the new reality ---
  buildExportMap(project);
  
  // --- PASS 3: Fix all import errors in the target files based on diagnostics ---
  const sourceFilesToFix = specificFilePaths.length > 0 
    ? specificFilePaths.map(filePath => project.getSourceFileOrThrow(filePath))
    : project.getSourceFiles().filter(sf => !sf.getFilePath().includes('/node_modules/') && !sf.isDeclarationFile());
    
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