#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🔌 Installing RevitPy VS Code Extension...\n');

// Check if VS Code is installed
console.log('🔍 Checking VS Code installation...');
try {
  execSync('code --version', { stdio: 'pipe' });
  console.log('✅ VS Code found\n');
} catch (error) {
  console.error('❌ VS Code not found in PATH');
  console.log('\n💡 Please ensure VS Code is installed and the "code" command is available');
  console.log('   You can enable it by opening VS Code and running:');
  console.log('   Command Palette > Shell Command: Install \'code\' command in PATH');
  process.exit(1);
}

// Find VSIX file
const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const vsixFile = `${packageJson.name}-${packageJson.version}.vsix`;

if (!fs.existsSync(vsixFile)) {
  console.error(`❌ Extension package not found: ${vsixFile}`);
  console.log('\n💡 Run the build script first:');
  console.log('   npm run build');
  process.exit(1);
}

// Install extension
console.log(`📦 Installing extension: ${vsixFile}`);
try {
  execSync(`code --install-extension ${vsixFile}`, { stdio: 'inherit' });
  console.log('✅ Extension installed successfully!\n');
} catch (error) {
  console.error('❌ Extension installation failed');
  process.exit(1);
}

// Check installation
console.log('🔍 Verifying installation...');
try {
  const result = execSync('code --list-extensions', { encoding: 'utf8' });
  if (result.includes(packageJson.name)) {
    console.log('✅ Extension verified in VS Code\n');
  } else {
    console.warn('⚠️  Extension not found in list, but installation reported success\n');
  }
} catch (error) {
  console.warn('⚠️  Could not verify installation\n');
}

console.log('🎉 Installation completed!\n');
console.log('📋 Extension Information:');
console.log(`   ID: ${packageJson.name}`);
console.log(`   Name: ${packageJson.displayName}`);
console.log(`   Version: ${packageJson.version}`);
console.log('\n🚀 Getting Started:');
console.log('1. Open VS Code');
console.log('2. Create or open a RevitPy project');
console.log('3. Use Ctrl+Shift+P and search for "RevitPy" commands');
console.log('4. Connect to Revit and start developing!');
console.log('\n📚 Documentation: https://docs.revitpy.com');
console.log('🐛 Issues: https://github.com/revitpy/vscode-extension/issues');