import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

// Ensure process.cwd matches the real target directory if launched through a junction/symlink
if (process.cwd().toLowerCase() !== rootDir.toLowerCase().replace(/[\/\\]$/, "")) {
  try {
    process.chdir(rootDir);
  } catch (e) {
    // ignore
  }
}

export default defineConfig({
  root: rootDir,
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      strict: false,
    },
  },
});
