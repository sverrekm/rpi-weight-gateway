import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Source and destination directories
const srcDir = path.join(__dirname, 'dist');
const destDir = path.join(__dirname, '..', 'weightd', 'app', 'static');
const staticAssetsDir = path.join(__dirname, '..', '..', 'static');

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

    // First, copy all files from dist to static directory
    await fs.copy(srcDir, destDir, { 
      overwrite: true,
      filter: (src) => !src.endsWith('favicon.ico') // Skip any favicon.ico from dist
    });
    
    // Then ensure the static assets directory exists and copy favicon.png
    if (fs.existsSync(staticAssetsDir)) {
      const faviconSrc = path.join(staticAssetsDir, 'favicon.png');
      if (fs.existsSync(faviconSrc)) {
        await fs.copyFile(faviconSrc, path.join(destDir, 'favicon.png'));
        console.log('Copied favicon.png to static directory');
      } else {
        console.warn('Warning: favicon.png not found in static directory');
      }
      
      // Copy any other static assets
      const files = await fs.readdir(staticAssetsDir);
      for (const file of files) {
        const srcPath = path.join(staticAssetsDir, file);
        const destPath = path.join(destDir, file);
        if (file !== 'favicon.png') { // Skip favicon.png as we already copied it
          const stat = await fs.stat(srcPath);
          if (stat.isDirectory()) {
            await fs.copy(srcPath, destPath, {
              overwrite: true,
              recursive: true,
              filter: (src) => {
                // Skip node_modules and other unnecessary files
                if (src.includes('node_modules')) return false;
                if (src.endsWith('.map')) return false;
                return true;
              }
            });
          } else {
            await fs.copyFile(srcPath, destPath);
          }
          console.log(`Copied ${file} to static directory`);
        }
      }
    } else {
      console.warn(`Warning: Static assets directory not found: ${staticAssetsDir}`);
    }
    
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
