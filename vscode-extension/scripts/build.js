#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🔨 Building RevitPy VS Code Extension...\n');

// Clean previous build
console.log('📁 Cleaning previous build...');
try {
  if (fs.existsSync('out')) {
    fs.rmSync('out', { recursive: true, force: true });
  }
  console.log('✅ Clean completed\n');
} catch (error) {
  console.error('❌ Clean failed:', error.message);
  process.exit(1);
}

// Install dependencies
console.log('📦 Installing dependencies...');
try {
  execSync('npm install', { stdio: 'inherit' });
  console.log('✅ Dependencies installed\n');
} catch (error) {
  console.error('❌ Dependency installation failed');
  process.exit(1);
}

// Compile TypeScript
console.log('🔧 Compiling TypeScript...');
try {
  execSync('npm run compile', { stdio: 'inherit' });
  console.log('✅ TypeScript compilation completed\n');
} catch (error) {
  console.error('❌ TypeScript compilation failed');
  process.exit(1);
}

// Run linting
console.log('🔍 Running ESLint...');
try {
  execSync('npm run lint', { stdio: 'inherit' });
  console.log('✅ Linting completed\n');
} catch (error) {
  console.warn('⚠️  Linting completed with warnings\n');
}

// Run tests
console.log('🧪 Running tests...');
try {
  execSync('npm test', { stdio: 'inherit' });
  console.log('✅ Tests passed\n');
} catch (error) {
  console.error('❌ Tests failed');
  process.exit(1);
}

// Package extension
console.log('📦 Packaging extension...');
try {
  execSync('npm run package', { stdio: 'inherit' });
  console.log('✅ Extension packaged\n');
} catch (error) {
  console.error('❌ Packaging failed');
  process.exit(1);
}

// Display build info
const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const vsixFile = `${packageJson.name}-${packageJson.version}.vsix`;

console.log('🎉 Build completed successfully!\n');
console.log(`📋 Extension Details:`);
console.log(`   Name: ${packageJson.displayName}`);
console.log(`   Version: ${packageJson.version}`);
console.log(`   Package: ${vsixFile}`);
console.log('\n🚀 Installation:');
console.log(`   code --install-extension ${vsixFile}`);
console.log('\n📚 Next Steps:');
console.log('   1. Install the extension in VS Code');
console.log('   2. Open a RevitPy project');
console.log('   3. Connect to Revit and start developing!');