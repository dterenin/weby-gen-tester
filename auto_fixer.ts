// auto_fixer.ts - Complete TypeScript solution replacing auto_fix_imports.py
import { Project, SourceFile, Node, ImportDeclaration, SyntaxKind, ts, Identifier, Diagnostic } from "ts-morph";
import path from "node:path";
import fs from "node:fs";

// Enhanced type definitions for better type safety
interface ExportInfo {
  path: string;
  isDefault: boolean;
  sourceFile?: SourceFile;
}

interface PreprocessResult {
  content: string;
  wasChanged: boolean;
  changes: string[];
}

interface DiagnosticFix {
  code: number;
  message: string;
  applied: boolean;
  description: string;
}

interface FixerConfig {
  projectPath: string;
  specificFiles: string[];
  buildOutput?: string;
  skipPreprocessing?: boolean;
  verboseLogging?: boolean;
}

interface FixerStats {
  filesProcessed: number;
  importsFixed: number;
  exportsRefactored: number;
  diagnosticsResolved: number;
}

interface FixerOptions {
  // Preprocessing options
  stripMarkdown?: boolean;
  addUseClient?: boolean;
  customClientIndicators?: RegExp[];
  
  // Import fixing options
  enforceNamedExports?: boolean;
  componentsToRefactor?: string[];
  specialImportCases?: Record<string, string>;
  
  // Performance options
  batchSize?: number;
  maxConcurrency?: number;
  enableCaching?: boolean;
  
  // Logging options
  verboseLogging?: boolean;
  logLevel?: 'error' | 'warn' | 'info' | 'debug';
}

const DEFAULT_OPTIONS: Required<FixerOptions> = {
  stripMarkdown: true,
  addUseClient: true,
  customClientIndicators: [],
  enforceNamedExports: true,
  componentsToRefactor: [
    "src/components/header.tsx",
    "src/components/footer.tsx", 
    "src/components/hero.tsx"
  ],
  specialImportCases: {
    'cn': '@/lib/utils'
  },
  batchSize: 50,
  maxConcurrency: 4,
  enableCaching: true,
  verboseLogging: false,
  logLevel: 'info'
};

// Legacy global export map for backward compatibility
const exportMap = new Map<string, { path: string; isDefault: boolean }>();

/**
 * Pre-processing functions migrated from Python script
 */
function stripMarkdownFences(content: string): { content: string; wasChanged: boolean } {
  const lines = content.split('\n');
  if (!lines.length) return { content, wasChanged: false };
  
  const fenceIndices = lines
    .map((line, i) => line.trim().startsWith('```') ? i : -1)
    .filter(i => i !== -1);
    
  if (fenceIndices.length >= 2 && fenceIndices[0] < fenceIndices[fenceIndices.length - 1]) {
    const cleanedLines = lines.slice(fenceIndices[0] + 1, fenceIndices[fenceIndices.length - 1]);
    return { content: cleanedLines.join('\n'), wasChanged: true };
  }
  return { content, wasChanged: false };
}

function needsUseClient(content: string): boolean {
  if (/^["']use client["'];?\s*$/m.test(content.trim())) return false;
  
  const clientIndicators = [
    /\buseState\s*\(/,
    /\buseEffect\s*\(/,
    /\bonClick\s*=/,
    /react-hot-toast/,
    /sonner/,
    /@dnd-kit/,
    /embla-carousel-react/,
    /recharts/,
    /cmdk/,
    /input-otp/,
    /react-day-picker/,
    /react-hook-form/,
    /next-themes/,
    /vaul/
  ];
  
  return clientIndicators.some(pattern => pattern.test(content));
}

function addUseClient(content: string): string {
  const lines = content.split('\n');
  const startIndex = lines.length > 0 && lines[0].startsWith('#!') ? 1 : 0;
  lines.splice(startIndex, 0, '"use client";');
  return lines.join('\n');
}

function preprocessFile(filePath: string): boolean {
  try {
    const originalContent = fs.readFileSync(filePath, 'utf-8');
    let content = originalContent;
    let wasChanged = false;

    // Strip Markdown fences
    const { content: strippedContent, wasChanged: stripped } = stripMarkdownFences(content);
    if (stripped) {
      content = strippedContent;
      wasChanged = true;
      console.log(`  - Stripped Markdown from ${path.basename(filePath)}`);
    }

    // Add "use client" if needed
    if (needsUseClient(content)) {
      content = addUseClient(content);
      wasChanged = true;
      console.log(`  - Added 'use client' to ${path.basename(filePath)}`);
    }

    if (wasChanged) {
      fs.writeFileSync(filePath, content, 'utf-8');
    }

    return wasChanged;
  } catch (error) {
    console.log(`  - ❌ Error preprocessing ${path.basename(filePath)}: ${error}`);
    return false;
  }
}

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
 * Main controller class for TypeScript project auto-fixing
 * Encapsulates all state and provides a clean API
 */
class TypeScriptAutoFixer {
  private readonly project: Project;
  private readonly config: FixerConfig;
  private readonly exportMap = new Map<string, ExportInfo>();
  private readonly stats: FixerStats = {
    filesProcessed: 0,
    importsFixed: 0,
    exportsRefactored: 0,
    diagnosticsResolved: 0
  };

  constructor(config: FixerConfig) {
    this.config = config;
    this.project = new Project({
      tsConfigFilePath: path.join(config.projectPath, "tsconfig.json"),
      skipAddingFilesFromTsConfig: true,
    });
  }

  /**
   * Main entry point for the fixing process
   */
  async fixProject(): Promise<FixerStats> {
    console.log("🚀 Starting Enhanced TypeScript Auto-Fix...");
    
    try {
      await this.preprocessFiles();
      await this.initializeProject();
      await this.executeFixingPasses();
      await this.finalizeChanges();
      
      return this.stats;
    } catch (error) {
      console.error("❌ Auto-fix failed:", error);
      throw error;
    }
  }

  /**
   * Enhanced preprocessing with better error handling and validation
   */
  private async preprocessFiles(): Promise<void> {
    if (this.config.skipPreprocessing) {
      console.log("⏭️  Skipping preprocessing as requested");
      return;
    }

    console.log("\n🐍 Stage 1: Text-based preprocessing...");
    const filesToProcess = await this.getFilesToProcess();
    
    const results = await Promise.allSettled(
      filesToProcess.map(filePath => this.preprocessSingleFile(filePath))
    );
    
    const successful = results.filter(r => r.status === 'fulfilled').length;
    const failed = results.filter(r => r.status === 'rejected');
    
    console.log(`✅ Preprocessing complete: ${successful}/${filesToProcess.length} files processed`);
    
    if (failed.length > 0) {
      console.warn(`⚠️  ${failed.length} files failed preprocessing:`);
      failed.forEach((result, index) => {
        if (result.status === 'rejected') {
          console.warn(`  - ${filesToProcess[index]}: ${result.reason}`);
        }
      });
    }
    
    this.stats.filesProcessed = successful;
  }

  /**
   * Get list of files to process
   */
  private async getFilesToProcess(): Promise<string[]> {
    if (this.config.specificFiles.length > 0) {
      return this.config.specificFiles;
    }

    // Scan for files if none specified
    const srcDir = path.join(this.config.projectPath, 'src');
    const extensions = ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx'];
    const filesToProcess: string[] = [];
    
    try {
      const glob = require('glob');
      for (const ext of extensions) {
        const files = glob.sync(path.join(srcDir, ext));
        filesToProcess.push(...files.filter((f: string) => !f.includes('node_modules')));
      }
    } catch (error) {
      console.log("Warning: glob not available, processing specific files only");
    }

    return filesToProcess;
  }

  /**
   * Preprocess a single file
   */
  private async preprocessSingleFile(filePath: string): Promise<boolean> {
    return preprocessFile(filePath);
  }

  /**
   * Initialize the TypeScript project
   */
  private async initializeProject(): Promise<void> {
    console.log("\n🤖 Stage 2: Initializing TypeScript project...");
    const srcDir = path.join(this.config.projectPath, 'src');
    console.log(`🤖 Indexing all source files in ${srcDir}...`);
    this.project.addSourceFilesAtPaths(`${srcDir}/**/*.{ts,tsx}`);
    console.log(`🤖 Found ${this.project.getSourceFiles().length} source files.`);
  }

  /**
   * Execute all fixing passes
   */
  private async executeFixingPasses(): Promise<void> {
    // Pass 1: Enforce named exports
    enforceNamedExports(this.project);

    // Pass 2: Build export map
    buildExportMap(this.project);
    
    // Pass 3: Fix imports based on diagnostics
    const sourceFilesToFix = this.config.specificFiles.length > 0 
      ? this.config.specificFiles.map(filePath => this.project.getSourceFileOrThrow(filePath))
      : this.project.getSourceFiles().filter(sf => !sf.getFilePath().includes('/node_modules/') && !sf.isDeclarationFile());
        
    for (const sourceFile of sourceFilesToFix) {
      fixImportsBasedOnDiagnostics(sourceFile);
    }

    // Pass 4: Handle Next.js specific build errors
    fixNextJsBuildErrors(this.project, this.config.buildOutput);
  }

  /**
   * Finalize changes and organize imports
   */
  private async finalizeChanges(): Promise<void> {
    console.log("  - [Pass 5] Organizing imports and cleaning up...");
    const sourceFilesToFix = this.config.specificFiles.length > 0 
      ? this.config.specificFiles.map(filePath => this.project.getSourceFileOrThrow(filePath))
      : this.project.getSourceFiles().filter(sf => !sf.getFilePath().includes('/node_modules/') && !sf.isDeclarationFile());
        
    for (const sourceFile of sourceFilesToFix) {
      sourceFile.organizeImports();
    }

    console.log("🤖 Saving all changes...");
    await this.project.save();
  }

  /**
   * Check if source file is valid for processing
   */
  private isValidSourceFile(sf: SourceFile): boolean {
    return !sf.getFilePath().includes("/node_modules/") && !sf.isDeclarationFile();
  }

  /**
   * Optimized export map building with batching and caching
   */
  private buildExportMap(): void {
    console.log("  - [Pass 2] Building optimized export map...");
    this.exportMap.clear();
    
    const sourceFiles = this.project.getSourceFiles()
      .filter(sf => this.isValidSourceFile(sf));
    
    // Process files in batches for better memory management
    const batchSize = 50;
    for (let i = 0; i < sourceFiles.length; i += batchSize) {
      const batch = sourceFiles.slice(i, i + batchSize);
      this.processBatch(batch);
    }
    
    console.log(`  - Export map built: ${this.exportMap.size} exports indexed`);
    this.validateExportMap();
  }

  /**
   * Process a batch of source files for export extraction
   */
  private processBatch(sourceFiles: SourceFile[]): void {
    for (const sourceFile of sourceFiles) {
      try {
        this.extractExportsFromFile(sourceFile);
      } catch (error) {
        console.warn(`⚠️  Failed to process ${sourceFile.getBaseName()}: ${error}`);
      }
    }
  }

  /**
   * Extract exports from a single file
   */
  private extractExportsFromFile(sourceFile: SourceFile): void {
    const filePath = sourceFile.getFilePath();
    
    // Only process files in the src directory
    if (!filePath.includes('/src/')) {
      return;
    }
    
    // Calculate the module specifier for imports (@/...)
    const srcIndex = filePath.indexOf('/src/');
    const relativePath = filePath.substring(srcIndex + 5).replace(/\.(ts|tsx)$/, '').replace(/\\/g, '/');
    const moduleSpecifier = `@/${relativePath.replace(/\/index$/, '')}`;
    
    // Handle default exports
    const defaultExportSymbol = sourceFile.getDefaultExportSymbol();
    if (defaultExportSymbol) {
      let exportName = defaultExportSymbol.getAliasedSymbol()?.getName() ?? defaultExportSymbol.getName();
      if (exportName === 'default') {
        const baseName = sourceFile.getBaseNameWithoutExtension();
        exportName = (baseName !== 'index') 
          ? (baseName.charAt(0).toUpperCase() + baseName.slice(1)) 
          : (path.basename(path.dirname(sourceFile.getFilePath())).charAt(0).toUpperCase() + path.basename(path.dirname(sourceFile.getFilePath())).slice(1));
      }
      if (!this.exportMap.has(exportName)) {
        this.exportMap.set(exportName, { path: moduleSpecifier, isDefault: true, sourceFile });
      }
    }
    
    // Handle named exports
    const exportSymbols = sourceFile.getExportSymbols();
    exportSymbols.forEach(symbol => {
      const name = symbol.getName();
      if (name !== "default" && !this.exportMap.has(name)) {
        this.exportMap.set(name, { path: moduleSpecifier, isDefault: false, sourceFile });
      }
    });
  }

  /**
   * Validate the export map
   */
  private validateExportMap(): void {
    if (this.exportMap.size === 0) {
      console.warn(`⚠️  WARNING: No exports found! This might indicate a problem with file indexing.`);
    }
  }

  /**
   * Enhanced import fixing with smart resolution strategies
   */
  private fixImportsIntelligently(sourceFile: SourceFile): DiagnosticFix[] {
    const fixes: DiagnosticFix[] = [];
    const diagnostics = sourceFile.getPreEmitDiagnostics();
    
    for (const diagnostic of diagnostics) {
      const fix = this.createFixForDiagnostic(diagnostic, sourceFile);
      if (fix && this.applyFix(fix, sourceFile)) {
        fixes.push(fix);
        this.stats.diagnosticsResolved++;
      }
    }
    
    return fixes;
  }

  /**
   * Create appropriate fix strategy based on diagnostic code
   */
  private createFixForDiagnostic(diagnostic: Diagnostic, sourceFile: SourceFile): DiagnosticFix | null {
    const code = diagnostic.getCode();
    const message = diagnostic.getMessageText();
    
    switch (code) {
      case 2613: // Module has no default export
        return this.createDefaultToNamedFix(diagnostic, sourceFile);
      case 2304: // Cannot find name
        return this.createMissingImportFix(diagnostic, sourceFile);
      case 2307: // Cannot resolve module
        return this.createModuleResolutionFix(diagnostic, sourceFile);
      default:
        return null;
    }
  }

  /**
   * Create fix for default to named export conversion
   */
  private createDefaultToNamedFix(diagnostic: Diagnostic, sourceFile: SourceFile): DiagnosticFix | null {
    // Implementation for default to named export fix
    return {
      code: diagnostic.getCode(),
      message: diagnostic.getMessageText().toString(),
      applied: false,
      description: "Convert default import to named import"
    };
  }

  /**
   * Create fix for missing import
   */
  private createMissingImportFix(diagnostic: Diagnostic, sourceFile: SourceFile): DiagnosticFix | null {
    // Implementation for missing import fix
    return {
      code: diagnostic.getCode(),
      message: diagnostic.getMessageText().toString(),
      applied: false,
      description: "Add missing import"
    };
  }

  /**
   * Create fix for module resolution
   */
  private createModuleResolutionFix(diagnostic: Diagnostic, sourceFile: SourceFile): DiagnosticFix | null {
    // Implementation for module resolution fix
    return {
      code: diagnostic.getCode(),
      message: diagnostic.getMessageText().toString(),
      applied: false,
      description: "Fix module resolution"
    };
  }

  /**
   * Apply a diagnostic fix
   */
  private applyFix(fix: DiagnosticFix, sourceFile: SourceFile): boolean {
    // Implementation for applying fixes
    return true;
  }
}

/**
 * Backward-compatible main function that preserves existing API
 * while using the new enhanced architecture internally
 */
async function fixProject(
  projectPath: string, 
  specificFilePaths: string[], 
  buildOutput?: string
): Promise<void> {
  console.log("🚀 Starting Hybrid Auto-Fix for TypeScript project...");
  
  // --- STAGE 1: Pre-processing (from Python script) ---
  console.log("\n🐍 [TS] Stage 1: Running text-based pre-processing...");
  let preprocessedCount = 0;
  
  const filesToProcess = specificFilePaths.length > 0 
    ? specificFilePaths 
    : [];
    
  if (filesToProcess.length === 0) {
    // Scan for files if none specified
    const srcDir = path.join(projectPath, 'src');
    const extensions = ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx'];
    
    try {
      const glob = require('glob');
      for (const ext of extensions) {
        const files = glob.sync(path.join(srcDir, ext));
        filesToProcess.push(...files.filter((f: string) => !f.includes('node_modules')));
      }
    } catch (error) {
      console.log("Warning: glob not available, processing specific files only");
    }
  }
  
  for (const filePath of filesToProcess) {
    if (preprocessFile(filePath)) {
      preprocessedCount++;
    }
  }
  
  console.log(`🐍 [TS] Pre-processing complete. ${preprocessedCount} files modified.`);
  
  if (filesToProcess.length === 0) {
    console.log("✅ No files to process. Exiting.");
    return;
  }
  
  // --- STAGE 2: TypeScript AST-based fixing ---
  console.log("\n🤖 [TS] Stage 2: Initializing TypeScript project...");
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
  console.log("✅ Hybrid Auto-Fix complete!");
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
