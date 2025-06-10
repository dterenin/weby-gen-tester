// auto_fixer.ts
import { Project, SourceFile, Node, ImportDeclaration, SyntaxKind, ts, Identifier } from "ts-morph";
import path from "node:path";

// A map to store all available exports in the project.
const exportMap = new Map<string, { path: string; isDefault: boolean }>();

/**
 * Pass 1: Proactively refactors key components (like Header/Footer/Hero) to use named exports.
 * This enforces a consistent style at the source and prevents import/export mismatches.
 */
function enforceNamedExports(project: Project) {
  console.log("  - [Pass 1] Enforcing named exports for key components...");
  
  // Extended list to include hero.tsx which was causing the build error
  const componentsToRefactor = [
    "src/components/header.tsx", 
    "src/components/footer.tsx",
    "src/components/hero.tsx"  // Added hero.tsx to fix the build error
  ];
  
  for (const relativePath of componentsToRefactor) {
    const sourceFile = project.getSourceFile(sf => sf.getFilePath().endsWith(relativePath));
    if (!sourceFile) continue;

    const exportAssignment = sourceFile.getExportAssignment(e => !e.isExportEquals());
    if (!exportAssignment) continue;
    
    const expression = exportAssignment.getExpression();
    if (!Node.isIdentifier(expression)) continue;

    const exportName = expression.getText();
    console.log(`    - 🔄 Refactoring '${exportName}' in ${relativePath} to a named export.`);
    
    // Find all references to this export and update imports
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

    // Convert the declaration to a named export
    const declaration = expression.getSymbolOrThrow().getDeclarations()[0];
    if (Node.isVariableDeclaration(declaration)) {
      const varStatement = declaration.getParent().getParent();
      if (Node.isVariableStatement(varStatement)) varStatement.setIsExported(true);
    } else if (Node.isFunctionDeclaration(declaration) || Node.isClassDeclaration(declaration)) {
      declaration.setIsExported(true);
    }
    
    // Remove the default export statement
    exportAssignment.remove();
  }
}

/**
 * Pass 2: Build a comprehensive map of all available exports in the project.
 * This is essential for fixing completely missing imports (TS2304 errors).
 */
function buildExportMap(project: Project) {
  console.log("  - [Pass 2] Building project-wide export map...");
  exportMap.clear();

  project.getSourceFiles().forEach(sourceFile => {
    // Skip node_modules and declaration files
    if (sourceFile.getFilePath().includes("/node_modules/") || sourceFile.isDeclarationFile()) return;
    
    const filePath = sourceFile.getFilePath();
    console.log(`    - Checking file: ${filePath}`);
    
    // Only process files in the src directory
    if (!filePath.includes('/src/')) {
      console.log(`    - Skipping file outside src: ${filePath}`);
      return;
    }
    
    // Calculate the module specifier for imports (@/...)
    const srcIndex = filePath.indexOf('/src/');
    const relativePath = filePath.substring(srcIndex + 5).replace(/\.(ts|tsx)$/, '').replace(/\\/g, '/');
    const moduleSpecifier = `@/${relativePath.replace(/\/index$/, '')}`;
    
    console.log(`    - Processing file: ${filePath}`);
    console.log(`    - Module specifier: ${moduleSpecifier}`);
    
    // Handle default exports
    const defaultExportSymbol = sourceFile.getDefaultExportSymbol();
    if (defaultExportSymbol) {
      let exportName = defaultExportSymbol.getAliasedSymbol()?.getName() ?? defaultExportSymbol.getName();
      // If the export name is 'default', derive it from the filename
      if (exportName === 'default') {
        const baseName = sourceFile.getBaseNameWithoutExtension();
        exportName = (baseName !== 'index') 
          ? (baseName.charAt(0).toUpperCase() + baseName.slice(1)) 
          : (path.basename(path.dirname(sourceFile.getFilePath())).charAt(0).toUpperCase() + path.basename(path.dirname(sourceFile.getFilePath())).slice(1));
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
 * Pass 3: Fix import-related errors based on TypeScript diagnostics.
 * This handles various import/export mismatch scenarios.
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
    
    // CASE 1: Module has no default export, suggests using named import
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

    // CASE 2: Cannot find name - missing import
    if (code === 2304 && typeof messageText === 'string') {
        const match = messageText.match(/'([^']+)'/);
        if (match) {
            const importName = match[1];
            console.log(`    - Looking for missing import: ${importName}`);
            
            // Special case for utility functions
            if (importName === 'cn') {
                console.log(`    - 🎯 Adding special case: 'cn' from '@/lib/utils' (TS2304).`);
                sourceFile.addImportDeclaration({ moduleSpecifier: '@/lib/utils', namedImports: ['cn'] });
                changesMade = true;
                continue;
            }

            // Look up in the export map
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

    // CASE 3: Module cannot be found - path resolution issues
    if (code === 2307 && typeof messageText === 'string') {
        const match = messageText.match(/Module '([^']+)'/);
        if (match) {
            const modulePath = match[1];
            console.log(`    - 🔍 Found module resolution error for '${modulePath}' (TS2307).`);
            
            // Fix malformed @/ paths
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
 * Pass 4: Handle Next.js build errors that aren't caught by TypeScript diagnostics.
 * This parses build output and fixes import/export mismatches.
 */
function fixNextJsBuildErrors(project: Project, buildOutput?: string) {
  if (!buildOutput) return;
  
  console.log("  - [Pass 4] Fixing Next.js build errors...");
  
  // Parse "Attempted import error" messages from Next.js build output
  const exportErrors = buildOutput.match(/Attempted import error: '([^']+)' is not exported from '([^']+)'/g);
  
  if (exportErrors) {
    for (const error of exportErrors) {
      const match = error.match(/Attempted import error: '([^']+)' is not exported from '([^']+)'/);
      if (match) {
        const [, importName, modulePath] = match;
        console.log(`    - 🔍 Found Next.js import error: '${importName}' from '${modulePath}'`);
        fixImportExportMismatch(project, importName, modulePath);
      }
    }
  }
}

/**
 * Helper function to fix import/export mismatches detected in build errors.
 */
function fixImportExportMismatch(project: Project, importName: string, modulePath: string) {
  // Find the module file
  const moduleFile = project.getSourceFile(sf => {
    const filePath = sf.getFilePath();
    return filePath.includes(modulePath.replace('@/', 'src/'));
  });
  
  if (!moduleFile) {
    console.log(`    - ❌ Could not find module file for '${modulePath}'`);
    return;
  }
  
  // Check what type of export exists
  const hasDefaultExport = moduleFile.getDefaultExportSymbol();
  const hasNamedExport = moduleFile.getExportSymbols().some(s => s.getName() === importName);
  
  console.log(`    - Module analysis: hasDefault=${!!hasDefaultExport}, hasNamed=${hasNamedExport}`);
  
  if (hasDefaultExport && !hasNamedExport) {
    // The module has a default export but the import expects a named export
    // Fix all files that import from this module
    project.getSourceFiles().forEach(sf => {
      const importDecl = sf.getImportDeclaration(d => 
        d.getModuleSpecifier().getLiteralValue() === modulePath
      );
      
      if (importDecl) {
        const namedImports = importDecl.getNamedImports();
        const targetImport = namedImports.find(ni => ni.getName() === importName);
        
        if (targetImport) {
          console.log(`    - 🛠️  Converting named import '${importName}' to default import in ${path.basename(sf.getFilePath())}`);
          
          // Remove the named import
          targetImport.remove();
          
          // If this was the only named import, remove the entire named imports clause
          if (namedImports.length === 1) {
            importDecl.removeNamedImports();
          }
          
          // Add as default import
          importDecl.setDefaultImport(importName);
        }
      }
    });
  }
}

/**
 * Main function that orchestrates the entire code fixing process.
 */
async function fixProject(projectPath: string, specificFilePaths: string[], buildOutput?: string): Promise<void> {
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

  // --- PASS 4: Handle Next.js specific build errors ---
  fixNextJsBuildErrors(project, buildOutput);

  // --- PASS 5: Final cleanup and organization ---
  console.log("  - [Pass 5] Organizing imports and cleaning up...");
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

// Check for build output flag
const buildErrorsFlag = process.argv.includes('--build-errors');
let buildOutput: string | undefined;

if (buildErrorsFlag) {
  // Read build output from stdin when --build-errors flag is present
  const chunks: Buffer[] = [];
  process.stdin.on('data', chunk => chunks.push(chunk));
  process.stdin.on('end', () => {
    buildOutput = Buffer.concat(chunks).toString();
    runFixer();
  });
} else {
  runFixer();
}

function runFixer() {
  if (!projectDirectory) {
    console.error("❌ [TS] Error: Project directory path is required as the first argument.");
    process.exit(1);
  }

  fixProject(path.resolve(projectDirectory), specificFiles, buildOutput).catch((err) => {
    console.error("❌ [TS] An unexpected error occurred:", err);
    process.exit(1);
  });
}
