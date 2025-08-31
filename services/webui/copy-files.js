import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Source and destination directories
const srcDir = path.join(__dirname, 'dist');
const destDir = path.join(__dirname, '..', 'weightd', 'app', 'static');

async function copyFiles() {
  try {
    // Ensure source directory exists
    if (!fs.existsSync(srcDir)) {
      console.error(`Error: Source directory ${srcDir} does not exist`);
      process.exit(1);
    }

    console.log(`Copying files from ${srcDir} to ${destDir}`);

    // Ensure destination directory exists
    fs.ensureDirSync(destDir);

    // Clear destination directory first
    await fs.emptyDir(destDir);

    // Copy files from dist to static directory
    await fs.copy(srcDir, destDir, { 
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
    const files = await fs.readdir(destDir);
    console.log(`Copied ${files.length} files to ${destDir}`);
    console.log('Files:', files.join(', '));
    
  } catch (err) {
    console.error('Error copying files:', err);
    process.exit(1);
  }
}

// Execute the copy operation
copyFiles();
