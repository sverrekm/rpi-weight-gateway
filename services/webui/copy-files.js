import { copyFileSync, mkdirSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourceDir = join(__dirname, 'dist');
const targetDir = join(__dirname, '../../weightd/app/static');

// Create target directory if it doesn't exist
mkdirSync(targetDir, { recursive: true });

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
  copyRecursiveSync(sourceDir, targetDir);
  console.log('Successfully copied all files');
} catch (error) {
  console.error('Error copying files:', error);
  process.exit(1);
}
