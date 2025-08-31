import { copyFileSync, mkdirSync, readdirSync, statSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Check where the build output is
const possibleSourceDirs = [
  join(__dirname, 'dist'),
  join(__dirname, '../../weightd/app/static')
];

const targetDir = join(__dirname, '../../weightd/app/static');

// Create target directory if it doesn't exist
mkdirSync(targetDir, { recursive: true });

// Find which source directory exists
let sourceDir = null;
for (const dir of possibleSourceDirs) {
  if (existsSync(dir)) {
    sourceDir = dir;
    break;
  }
}

if (!sourceDir) {
  console.error('Error: Could not find build output directory');
  process.exit(1);
}

console.log(`Using source directory: ${sourceDir}`);

// Function to copy files recursively
function copyRecursiveSync(src, dest) {
  const entries = readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);

    if (entry.isDirectory()) {
      mkdirSync(destPath, { recursive: true });
      copyRecursiveSync(srcPath, destPath);
    } else {
      copyFileSync(srcPath, destPath);
      console.log(`Copied: ${srcPath} -> ${destPath}`);
    }
  }
}

console.log(`Copying files from ${sourceDir} to ${targetDir}`);
try {
  // If source and target are the same, no need to copy
  if (sourceDir !== targetDir) {
    copyRecursiveSync(sourceDir, targetDir);
    console.log('Successfully copied all files');
  } else {
    console.log('Source and target are the same, skipping copy');
  }
} catch (error) {
  console.error('Error copying files:', error);
  process.exit(1);
}
