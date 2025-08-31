const fs = require('fs-extra');
const path = require('path');

// Source and destination directories
const srcDir = path.join(__dirname, 'dist');
const destDir = path.join(__dirname, '..', 'weightd', 'app', 'static');

// Ensure source directory exists
if (!fs.existsSync(srcDir)) {
  console.error(`Error: Source directory ${srcDir} does not exist`);
  process.exit(1);
}

console.log(`Copying files from ${srcDir} to ${destDir}`);

// Ensure destination directory exists
fs.ensureDirSync(destDir);

// Clear destination directory first
fs.emptyDirSync(destDir);

// Copy files from dist to static directory
try {
  fs.copySync(srcDir, destDir, { 
    overwrite: true, 
    recursive: true,
    filter: (src) => {
      // Skip node_modules and other unnecessary files
      if (src.includes('node_modules')) return false;
      if (src.endsWith('.map')) return false;
      return true;
    }
  });
  
  console.log(`Successfully copied files to ${destDir}`);
  
  // Verify the copy was successful
  const files = fs.readdirSync(destDir);
  console.log(`Copied ${files.length} files to ${destDir}`);
  console.log('Files:', files.join(', '));
  
} catch (err) {
  console.error('Error copying files:', err);
  process.exit(1);
}
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
